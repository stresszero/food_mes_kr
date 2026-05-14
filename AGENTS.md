# AGENTS.md — food_mes_kr 코딩 에이전트 가이드

이 파일은 이 저장소에서 작업하는 모든 코딩 에이전트(Claude Code 등)가 매 세션마다 읽어야 할 단일 진입점입니다.
**여기 나온 규칙이 다른 문서보다 우선합니다.**

---

## 1. 프로젝트 개요

| 항목 | 내용 |
|---|---|
| 앱 이름 | `food_mes_kr` (Food MES Korea) |
| 목적 | ERPNext v15를 한국 식음료 제조사(음료 OEM/ODM 중심)에 맞게 확장하는 커스텀 앱 |
| 현재 상태 | 프로토타입 — LOT 채번·추적 구현 완료, HACCP·라벨 미구현 |
| 라이선스 | GPLv3 (ERPNext 따름) |

### 이 앱이 하는 것
- 한국식 LOT 번호 자동 채번 (`YYMMDD-LINE-SEQ`)
- 완제품 Batch에 LOT 번호 자동 적용
- 원료→완제품 Forward Trace / 완제품→원료 Backward Trace (재귀 CTE)
- 유통기한 임박 Batch 일일 알림
- 식음료 전용 Custom Fields 19개 (알러겐, 식품유형코드, CCP 등)

### 이 앱이 하지 않는 것 (Anti-goals)
- ERPNext/Frappe 코어 수정 — 절대 불가
- 별도 IoT/센서 DB 구축 — Node-RED + InfluxDB 외부에서 처리
- ERPNext 화면 전체 재설계 — 기존 UI 확장만
- 한국 회계(전자세금계산서, KSI) — 별도 앱으로 분리
- ERPNext가 이미 제공하는 표준 ERP 기능 (구매, 회계, AR/AP)

---

## 2. 기술 스택

| 항목 | 버전/내용 |
|---|---|
| 기반 플랫폼 | Frappe Framework v15 + ERPNext v15 |
| 언어 | Python 3.11+ |
| DB | MariaDB 10.6+ (재귀 CTE 필수) |
| 캐시/큐 | Redis |
| 설치 방식 | `frappe-bench` + Docker devcontainer 권장 |
| 테스트 | stdlib `unittest` (단순 로직) + `frappe.tests.utils.FrappeTestCase` (통합) |

---

## 3. 저장소 구조 (실제 현황 기준)

```
CustomNextERP/                            ← 작업 루트
├── AGENTS.md                             ← 이 파일
├── README.md                             ← 인간용 소개
├── food_mes_kr/                          ← pip 설치 가능한 앱 패키지 루트
│   ├── setup.py
│   ├── requirements.txt
│   ├── test_lot_logic.py                 ← 독립 단위 테스트 (Frappe 불필요)
│   ├── test_trace_queries.py             ← SQLite로 CTE 알고리즘 검증
│   └── food_mes_kr/                      ← 앱 Python 패키지
│       ├── __init__.py                   ← __version__ 정의
│       ├── hooks.py                      ★ 모든 훅·이벤트 등록 (진입점)
│       ├── modules.txt
│       ├── patches.txt
│       ├── fixtures/
│       │   └── custom_field.json         ★ Custom Field 19개 정의
│       └── food_mes_kr/                  ← 비즈니스 로직 모듈
│           ├── tasks.py                  ← 스케줄러 작업
│           ├── demo_seed.py              ← 시연용 더미 데이터 생성기
│           ├── server_scripts/           ★ doc_events 훅 함수
│           │   ├── work_order_lot.py     ← LOT 자동 채번
│           │   └── batch_naming.py       ← Batch에 LOT 적용
│           └── report/                   ★ Script Reports
│               ├── forward_trace/        ← 원료→완제품 추적
│               │   ├── forward_trace.json
│               │   ├── forward_trace.py
│               │   └── forward_trace.js
│               └── backward_trace/       ← 완제품→원료 추적
│                   ├── backward_trace.json
│                   ├── backward_trace.py
│                   └── backward_trace.js
├── erpnext_guide/                        ← 개발 가이드 문서
│   ├── CLAUDE.md
│   ├── DEVELOPMENT_GUIDE.md              ← 4 Phase 16 Task 로드맵
│   └── TROUBLESHOOTING.md
└── *.py (루트)                           ← 독립 실행 테스트/유틸 스크립트
```

### 신규 기능 파일 위치 규칙

| 추가할 것 | 위치 |
|---|---|
| 새 Custom Field | `food_mes_kr/fixtures/custom_field.json` |
| 새 doc_events 훅 | `food_mes_kr/food_mes_kr/server_scripts/<name>.py` + `hooks.py` 등록 |
| 새 Script Report | `food_mes_kr/food_mes_kr/report/<name>/` |
| 새 Custom DocType | `food_mes_kr/food_mes_kr/doctype/<name>/` |
| 새 Print Format | `food_mes_kr/food_mes_kr/print_format/<name>/` |
| 외부 API 연동 | `food_mes_kr/food_mes_kr/api/<name>.py` |
| 스케줄러 작업 | `food_mes_kr/food_mes_kr/tasks.py` + `hooks.py` 등록 |

---

## 4. 절대 규칙 (위반 금지)

### 4.1 ERPNext/Frappe 코어 절대 수정 금지
`apps/frappe/`, `apps/erpnext/` 디렉터리는 **읽기 전용**. 코어 수정이 필요해 보이면 아래 순서로 해결:
1. Custom Field (우선)
2. `doc_events` 훅
3. `override_doctype_class` (필요한 경우만)
4. `__init__.py` 몽키패치 (최후 수단, 반드시 이유 주석)

### 4.2 SQL 문자열 보간 절대 금지
```python
# 금지
frappe.db.sql(f"SELECT * FROM `tabBatch` WHERE name = '{batch_id}'")

# 필수
frappe.db.sql("SELECT * FROM `tabBatch` WHERE name = %(name)s", {"name": batch_id})
```
식품 추적 시스템의 SQL 인젝션은 규제 위반 사고임.

### 4.3 브라우저 스토리지 사용 금지
`localStorage`, `sessionStorage`, `IndexedDB` 사용 불가. Frappe 서버사이드 User Settings 또는 문서 필드 사용.

### 4.4 한국어 문자열 직접 하드코딩 금지
```python
# 금지
frappe.throw("LOT 번호가 없습니다")

# 필수
frappe.throw(_("LOT 번호가 없습니다"))  # Python: frappe._()
```
JS에서는 `__()` 사용.

### 4.5 Custom Field 존재 확인 후 접근
fixtures가 아직 import되지 않은 환경에서도 앱이 깨지지 않도록:
```python
def _has_custom_field(doctype: str, fieldname: str) -> bool:
    return bool(frappe.db.exists("Custom Field", {"dt": doctype, "fieldname": fieldname}))
```
이 패턴은 `work_order_lot.py`에 이미 정의되어 있음. 재정의 하지 말고 import해서 사용.

### 4.6 훅은 반드시 멱등성 보장
훅은 재시도·데이터 import·bulk update 시 중복 실행될 수 있음.
```python
# 올바른 패턴: 이미 값이 있으면 건드리지 않음
if doc.get("production_lot_no"):
    return
```

### 4.7 식별자에 ASCII 영숫자만 허용
Python의 `str.isalnum()`은 한글에서도 `True`를 반환함. LOT 코드·라인 코드 등 식별자에는 반드시:
```python
# 금지
"".join(c for c in s if c.isalnum())

# 필수
"".join(c for c in s if c.isascii() and c.isalnum()).upper()
```

---

## 5. 구현된 기능 상세

### 5.1 hooks.py 등록 현황

| DocType | 이벤트 | 함수 | 상태 |
|---|---|---|---|
| Work Order | `before_insert` | `work_order_lot.assign_production_lot_no` | ✅ 구현 |
| Work Order | `before_submit` | `work_order_lot.finalize_production_lot` | ✅ 구현 |
| Batch | `before_insert` | `batch_naming.apply_work_order_lot_to_batch` | ✅ 구현 |
| Stock Entry | `validate` | `stock_entry_validate.warn_on_fefo_violation` | ⬜ 미구현 |
| Quality Inspection | `on_submit` | `quality_inspection_hook.auto_create_non_conformance_on_ccp_failure` | ⬜ 미구현 |

### 5.2 Custom Fields (fixtures/custom_field.json)

| DocType | 필드명 | 타입 | 용도 |
|---|---|---|---|
| Workstation | `line_code` | Data | LOT 채번 시 라인 코드 (예: L1) |
| Work Order | `production_lot_no` | Data (read-only) | 자동 채번된 LOT 번호 |
| Work Order | `production_line` | Link→Workstation | LOT 채번 기준 라인 |
| Work Order | `production_shift` | Link→Shift Type | 작업 교대 |
| Work Order | `mfg_date` | Date (read-only) | 자동 계산 제조일자 |
| Work Order | `best_before_date` | Date (read-only) | 자동 계산 유통기한 |
| Item | `allergen_flags` | Small Text | 알러겐 표시 (추후 Table MultiSelect로 변경 예정) |
| Item | `is_halal` | Check | 할랄 인증 여부 |
| Item | `is_organic` | Check | 유기농 인증 여부 |
| Item | `kc_food_code` | Data | 식약처 식품유형 코드 (예: 04101) |
| Item | `storage_temp_min` | Float | 최저 보관 온도 |
| Item | `storage_temp_max` | Float | 최고 보관 온도 |
| Item | `customer_owned` | Check | OEM 고객 소유 SKU 여부 |
| Item | `customer` | Link→Customer | OEM 고객사 |
| Item Quality Inspection Parameter | `is_ccp` | Check | HACCP CCP 여부 |
| Non Conformance | `severity` | Select | 심각도 |
| Non Conformance | `due_date` | Date | 조치 기한 |
| Non Conformance | `assigned_to` | Link→User | 담당자 |
| Non Conformance | `linked_quality_inspection` | Link→Quality Inspection | 연결 QI |
| Non Conformance | `linked_batch` | Link→Batch | 연결 Batch |
| Non Conformance | `effectiveness_check` | Check | CAPA 효과성 검증 완료 |

### 5.3 스케줄러

```python
scheduler_events = {
    "daily": ["food_mes_kr.food_mes_kr.tasks.notify_expiring_batches"],  # ✅ 구현
    "hourly": [],  # HACCP 모니터링 누락 알림 — ⬜ 미구현 (주석 처리됨)
}
```

---

## 6. 도메인 지식

### 6.1 한국식 LOT 채번 규칙
```
형식: YYMMDD-LINE-SEQ
예시: 251207-L1-001

- YYMMDD : Work Order.planned_start_date 기준 KST (없으면 today(KST))
- LINE   : Workstation.line_code (Custom Field) 우선, 없으면 워크스테이션 이름 첫 3 영숫자
- SEQ    : 같은 (날짜, 라인) 조합 내 일련번호 3자리 (0 패딩)
```
이 LOT 번호가 그대로 완제품 `Batch.batch_id`가 됨.

### 6.2 Traceability 알고리즘

```
Forward (원료 → 완제품):
  consume_sle (actual_qty < 0)
    → Stock Entry: Manufacture (같은 voucher_no)
    → produce_sle (actual_qty > 0)
    → 재귀 반복 (최대 depth=6)

Backward (완제품 → 원료):
  produce_sle (actual_qty > 0)
    → Stock Entry: Manufacture (같은 voucher_no)
    → consume_sle (actual_qty < 0)
    → 재귀 반복 (최대 depth=6)
```

두 쿼리 모두 `WITH RECURSIVE` CTE로 구현되어 있고 MariaDB 10.6+ / MySQL 8.0+ / PostgreSQL 호환.

### 6.3 HACCP 구조

| ERPNext 개념 | HACCP 개념 |
|---|---|
| `Item Quality Inspection Parameter.is_ccp = 1` | CCP 지정 |
| `min_value` / `max_value` | 한계기준 (Critical Limit) |
| `Quality Inspection Reading` | 모니터링 기록 |
| `Non Conformance` (자동 생성) | 이탈 기록 + CAPA |

### 6.4 식약처 표시 필수 항목 (완제품 Item)

| 필드 | 내용 |
|---|---|
| `kc_food_code` | 식품유형 (예: 04101 = 과채주스) |
| `allergen_flags` | 22종 알러겐 다중 선택 |
| `is_organic`, `is_halal` | 인증 여부 |
| `shelf_life_in_days` | Batch.expiry_date 자동 계산 기준 |
| `nutrition_facts` | 영양성분 (JSON, 100mL 또는 1회 제공량 기준) |

### 6.5 OEM/ODM 데이터 모델
한 레시피로 여러 고객사 SKU를 생산:
- 내부 벌크 Item (`customer_owned = 0`) → BOM/Routing 정의
- 고객사 Item (`customer_owned = 1`, `customer = "거래처명"`) → 동일 BOM 연결

---

## 7. ERPNext 핵심 패턴 (코드 예시)

### Custom Field 추가
`fixtures/custom_field.json`에 항목 추가 후 `bench migrate`:
```json
{
  "doctype": "Custom Field",
  "name": "Work Order-my_field",
  "dt": "Work Order",
  "fieldname": "my_field",
  "label": "My Field",
  "fieldtype": "Data",
  "insert_after": "production_lot_no",
  "module": "Food Mes Kr"
}
```

### doc_events 훅 등록
`hooks.py`에 추가:
```python
doc_events = {
    "Work Order": {
        "before_insert": "food_mes_kr.food_mes_kr.server_scripts.my_module.my_function",
    },
}
```

### Whitelisted API 메서드 (UI에서 호출 가능)
```python
@frappe.whitelist()
def my_api_function(param: str) -> dict:
    ...
```

### Script Report 최소 구조
```python
def execute(filters=None):
    filters = filters or {}
    columns = [{"label": _("Name"), "fieldname": "name", "fieldtype": "Data", "width": 200}]
    data = frappe.db.sql("SELECT ...", filters, as_dict=True)
    return columns, data
```

### 새 Custom DocType 디렉터리 구조
```
doctype/<name>/
├── __init__.py
├── <name>.json    ← schema (bench new-doctype 후 편집)
├── <name>.py      ← Document 상속 컨트롤러
├── <name>.js      ← Form 스크립트 (선택)
└── test_<name>.py ← FrappeTestCase 상속 테스트
```

---

## 8. 개발 워크플로우

### 변경 적용 사이클
```bash
# 1. 코드 편집 후
bench --site dev.localhost migrate        # fixture·DocType 변경 적용
bench --site dev.localhost clear-cache    # 캐시 제거

# hooks.py만 변경했을 때 빠른 리로드
touch apps/food_mes_kr/food_mes_kr/hooks.py

# DocType JSON 변경 시
bench --site dev.localhost reload-doc <module> <doctype> <name>

# 2. 브라우저에서 직접 시나리오 실행 (필수)

# 3. 테스트
bench --site dev.localhost run-tests --app food_mes_kr

# 4. fixture export (Custom Field 변경 시)
bench --site dev.localhost export-fixtures --app food_mes_kr
```

### 커밋 메시지 형식
```
<Task-ID>: <명령형 한 줄 요약>
예) T2.3: Job Card 측정값 필드 추가 + QI 자동 연결
```

### 환경 분리

| 환경 | 사이트명 | 용도 |
|---|---|---|
| dev | `dev.localhost` | 개발/에이전트 작업 |
| demo | `demo.localhost` | 시연 (더미 데이터) |
| staging | `staging.<domain>` | 고객 검수 |
| production | 실제 도메인 | 운영 |

---

## 9. 테스트 지침

### 독립 단위 테스트 (Frappe 불필요)
`test_lot_logic.py`, `test_trace_queries.py` — SQLite로 핵심 알고리즘 검증.
```bash
python food_mes_kr/test_lot_logic.py
python food_mes_kr/test_trace_queries.py
```

### Frappe 통합 테스트
```python
import frappe.tests.utils

class TestWorkOrderLot(frappe.tests.utils.FrappeTestCase):
    def test_lot_auto_assigned(self):
        wo = frappe.get_doc({...}).insert()
        self.assertRegex(wo.production_lot_no, r'^\d{6}-[A-Z0-9]+-\d{3}$')
```
```bash
bench --site dev.localhost run-tests --app food_mes_kr
```

### 커밋 전 최소 스모크 테스트
1. `bench migrate` + `clear-cache` 에러 없음
2. 브라우저에서 영향받은 화면 직접 확인
3. 위 두 가지 실패 시 커밋 금지

---

## 10. 개발 로드맵 (16 Tasks)

```
[Phase 1: 마스터 데이터]  ← 4개 독립적, 병렬 가능
  T1.1 알러겐 DocType (식약처 22종)
  T1.2 식품유형 코드 DocType (kc_food_code → Link)
  T1.3 라인·교대 마스터 정비 (Shift Type fixture)
  T1.4 데이터 Import 템플릿 (Item, BOM, Customer CSV)

[Phase 2: 생산 실행]      ← Phase 1 완료 후
  T2.1 LOT 채번 보강 (멀티 회사, 재발행 UI)    ← 일부 구현됨
  T2.2 FEFO 자동 출고 (stock_entry_validate.py)
  T2.3 Job Card 측정값 입력 (온도/pH/Brix + QI 연결)
  T2.4 작업자 태블릿 화면 (Client Script 또는 /operator/tablet)

[Phase 3: 품질·HACCP]     ← Phase 1 완료 후
  T3.1 CCP 모니터링 로그 보고서
  T3.2 CCP 이탈 시 Non Conformance 자동 생성    ← hooks.py placeholder 있음
  T3.3 NC → CAPA 워크플로우 (6단계 Workflow DocType)
  T3.4 Trace 보고서 보강 (Recall Notice PDF)    ← 기본 구현됨

[Phase 4: 라벨·외부 통합] ← Phase 3 완료 후
  T4.1 식약처 표시기준 라벨 Print Format (Jinja)
  T4.2 ZPL 라벨 프린터 API
  T4.3 스마트스토어 주문 동기화 (선택)
  T4.4 ERP 회계 연동 (별도 프로젝트)
```

**현재 완료**: T2.1 일부, T3.4 기본, 그리고 공통 인프라(Custom Fields, hooks 골격, demo_seed)

---

## 11. 디버깅 참고

| 방법 | 명령 |
|---|---|
| 서버 로그 | `frappe-bench/logs/web.log`, `worker.log` |
| ERPNext 에러 화면 | 관리자 메뉴 → Error Log |
| DB 직접 조회 | `bench --site dev.localhost mariadb` |
| Python REPL | `bench --site dev.localhost console` |
| 특정 함수 실행 | `bench --site dev.localhost execute food_mes_kr.food_mes_kr.demo_seed.run` |

---

## 12. 용어 사전

| 용어 | 의미 |
|---|---|
| BOM | Bill of Materials = 레시피 |
| Routing | 공정 순서 (혼합 → 살균 → 충전 → ...) |
| Work Order (WO) | 생산 지시서 한 건 |
| Job Card | WO 안의 공정 단계 하나 (작업자가 직접 조작) |
| Stock Entry | 창고 이동 기록 (출고/입고/이전/생산) |
| Batch / LOT | 동일 제조일·유통기한을 갖는 추적 단위 |
| Quality Inspection (QI) | 검사 기록 |
| Non Conformance (NC) | 품질 부적합 기록 |
| CAPA | 시정조치 및 예방조치 |
| HACCP | 위해요소 중점관리기준 (식품 안전 관리 시스템) |
| CCP | 중요관리점 (Critical Control Point) |
| FEFO | 선입선출 대신 유통기한 임박순 출고 (First Expired, First Out) |
| OEM/ODM | 타사 브랜드로 제조 납품 |
| 식약처 (MFDS) | 식품의약품안전처 (한국 식품 규제 기관) |
| SLE | Stock Ledger Entry (재고 원장 행) |
| SE | Stock Entry |
| Fixture | `bench migrate` 시 자동 import되는 메타데이터 JSON |
