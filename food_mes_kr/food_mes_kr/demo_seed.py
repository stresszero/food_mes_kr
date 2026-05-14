"""
food_mes_kr/food_mes_kr/demo_seed.py

시연용 가짜 데이터 생성기.
음료 OEM 회사 시나리오 (좋은F&B 같은 회사를 베이스로):
  - 라인 2개 (L1: 파우치 라인, L2: 곤약젤리 라인)
  - 제품 3종 (헬로아이 사과주스, 헬로아이 배도라지, 곤약젤리 복숭아)
  - 원료 5종
  - BOM, Routing, 첫 작업지시까지 자동 생성

실행법:
  bench --site <your-site> execute food_mes_kr.food_mes_kr.demo_seed.run
"""

import frappe
from frappe.utils import today, add_days


COMPANY = None  # run() 시점에 첫 회사 자동 선택


def run():
    """전체 시드 실행."""
    global COMPANY
    COMPANY = frappe.db.get_value("Company", {}, "name")
    if not COMPANY:
        frappe.throw("회사가 먼저 셋업되어 있어야 합니다.")

    print(f"▶ Seeding demo data for company: {COMPANY}")

    _create_uoms()
    _create_warehouses()
    _create_workstations()
    _create_items()
    _create_boms()
    _create_first_work_order()

    frappe.db.commit()
    print("✅ Seed 완료. 메뉴 > Manufacturing > Work Order 에서 확인하세요.")


# ────────────────────────────────────────────────────────────

def _create_uoms():
    for uom in ["mL", "L", "g", "kg", "Pouch"]:
        if not frappe.db.exists("UOM", uom):
            frappe.get_doc({"doctype": "UOM", "uom_name": uom}).insert()


def _create_warehouses():
    for wname in ["원료창고", "WIP", "완제품창고", "스크랩"]:
        if frappe.db.exists("Warehouse", {"warehouse_name": wname, "company": COMPANY}):
            continue
        frappe.get_doc({
            "doctype": "Warehouse",
            "warehouse_name": wname,
            "company": COMPANY,
        }).insert()


def _create_workstations():
    for code, name in [("L1", "파우치 라인 #1"), ("L2", "곤약젤리 라인")]:
        if frappe.db.exists("Workstation", name):
            continue
        ws = frappe.get_doc({
            "doctype": "Workstation",
            "workstation_name": name,
            "production_capacity": 1,
            "hour_rate": 50000,
        })
        ws.insert()
        # Custom Field line_code 설정
        if frappe.db.exists("Custom Field", {"dt": "Workstation", "fieldname": "line_code"}):
            frappe.db.set_value("Workstation", ws.name, "line_code", code)


def _create_items():
    items = [
        # 원료
        {"code": "RM-APPLE-CONC", "name": "사과농축액 70Brix",
         "is_stock": 1, "has_batch": 1, "shelf_life": 365, "uom": "L"},
        {"code": "RM-PEAR-DORAJI", "name": "배도라지 추출액",
         "is_stock": 1, "has_batch": 1, "shelf_life": 365, "uom": "L"},
        {"code": "RM-WATER", "name": "정제수",
         "is_stock": 1, "has_batch": 0, "uom": "L", "valuation_rate": 100},
        {"code": "RM-VITC", "name": "비타민C",
         "is_stock": 1, "has_batch": 1, "shelf_life": 730, "uom": "kg"},
        {"code": "RM-POUCH-80ML", "name": "스파우트파우치 80mL",
         "is_stock": 1, "has_batch": 0, "uom": "Pouch", "valuation_rate": 50},
        # 완제품
        {"code": "FG-HELLO-APPLE", "name": "헬로아이 착즙 달콤사과 80mL",
         "is_stock": 1, "has_batch": 1, "shelf_life": 270, "uom": "Pouch",
         "is_organic": 1, "kc_food_code": "04101"},
        {"code": "FG-HELLO-PEAR", "name": "헬로아이 착즙 배도라지 80mL",
         "is_stock": 1, "has_batch": 1, "shelf_life": 270, "uom": "Pouch",
         "kc_food_code": "04101"},
    ]
    for it in items:
        if frappe.db.exists("Item", it["code"]):
            continue
        doc = frappe.get_doc({
            "doctype": "Item",
            "item_code": it["code"],
            "item_name": it["name"],
            "item_group": "Products" if frappe.db.exists("Item Group", "Products") else "All Item Groups",
            "stock_uom": it["uom"],
            "is_stock_item": it.get("is_stock", 1),
            "include_item_in_manufacturing": 1,
            "has_batch_no": it.get("has_batch", 0),
            "create_new_batch": it.get("has_batch", 0),
            "has_expiry_date": 1 if it.get("shelf_life") else 0,
            "shelf_life_in_days": it.get("shelf_life") or 0,
            "valuation_rate": it.get("valuation_rate") or 0,
        })
        doc.insert()
        # Custom Fields
        if it.get("is_organic"):
            frappe.db.set_value("Item", doc.name, "is_organic", 1)
        if it.get("kc_food_code"):
            frappe.db.set_value("Item", doc.name, "kc_food_code", it["kc_food_code"])


def _create_boms():
    """헬로아이 사과주스 80mL 1팩의 표준 레시피."""
    bom_specs = [
        {
            "fg": "FG-HELLO-APPLE",
            "qty": 1000,  # 1000팩 1배치
            "loss": 5.0,  # 5% 가공 손실 (살균 시 증발 + 라인 잔류)
            "items": [
                ("RM-APPLE-CONC", 12.0, "L"),     # 12L 농축액
                ("RM-WATER", 70.0, "L"),          # 70L 희석수
                ("RM-VITC", 0.05, "kg"),          # 50g 비타민 C
                ("RM-POUCH-80ML", 1050, "Pouch"), # 5% 여유분 포함
            ],
        },
        {
            "fg": "FG-HELLO-PEAR",
            "qty": 1000,
            "loss": 5.0,
            "items": [
                ("RM-PEAR-DORAJI", 80.0, "L"),
                ("RM-VITC", 0.04, "kg"),
                ("RM-POUCH-80ML", 1050, "Pouch"),
            ],
        },
    ]
    for spec in bom_specs:
        # 이미 존재하는 BOM 있으면 skip
        if frappe.db.exists("BOM", {"item": spec["fg"], "is_active": 1}):
            continue
        bom = frappe.get_doc({
            "doctype": "BOM",
            "item": spec["fg"],
            "quantity": spec["qty"],
            "is_active": 1,
            "is_default": 1,
            "process_loss_percentage": spec["loss"],
            "items": [
                {
                    "item_code": code,
                    "qty": qty,
                    "uom": uom,
                    "stock_uom": uom,
                    "rate": 1000,  # 가짜 단가
                }
                for code, qty, uom in spec["items"]
            ],
        })
        bom.insert()
        bom.submit()


def _create_first_work_order():
    """헬로아이 사과주스 1배치(1000팩) 작업지시 생성."""
    if frappe.db.exists("Work Order", {"production_item": "FG-HELLO-APPLE",
                                        "status": ("in", ["Draft", "Not Started"])}):
        return

    bom_no = frappe.db.get_value("BOM", {"item": "FG-HELLO-APPLE", "is_default": 1}, "name")
    if not bom_no:
        return

    workstation = frappe.db.get_value("Workstation", {"workstation_name": "파우치 라인 #1"}, "name")

    def _get_wh(name):
        return frappe.db.get_value("Warehouse", {"warehouse_name": name, "company": COMPANY}, "name")

    wo = frappe.get_doc({
        "doctype": "Work Order",
        "production_item": "FG-HELLO-APPLE",
        "bom_no": bom_no,
        "qty": 1000,
        "company": COMPANY,
        "wip_warehouse": _get_wh("WIP"),
        "fg_warehouse": _get_wh("완제품창고"),
        "scrap_warehouse": _get_wh("스크랩"),
        "planned_start_date": today(),
        "planned_end_date": add_days(today(), 1),
    })
    # Custom Field 직접 셋팅
    if frappe.db.exists("Custom Field", {"dt": "Work Order", "fieldname": "production_line"}):
        wo.production_line = workstation

    wo.insert()
    print(f"  → Created Work Order {wo.name} with LOT {wo.get('production_lot_no')}")


def create_fefo_test_stock():
    """
    FEFO 검증용 테스트 재고 생성.
    RM-APPLE-CONC 를 두 배치(만료일 다름)로 원료창고에 입고한다.

    실행법:
      bench --site <site> execute food_mes_kr.food_mes_kr.demo_seed.create_fefo_test_stock
    """
    global COMPANY
    COMPANY = frappe.db.get_value("Company", {}, "name")

    warehouse = frappe.db.get_value(
        "Warehouse", {"warehouse_name": "원료창고", "company": COMPANY}, "name"
    )
    if not warehouse:
        frappe.throw("원료창고가 없습니다. 먼저 demo_seed.run 을 실행하세요.")

    batches = [
        {"id": "FEFO-TEST-A", "expiry": "2026-06-01", "qty": 10},
        {"id": "FEFO-TEST-B", "expiry": "2026-12-31", "qty": 10},
    ]

    for b in batches:
        # Batch 문서 생성 (없으면)
        if not frappe.db.exists("Batch", b["id"]):
            frappe.get_doc({
                "doctype": "Batch",
                "batch_id": b["id"],
                "item": "RM-APPLE-CONC",
                "expiry_date": b["expiry"],
            }).insert(ignore_permissions=True)

        # 이미 재고가 있으면 skip
        existing = frappe.db.sql(
            "SELECT SUM(actual_qty) FROM `tabStock Ledger Entry` "
            "WHERE item_code='RM-APPLE-CONC' AND batch_no=%s AND warehouse=%s",
            (b["id"], warehouse),
        )
        if existing and existing[0][0] and existing[0][0] > 0:
            print(f"  → {b['id']} 재고 이미 존재, skip")
            continue

        se = frappe.get_doc({
            "doctype": "Stock Entry",
            "stock_entry_type": "Material Receipt",
            "company": COMPANY,
            "items": [{
                "item_code": "RM-APPLE-CONC",
                "qty": b["qty"],
                "uom": "L",
                "stock_uom": "L",
                "t_warehouse": warehouse,
                "batch_no": b["id"],
                "use_serial_batch_fields": 1,
                "basic_rate": 1000,
            }],
        })
        se.insert(ignore_permissions=True)
        se.submit()
        print(f"  → 입고 완료: {b['id']} (만료: {b['expiry']}) {b['qty']}L → {warehouse}")

    frappe.db.commit()
    print("✅ FEFO 테스트 재고 준비 완료.")
    print("   이제 Stock Entry: Material Issue 에서 FEFO-TEST-B (늦은 만료일)를 선택해보세요.")


def test_fefo():
    """
    FEFO 경고 로직을 터미널에서 직접 검증한다.
    FEFO-TEST-B(늦은 만료일)를 선택했을 때 FEFO-TEST-A(빠른 만료일)가 감지되는지 확인.

    실행법:
      bench --site <site> execute food_mes_kr.food_mes_kr.demo_seed.test_fefo
    """
    global COMPANY
    COMPANY = frappe.db.get_value("Company", {}, "name")

    print("▶ FEFO 검증 시작")

    # 테스트 재고가 없으면 자동 생성
    create_fefo_test_stock()

    warehouse = frappe.db.get_value(
        "Warehouse", {"warehouse_name": "원료창고", "company": COMPANY}, "name"
    )

    selected_batch = "FEFO-TEST-B"
    selected_expiry = frappe.db.get_value("Batch", selected_batch, "expiry_date")

    print(f"\n  선택 배치 : {selected_batch} (만료: {selected_expiry})")
    print(f"  창고       : {warehouse}")

    # FEFO 핵심 쿼리 — ERPNext v15 Serial and Batch Bundle 기준
    earlier = frappe.db.sql(
        """
        SELECT b.name, b.expiry_date, SUM(sbe.qty) AS qty
          FROM `tabBatch` b
          JOIN `tabSerial and Batch Entry` sbe ON sbe.batch_no = b.name
          JOIN `tabSerial and Batch Bundle` sbb ON sbe.parent  = sbb.name
         WHERE sbb.item_code = 'RM-APPLE-CONC'
           AND sbb.warehouse = %(warehouse)s
           AND sbb.docstatus = 1
           AND b.expiry_date < %(expiry)s
           AND b.disabled    = 0
         GROUP BY b.name
        HAVING qty > 0
        """,
        {"warehouse": warehouse, "expiry": selected_expiry},
        as_dict=True,
    )

    if earlier:
        print("\n✅ FEFO 경고 조건 충족! 훅이 정상 동작합니다.")
        for b in earlier:
            print(f"   더 빠른 배치: {b.name}  만료: {b.expiry_date}  잔량: {b.qty} L")
    else:
        print("\n❌ FEFO 경고 조건 미충족 — FEFO-TEST-A 재고가 없거나 이미 소진됨")


def create_trace_demo():
    """
    역추적(Backward Trace) 시연용 데이터 생성.

    실행하면:
    1. 원료(사과농축액 FEFO-TEST-A, 비타민C) 입고
    2. 헬로아이 사과주스 Work Order Submit
    3. 원료 → WIP 이송 (Material Transfer for Manufacture)
    4. 생산 완료 (Manufacture) → 완제품 LOT 배치 자동 생성

    실행:
      bench --site dev.localhost execute food_mes_kr.food_mes_kr.demo_seed.create_trace_demo
    """
    global COMPANY
    COMPANY = frappe.db.get_value("Company", {"abbr": "GFD"}, "name") or \
              frappe.db.get_value("Company", {}, "name")

    def wh(name):
        return frappe.db.get_value("Warehouse", {"warehouse_name": name, "company": COMPANY}, "name")

    raw_wh  = wh("원료창고")
    wip_wh  = wh("WIP")
    fg_wh   = wh("완제품창고")
    scrap_wh = wh("스크랩")

    if not raw_wh:
        frappe.throw("원료창고를 찾을 수 없습니다. demo_seed.run 을 먼저 실행하세요.")

    print("▶ 역추적 시연 데이터 생성 시작")

    # ── 1. 원료 사전 입고 (없으면 생성) ──────────────────────────
    # 배치 추적 원료
    trace_batches = [
        {"item": "RM-APPLE-CONC", "batch_id": "TRACE-APPLE-001",
         "expiry": "2027-03-31", "qty": 20, "uom": "L", "rate": 5000},
        {"item": "RM-VITC",       "batch_id": "TRACE-VITC-001",
         "expiry": "2028-01-01", "qty": 5,  "uom": "kg", "rate": 5000},
    ]
    for b in trace_batches:
        if not frappe.db.exists("Batch", b["batch_id"]):
            frappe.get_doc({
                "doctype": "Batch",
                "batch_id": b["batch_id"],
                "item": b["item"],
                "expiry_date": b["expiry"],
            }).insert(ignore_permissions=True)

        existing_qty = frappe.db.sql(
            "SELECT SUM(actual_qty) FROM `tabStock Ledger Entry` "
            "WHERE item_code=%s AND batch_no=%s AND warehouse=%s AND is_cancelled=0",
            (b["item"], b["batch_id"], raw_wh)
        )
        if existing_qty and existing_qty[0][0] and existing_qty[0][0] > 0:
            print(f"  → {b['batch_id']} 재고 이미 있음, skip")
            continue

        se = frappe.get_doc({
            "doctype": "Stock Entry",
            "stock_entry_type": "Material Receipt",
            "company": COMPANY,
            "items": [{
                "item_code": b["item"],
                "qty": b["qty"],
                "uom": b["uom"],
                "stock_uom": b["uom"],
                "t_warehouse": raw_wh,
                "batch_no": b["batch_id"],
                "use_serial_batch_fields": 1,
                "basic_rate": b["rate"],
            }],
        })
        se.insert(ignore_permissions=True)
        se.submit()
        print(f"  → 입고: {b['batch_id']} {b['qty']}{b['uom']}")

    # 비배치 원료 (BOM 구성 원료이므로 단가 이력과 충분한 재고 필요)
    # min_qty 이상 없으면 target_qty 만큼 추가 입고
    non_batch_items = [
        {"item": "RM-WATER",      "min_qty": 50,   "target_qty": 200,  "uom": "L",     "rate": 100},
        {"item": "RM-POUCH-80ML", "min_qty": 500,  "target_qty": 2000, "uom": "Pouch", "rate": 50},
    ]
    for nb in non_batch_items:
        existing_qty = frappe.db.sql(
            "SELECT COALESCE(SUM(actual_qty), 0) FROM `tabStock Ledger Entry` "
            "WHERE item_code=%s AND warehouse=%s AND is_cancelled=0",
            (nb["item"], raw_wh)
        )
        current = existing_qty[0][0] if existing_qty else 0
        if current >= nb["min_qty"]:
            print(f"  → {nb['item']} 재고 충분({current:.1f}), skip")
            continue

        se = frappe.get_doc({
            "doctype": "Stock Entry",
            "stock_entry_type": "Material Receipt",
            "company": COMPANY,
            "items": [{
                "item_code": nb["item"],
                "qty": nb["target_qty"],
                "uom": nb["uom"],
                "stock_uom": nb["uom"],
                "t_warehouse": raw_wh,
                "basic_rate": nb["rate"],
            }],
        })
        se.insert(ignore_permissions=True)
        se.submit()
        print(f"  → 입고: {nb['item']} {nb['target_qty']}{nb['uom']}")

    # tabBin valuation_rate 가 transfer 검증 전에 DB에 반영되도록 커밋
    frappe.db.commit()

    # ── 2. Work Order 확보 (qty ≤ 200인 Draft 재사용 또는 신규) ──────────
    # 대형 WO를 재사용하면 원료 재고 부족이 발생하므로 소형(≤200) WO만 사용
    wo_name = frappe.db.get_value(
        "Work Order",
        {"production_item": "FG-HELLO-APPLE", "docstatus": 0, "qty": ["<=", 200]},
        "name"
    )
    if not wo_name:
        bom = frappe.db.get_value("BOM", {"item": "FG-HELLO-APPLE", "is_default": 1}, "name")
        workstation = frappe.db.get_value("Workstation", {"workstation_name": "파우치 라인 #1"}, "name")
        wo_doc = frappe.get_doc({
            "doctype": "Work Order",
            "production_item": "FG-HELLO-APPLE",
            "bom_no": bom,
            "qty": 100,
            "company": COMPANY,
            "wip_warehouse": wip_wh,
            "fg_warehouse": fg_wh,
            "scrap_warehouse": scrap_wh,
            "planned_start_date": frappe.utils.today(),
        })
        if frappe.db.exists("Custom Field", {"dt": "Work Order", "fieldname": "production_line"}):
            wo_doc.production_line = workstation
        wo_doc.insert(ignore_permissions=True)
        wo_name = wo_doc.name
        print(f"  → Work Order 생성: {wo_name}")
    else:
        print(f"  → 기존 Work Order 사용: {wo_name}")

    wo_doc = frappe.get_doc("Work Order", wo_name)
    lot_no = wo_doc.get("production_lot_no") or "TRACE-LOT"

    # Submit WO
    if wo_doc.docstatus == 0:
        wo_doc.submit()
        wo_doc.reload()
        print(f"  → WO Submit 완료, LOT: {wo_doc.get('production_lot_no')}")

    # ── 3. Material Transfer for Manufacture ──────────────────────
    existing_transfer = frappe.db.get_value(
        "Stock Entry",
        {"work_order": wo_name, "purpose": "Material Transfer for Manufacture", "docstatus": 1},
        "name"
    )
    if not existing_transfer:
        from erpnext.manufacturing.doctype.work_order.work_order import make_stock_entry
        transfer_se = frappe.get_doc(make_stock_entry(wo_name, "Material Transfer for Manufacture", wo_doc.qty))

        # 원료 배치 직접 지정 + s_warehouse 누락 시 보완
        batch_map = {
            "RM-APPLE-CONC": "TRACE-APPLE-001",
            "RM-VITC":       "TRACE-VITC-001",
        }
        for row in transfer_se.items:
            row.s_warehouse = raw_wh  # 시연 재고는 모두 raw_wh에 입고됨
            if row.item_code in batch_map:
                row.batch_no = batch_map[row.item_code]
                row.use_serial_batch_fields = 1

        transfer_se.insert(ignore_permissions=True)
        transfer_se.submit()
        print(f"  → Material Transfer 완료: {transfer_se.name}")

    # ── 4. Manufacture (생산 완료) ────────────────────────────────
    existing_mfg = frappe.db.get_value(
        "Stock Entry",
        {"work_order": wo_name, "purpose": "Manufacture", "docstatus": 1},
        "name"
    )
    if not existing_mfg:
        from erpnext.manufacturing.doctype.work_order.work_order import make_stock_entry
        mfg_se = frappe.get_doc(make_stock_entry(wo_name, "Manufacture", wo_doc.qty))
        mfg_se.insert(ignore_permissions=True)
        mfg_se.submit()
        print(f"  → Manufacture 완료: {mfg_se.name}")

        # 생성된 완제품 Batch 확인
        fg_batch = frappe.db.get_value(
            "Batch", {"item": "FG-HELLO-APPLE", "reference_name": mfg_se.name}, "name"
        ) or frappe.db.get_value(
            "Stock Ledger Entry",
            {"voucher_no": mfg_se.name, "actual_qty": [">", 0], "item_code": "FG-HELLO-APPLE"},
            "batch_no"
        )
        print(f"  → 완제품 Batch(LOT) 생성: {fg_batch}")
    else:
        fg_batch = frappe.db.get_value(
            "Stock Ledger Entry",
            {"voucher_no": existing_mfg, "actual_qty": [">", 0], "item_code": "FG-HELLO-APPLE"},
            "batch_no"
        )
        print(f"  → 기존 Manufacture 사용: {existing_mfg}")

    frappe.db.commit()
    print("\n✅ 역추적 시연 데이터 준비 완료!")
    print(f"   Backward Trace 보고서에서 완제품 LOT을 입력하세요: {fg_batch}")
    print(f"   확인할 원료 배치: TRACE-APPLE-001 (사과농축액), TRACE-VITC-001 (비타민C)")


def setup_trace_suppliers():
    """
    역추적 시연용 원료 배치에 공급업자를 등록한다.

    - 사과농축액 배치 (TRACE-APPLE-001, Batch-A) → 청과원농산(주)
    - 비타민C 배치 (TRACE-VITC-001)              → 대한뉴트리(주)

    실행:
      bench --site dev.localhost execute food_mes_kr.food_mes_kr.demo_seed.setup_trace_suppliers
    """
    SUPPLIER_SPECS = [
        {
            "supplier_name": "청과원농산(주)",
            "batches": ["TRACE-APPLE-001", "Batch-A"],
        },
        {
            "supplier_name": "대한뉴트리(주)",
            "batches": ["TRACE-VITC-001"],
        },
    ]

    for spec in SUPPLIER_SPECS:
        sname = spec["supplier_name"]
        if not frappe.db.exists("Supplier", sname):
            frappe.get_doc({
                "doctype": "Supplier",
                "supplier_name": sname,
                "supplier_group": "Raw Material",
                "country": "Korea, Republic of",
            }).insert(ignore_permissions=True)
            print(f"  → Supplier 생성: {sname}")
        else:
            print(f"  → Supplier 이미 존재: {sname}")

        for batch_id in spec["batches"]:
            if frappe.db.exists("Batch", batch_id):
                frappe.db.set_value("Batch", batch_id, "supplier", sname)
                print(f"     Batch {batch_id} supplier = {sname}")
            else:
                print(f"     Batch {batch_id} 없음, skip")

    frappe.db.commit()
    print("✅ 공급업자 등록 완료.")


def bootstrap_site():
    """
    브라우저 설정 마법사 없이 사이트를 초기화한다.
    Docker setup.sh 에서 자동으로 호출되며, 수동 실행도 가능하다.

    이미 회사가 있으면 아무것도 하지 않는다.
    """
    if frappe.db.get_value("Company", {}, "name"):
        print("✓ 회사가 이미 존재합니다. bootstrap 건너뜀.")
        return

    from frappe.desk.page.setup_wizard.setup_wizard import setup_complete

    print("▶ ERPNext 초기화 중 (회사·계정과목·회계연도 생성)...")

    setup_complete(frappe._dict({
        "language": "en",
        "country": "Korea, Republic of",
        "timezone": "Asia/Seoul",
        "currency": "KRW",
        "company_name": "Good F&B (Demo)",
        "company_abbr": "GFD",
        "chart_of_accounts": "Standard",
        "fy_start_date": "2026-01-01",
        "fy_end_date": "2026-12-31",
        "setup_complete": "Yes",
    }))

    frappe.db.commit()
    print("✅ Bootstrap 완료: Good F&B (Demo) 회사가 생성되었습니다.")
