# CLAUDE.md

This file is read automatically by Claude Code at the start of every session.
**Purpose**: give Claude the long-lived context it needs so we don't have to re-explain the project each time.

---

## 1. Project at a Glance

- **Repo**: `food_mes_kr` — ERPNext custom app
- **Goal**: Adapt ERPNext v15 for **Korean small-to-mid F&B (food & beverage) manufacturers**, especially **liquid-food OEM/ODM** (e.g. juice in spouted pouches, konjac jelly).
- **Current phase**: prototype → first pilot
- **Stack**: Frappe Framework v15 + ERPNext v15 + Python 3.11 + MariaDB 10.6+ + Redis
- **License**: GPLv3 (inherits from ERPNext)

---

## 2. Hard Rules — read carefully

These rules exist because past mistakes cost real days. Do not violate without explicit confirmation from the user.

### 2.1 NEVER touch ERPNext or Frappe core
The directories `apps/frappe/` and `apps/erpnext/` are **read-only** from our perspective.
If a fix seems to require editing core, the right answer is one of:
1. A Custom Field (preferred)
2. A `doc_events` hook in our `hooks.py`
3. A `override_doctype_class` (only when truly needed)
4. A monkeypatch in our app's `__init__.py` (last resort, document why)

### 2.2 NEVER use browser storage in client scripts
`localStorage`, `sessionStorage`, `IndexedDB` are not allowed. Use Frappe's server-side User Settings or document fields.

### 2.3 NEVER hardcode Korean strings outside `_()` translation calls
All user-visible text goes through `frappe._()` (Python) or `__()` (JS) so we can localize later.

### 2.4 NEVER write SQL with string interpolation
Use `frappe.db.sql(query, params_dict)`. SQL injection in a food traceability system would be a regulatory disaster.

### 2.5 ALWAYS check Custom Field existence before reading it
Server scripts may run before fixtures are imported. Use the helper:
```python
def _has_custom_field(doctype, fieldname):
    return bool(frappe.db.exists("Custom Field", {"dt": doctype, "fieldname": fieldname}))
```
This pattern already exists in `server_scripts/work_order_lot.py`.

### 2.6 ALWAYS make hooks idempotent
A hook may fire on retry, on data import, on bulk update. Re-running it must not corrupt data. Example: `assign_production_lot_no` returns early if `production_lot_no` is already set.

### 2.7 ALWAYS sanitize ASCII-only for identifiers
Korean strings are valid Unicode and `str.isalnum()` returns True for them. For LOT codes, line codes, etc., use `c.isascii() and c.isalnum()`. There is a unit test that catches this regression.

---

## 3. Directory Map

```
food_mes_kr/                              ← repo root (this dir)
├── CLAUDE.md                             ← you are here
├── README.md                             ← human-facing intro
├── DEVELOPMENT_GUIDE.md                  ← full dev workflow
├── TROUBLESHOOTING.md                    ← common errors
├── setup.py / requirements.txt
├── prompts/                              ← per-task prompt templates
└── food_mes_kr/                          ← Python package
    ├── __init__.py                       ← __version__
    ├── hooks.py                          ★ event registration center
    ├── modules.txt
    ├── patches.txt
    ├── fixtures/
    │   └── custom_field.json             ★ all Custom Fields here
    └── food_mes_kr/                      ← business module
        ├── tasks.py                      ← scheduler jobs
        ├── demo_seed.py                  ← demo data generator
        ├── server_scripts/               ★ Python hooks
        │   ├── work_order_lot.py
        │   └── batch_naming.py
        ├── report/                       ★ Script Reports
        │   ├── forward_trace/
        │   └── backward_trace/
        ├── doctype/                      ← custom DocTypes (Allergen, etc.)
        ├── print_format/                 ← labels (KC food label, ZPL)
        └── api/                          ← external integrations
```

---

## 4. Domain Cheat Sheet

### 4.1 Korean LOT format
`YYMMDD-LINE-SEQ` (e.g. `251207-L1-001`)
- Date: planned_start_date in KST, fallback today
- Line: from `Workstation.line_code` (Custom Field), fallback first 3 chars of workstation name
- SEQ: zero-padded 3+ digits, monotonic per (date, line)

This LOT becomes the `Batch.batch_id` for finished goods (see `batch_naming.py`).

### 4.2 The traceability spine
Forward: `consume(parent SLE) → Stock Entry: Manufacture → produce(child SLE)` — recurse downward.
Backward: same shape, recurse upward.

Both queries already exist in `report/forward_trace/` and `report/backward_trace/`. Their algorithm is verified by `test_trace_queries.py`.

### 4.3 HACCP CCP mapping
- CCP (Critical Control Point) = `Item Quality Inspection Parameter.is_ccp = 1`
- Critical Limit (CL) = `min_value` and `max_value`
- Monitoring record = `Quality Inspection Reading`
- Out-of-limit handling = automatic `Non Conformance` creation (see `quality_inspection_hook.py` once implemented)

### 4.4 식약처 (MFDS) labeling fields a finished-goods Item must carry
- `kc_food_code` — 식품유형 (e.g. 04101 = 과채주스)
- `allergen_flags` — multi-select against Allergen master
- `is_organic`, `is_halal` — booleans
- `shelf_life_in_days` — drives Batch.expiry_date
- `nutrition_facts` — JSON, per-100mL or per-serving

### 4.5 OEM/ODM data shape
A single recipe can produce many SKUs that differ only in label.
We model this as: one **internal Item** for the bulk product + multiple **Customer-owned Items** (`customer_owned=1`) referencing the same BOM.

---

## 5. ERPNext Patterns Used Here

When in doubt, look for an example in the existing code:

| If you need... | Look at... |
|---|---|
| A new Custom Field | `fixtures/custom_field.json` |
| A `doc_events` hook | `server_scripts/work_order_lot.py` |
| A scheduled job | `food_mes_kr/tasks.py` |
| A Script Report with recursive SQL | `report/forward_trace/forward_trace.py` |
| Demo seed code | `food_mes_kr/demo_seed.py` |
| A whitelisted API method | `regenerate_lot_no` in `work_order_lot.py` |

A new DocType (e.g. Allergen) does not exist yet but should follow the standard ERPNext layout:
```
doctype/<name>/
├── __init__.py
├── <name>.json    ← schema (autogenerated by `bench new-doctype` then edited)
├── <name>.py      ← controller class extending Document
├── <name>.js      ← form script (optional)
└── test_<name>.py ← unittest
```

---

## 6. Testing

### 6.1 Pure-Python tests (no Frappe needed)
Live in `tests/` at repo root or alongside the file under test. Use stdlib `unittest`.

### 6.2 Frappe integration tests
Inherit `frappe.tests.utils.FrappeTestCase`. Run with:
```bash
bench --site dev.localhost run-tests --app food_mes_kr
```

### 6.3 Manual smoke test before every commit
1. `bench --site dev.localhost migrate`
2. `bench --site dev.localhost clear-cache`
3. Open the affected screen in browser, do one happy-path action.

If any of these fail, do not commit.

---

## 7. How to Make Changes Safely

The standard cycle:

```bash
# 0. Start fresh
git status                  # working tree clean?
git pull                    # latest

# 1. Branch
git checkout -b feature/<task-id>-<short-desc>

# 2. Edit files (Claude does this)

# 3. Apply changes to the running site
bench --site dev.localhost migrate
bench --site dev.localhost clear-cache
bench --site dev.localhost reload-doc <module> <doctype> <name>   # for DocType edits
# OR
touch apps/food_mes_kr/food_mes_kr/hooks.py   # forces Python reload during `bench start`

# 4. Test in browser

# 5. Run automated tests
bench --site dev.localhost run-tests --app food_mes_kr

# 6. Export fixtures if Custom Fields/Property Setters changed
bench --site dev.localhost export-fixtures --app food_mes_kr

# 7. Commit
git add -A
git diff --staged           # final review
git commit -m "<task-id>: <one-line summary>"
```

---

## 8. Things Not To Build (Anti-goals)

- **A separate database for IoT/sensor data.** Use Node-RED + InfluxDB outside ERPNext, push aggregated readings via REST API.
- **A custom MES UI replacing ERPNext desk.** We extend the existing UI; we do not rebuild.
- **Generic ERP features that ERPNext already has** (e.g. POs, GL, AR/AP). Only add when standard ERPNext fails for F&B specifically.
- **Korean accounting (e-Tax, KSI) inside this app.** That belongs in a separate `erpnext_korea` style app or commercial regional pack.

---

## 9. When You're Stuck

In rough priority:
1. Search this repo for an existing pattern.
2. Search `apps/erpnext/erpnext/` (READ-ONLY) for how core does it.
3. Check https://docs.frappe.io and https://docs.erpnext.com.
4. Ask the user. Don't invent a Frappe API that doesn't exist.

If a Frappe API call is uncertain, prefer reading `apps/frappe/frappe/__init__.py` or the relevant module to confirm signature, rather than guessing.

---

## 10. Style

- Python: PEP 8, 4-space indent, type hints where useful (Frappe core is loose about this; we are stricter).
- Docstrings: short summary line + blank line + details. Korean inline comments OK; English for public APIs.
- JS: ES6+, no jQuery unless required (Frappe still uses `$` heavily).
- SQL: lowercase keywords or uppercase consistently within a single query; backtick all table names like `` `tabXxx` ``.
- Commit messages: `<task-id>: <imperative summary>` (e.g. `T2.3: add measurement fields to Job Card`).

---

## 11. Current State (update this when major milestones land)

- **2025-12**: Prototype with LOT numbering, Forward/Backward Trace, demo seed. SQL algorithm validated by SQLite test harness. 19 Custom Fields defined.
- **Next**: T1.1 (Allergen DocType), T2.3 (Job Card measurement fields), T3.2 (auto-NC on CCP failure).

---

## 12. Glossary (for non-domain folks pairing with Claude)

| Term | Meaning |
|---|---|
| BOM | Bill of Materials = recipe |
| Routing | sequence of operations (mixing → sterilizing → filling → ...) |
| Work Order (WO) | one production run authorization |
| Job Card | one operation within a WO that an operator works on |
| Stock Entry | warehouse movement (issue, receive, transfer, manufacture) |
| Batch / LOT | a tracked lot of identical material with shared mfg/exp date |
| Quality Inspection (QI) | one inspection record |
| Non Conformance (NC) | a recorded quality failure |
| CAPA | Corrective Action / Preventive Action |
| HACCP | Hazard Analysis and Critical Control Points (food safety system) |
| CCP | Critical Control Point |
| FEFO | First Expired, First Out (used instead of FIFO for food) |
| OEM/ODM | making products under another company's brand |
| 식약처 (MFDS) | Korean Ministry of Food and Drug Safety |
