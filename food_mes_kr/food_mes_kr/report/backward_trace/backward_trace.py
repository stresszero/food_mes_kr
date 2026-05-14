"""
food_mes_kr/food_mes_kr/report/backward_trace/backward_trace.py

Backward Trace (역방향 추적):
  완제품 LOT (예: 251207-L1-001) 이 어떤 원료 LOT으로 만들어졌는지 추적.

소비자 클레임/품질 사고 시나리오:
  "헬로아이 사과주스 LOT 251207-L1-001 에서 이상한 맛이 난다."
  → 어떤 사과농축액 LOT? 어떤 공급사? 어떤 입고일자?

알고리즘:
  Forward Trace 와 거울 관계.
  Forward: consume(자식의 원료) → produce(자식)  로 내려감
  Backward: produce(자식)        → consume(부모) 로 올라감

  완제품이 만들어진 Manufacture Stock Entry 를 찾고, 그 안에서 함께 소비된
  원료 LOT 들이 부모(=원료 LOT). 부모의 부모도 같은 방식으로 따라감.
"""

import frappe
from frappe import _


def execute(filters=None):
    filters = filters or {}

    if not filters.get("finished_batch"):
        frappe.throw(_("추적할 완제품 LOT 번호를 입력해 주세요."))

    columns = _get_columns()
    data = _get_trace(filters)
    chart = _build_chart(data)
    summary = _build_summary(data, filters.get("finished_batch"))

    return columns, data, None, chart, summary


def _get_columns():
    return [
        {"label": _("Depth"), "fieldname": "depth", "fieldtype": "Int", "width": 70},
        {
            "label": _("Material LOT"),
            "fieldname": "material_lot",
            "fieldtype": "Link",
            "options": "Batch",
            "width": 200,
        },
        {
            "label": _("Item"),
            "fieldname": "item_code",
            "fieldtype": "Link",
            "options": "Item",
            "width": 150,
        },
        {"label": _("Item Name"), "fieldname": "item_name", "fieldtype": "Data", "width": 220},
        {
            "label": _("Supplier"),
            "fieldname": "supplier",
            "fieldtype": "Link",
            "options": "Supplier",
            "width": 180,
        },
        {"label": _("Mfg Date"), "fieldname": "manufacturing_date", "fieldtype": "Date", "width": 100},
        {"label": _("Expiry Date"), "fieldname": "expiry_date", "fieldtype": "Date", "width": 100},
        {"label": _("Consumed Qty"), "fieldname": "consumed_qty", "fieldtype": "Float", "width": 110},
        {
            "label": _("Used in Stock Entry"),
            "fieldname": "stock_entry",
            "fieldtype": "Link",
            "options": "Stock Entry",
            "width": 150,
        },
        {
            "label": _("Received via"),
            "fieldname": "purchase_receipt",
            "fieldtype": "Link",
            "options": "Purchase Receipt",
            "width": 150,
        },
    ]


def _get_trace(filters):
    """
    재귀 CTE — ERPNext v15 Serial and Batch Bundle 방식 기준.

    v15에서 SLE.batch_no 는 항상 NULL.
    배치 정보는 SLE.serial_and_batch_bundle → tabSerial and Batch Bundle
    → tabSerial and Batch Entry 에 저장된다.
    """
    max_depth = int(filters.get("max_depth") or 6)
    finished_batch = filters["finished_batch"]

    rows = frappe.db.sql(
        f"""
        WITH RECURSIVE upstream (
            target_batch, current_batch, depth, stock_entry, consumed_qty
        ) AS (
            -- 시작점: 완제품 LOT
            SELECT
                CAST(%(finished_batch)s AS CHAR(200))   AS target_batch,
                CAST(%(finished_batch)s AS CHAR(200))   AS current_batch,
                0                                       AS depth,
                CAST(NULL AS CHAR(140))                 AS stock_entry,
                CAST(0 AS DECIMAL(21,9))                AS consumed_qty

            UNION ALL

            -- 재귀: current_batch 가 산출된 Manufacture 에서 소비된 원료 배치 찾기
            SELECT
                u.target_batch,
                sbe_consume.batch_no        AS current_batch,
                u.depth + 1                 AS depth,
                produce_se.name             AS stock_entry,
                ABS(sbe_consume.qty)        AS consumed_qty
            FROM upstream u

            -- 1) current_batch 가 Inward 된 Serial and Batch Entry 찾기
            JOIN `tabSerial and Batch Entry` sbe_produce
                ON  sbe_produce.batch_no = u.current_batch
                AND sbe_produce.qty > 0

            -- 2) 해당 Bundle 이 submit 된 것
            JOIN `tabSerial and Batch Bundle` sbb_produce
                ON  sbb_produce.name = sbe_produce.parent
                AND sbb_produce.docstatus = 1

            -- 3) Bundle 을 참조하는 produce SLE (actual_qty > 0)
            JOIN `tabStock Ledger Entry` sle_produce
                ON  sle_produce.serial_and_batch_bundle = sbb_produce.name
                AND sle_produce.actual_qty > 0
                AND sle_produce.is_cancelled = 0

            -- 4) 해당 SLE 의 Stock Entry 가 Manufacture
            JOIN `tabStock Entry` produce_se
                ON  produce_se.name = sle_produce.voucher_no
                AND produce_se.docstatus = 1
                AND produce_se.purpose = 'Manufacture'

            -- 5) 같은 SE 에서 소비된 SLE (actual_qty < 0, 배치 있는 것만)
            JOIN `tabStock Ledger Entry` sle_consume
                ON  sle_consume.voucher_no = produce_se.name
                AND sle_consume.actual_qty < 0
                AND sle_consume.serial_and_batch_bundle IS NOT NULL
                AND sle_consume.is_cancelled = 0

            -- 6) 소비 Bundle 의 배치 항목
            JOIN `tabSerial and Batch Bundle` sbb_consume
                ON  sbb_consume.name = sle_consume.serial_and_batch_bundle

            JOIN `tabSerial and Batch Entry` sbe_consume
                ON  sbe_consume.parent = sbb_consume.name
                AND sbe_consume.qty < 0

            WHERE u.depth < {max_depth}
        )
        SELECT
            u.depth,
            u.current_batch                 AS material_lot,
            b.item                          AS item_code,
            b.item_name                     AS item_name,
            b.supplier                      AS supplier,
            b.manufacturing_date,
            b.expiry_date,
            u.consumed_qty,
            u.stock_entry,
            CASE
                WHEN b.reference_doctype = 'Purchase Receipt' THEN b.reference_name
                ELSE NULL
            END                             AS purchase_receipt
        FROM upstream u
        LEFT JOIN `tabBatch` b ON b.name = u.current_batch
        WHERE u.depth > 0
        ORDER BY u.depth, u.current_batch
        """,
        {"finished_batch": finished_batch},
        as_dict=True,
    )
    return rows


def _build_chart(data):
    if not data:
        return None
    # 공급사별 LOT 개수
    supplier_count = {}
    for r in data:
        s = r.get("supplier") or _("(no supplier)")
        supplier_count[s] = supplier_count.get(s, 0) + 1

    return {
        "data": {
            "labels": list(supplier_count.keys()),
            "datasets": [{
                "name": _("LOTs per Supplier"),
                "values": list(supplier_count.values()),
            }],
        },
        "type": "donut",
    }


def _build_summary(data, finished_batch):
    direct_materials = [r for r in data if r["depth"] == 1]
    suppliers = {r["supplier"] for r in data if r.get("supplier")}
    return [
        {
            "label": _("Finished LOT"),
            "value": finished_batch,
            "datatype": "Data",
            "indicator": "blue",
        },
        {
            "label": _("Direct Material LOTs"),
            "value": len(direct_materials),
            "datatype": "Int",
            "indicator": "orange",
        },
        {
            "label": _("Suppliers Involved"),
            "value": len(suppliers),
            "datatype": "Int",
            "indicator": "yellow",
        },
        {
            "label": _("Total LOTs in Chain"),
            "value": len(data),
            "datatype": "Int",
            "indicator": "blue",
        },
    ]
