"""
food_mes_kr/food_mes_kr/report/forward_trace/forward_trace.py

Forward Trace (정방향 추적):
  입력 LOT (예: 사과농축액 LOT FRX-2025-1102) 이 어떤 완제품 LOT으로 들어갔는지를 추적.

식약처 회수 대응 시나리오:
  "이 원료에 문제가 있다. 이걸 쓴 모든 완제품을 30초 안에 찾아라."

알고리즘:
  Stock Ledger Entry (SLE)와 Stock Entry (SE) 를 조인하여 '같은 Manufacture Stock Entry에서
  소비된 LOT(음수 SLE)와 생산된 LOT(양수 SLE)는 부모-자식 관계'라는 사실을 이용해
  재귀 CTE로 자손 LOT 트리를 펼친다.

  reproduction_lot ─consumed_in→ Stock Entry: Manufacture ─produced→ child_lot
  child_lot         ─consumed_in→ ...                      ─produced→ grandchild_lot
  ...

  중간 반제품(Sub-assembly)이 있을 때도 다단으로 따라간다.

DB 호환성:
  MariaDB 10.6+ / MySQL 8.0+ / PostgreSQL 모두 지원하는 표준 재귀 CTE 사용.
"""

import frappe
from frappe import _


def execute(filters=None):
    filters = filters or {}

    if not filters.get("source_batch"):
        frappe.throw(_("추적을 시작할 LOT 번호(원료/반제품)를 입력해 주세요."))

    columns = _get_columns()
    data = _get_trace(filters)

    chart = _build_chart(data)
    summary = _build_summary(data, filters.get("source_batch"))

    return columns, data, None, chart, summary


# ────────────────────────────────────────────────────────────
#   Columns
# ────────────────────────────────────────────────────────────

def _get_columns():
    return [
        {
            "label": _("Depth"),
            "fieldname": "depth",
            "fieldtype": "Int",
            "width": 70,
        },
        {
            "label": _("Produced LOT"),
            "fieldname": "produced_lot",
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
        {
            "label": _("Item Name"),
            "fieldname": "item_name",
            "fieldtype": "Data",
            "width": 220,
        },
        {
            "label": _("Mfg Date"),
            "fieldname": "manufacturing_date",
            "fieldtype": "Date",
            "width": 100,
        },
        {
            "label": _("Expiry Date"),
            "fieldname": "expiry_date",
            "fieldtype": "Date",
            "width": 100,
        },
        {
            "label": _("Qty"),
            "fieldname": "produced_qty",
            "fieldtype": "Float",
            "width": 100,
        },
        {
            "label": _("Work Order"),
            "fieldname": "work_order",
            "fieldtype": "Link",
            "options": "Work Order",
            "width": 150,
        },
        {
            "label": _("Stock Entry"),
            "fieldname": "stock_entry",
            "fieldtype": "Link",
            "options": "Stock Entry",
            "width": 150,
        },
        {
            "label": _("FG Warehouse"),
            "fieldname": "warehouse",
            "fieldtype": "Link",
            "options": "Warehouse",
            "width": 150,
        },
        {
            "label": _("Delivered To"),
            "fieldname": "delivered_to",
            "fieldtype": "Data",
            "width": 220,
        },
    ]


# ────────────────────────────────────────────────────────────
#   재귀 CTE 본체
# ────────────────────────────────────────────────────────────

def _get_trace(filters):
    """
    재귀 CTE — ERPNext v15 Serial and Batch Bundle 방식 기준.

    v15에서 SLE.batch_no 는 항상 NULL.
    배치 정보는 SLE.serial_and_batch_bundle → tabSerial and Batch Bundle
    → tabSerial and Batch Entry 에 저장된다.
    """
    max_depth = int(filters.get("max_depth") or 6)
    source_batch = filters["source_batch"]

    rows = frappe.db.sql(
        f"""
        WITH RECURSIVE batch_lineage (
            source_batch, current_batch, depth, work_order, stock_entry, produced_qty
        ) AS (
            -- 시작점: 입력받은 LOT (depth 0)
            SELECT
                CAST(%(source_batch)s AS CHAR(200))  AS source_batch,
                CAST(%(source_batch)s AS CHAR(200))  AS current_batch,
                0                                    AS depth,
                CAST(NULL AS CHAR(140))              AS work_order,
                CAST(NULL AS CHAR(140))              AS stock_entry,
                CAST(0 AS DECIMAL(21,9))             AS produced_qty

            UNION ALL

            -- 재귀: current_batch 가 소비된 Manufacture 의 산출 LOT을 자식으로 연결
            SELECT
                bl.source_batch,
                sbe_produce.batch_no    AS current_batch,
                bl.depth + 1            AS depth,
                consume_se.work_order   AS work_order,
                consume_se.name         AS stock_entry,
                sbe_produce.qty         AS produced_qty
            FROM batch_lineage bl

            -- 1) current_batch 가 소비된 Serial and Batch Entry 찾기
            JOIN `tabSerial and Batch Entry` sbe_consume
                ON  sbe_consume.batch_no = bl.current_batch
                AND sbe_consume.qty < 0

            -- 2) 해당 Bundle 이 submitted 인 것
            JOIN `tabSerial and Batch Bundle` sbb_consume
                ON  sbb_consume.name = sbe_consume.parent
                AND sbb_consume.docstatus = 1

            -- 3) Bundle 을 참조하는 consume SLE (actual_qty < 0)
            JOIN `tabStock Ledger Entry` sle_consume
                ON  sle_consume.serial_and_batch_bundle = sbb_consume.name
                AND sle_consume.actual_qty < 0
                AND sle_consume.is_cancelled = 0

            -- 4) 해당 SLE 의 Stock Entry 가 Manufacture
            JOIN `tabStock Entry` consume_se
                ON  consume_se.name = sle_consume.voucher_no
                AND consume_se.docstatus = 1
                AND consume_se.purpose = 'Manufacture'

            -- 5) 같은 SE 에서 산출된(actual_qty > 0) SLE 찾기
            JOIN `tabStock Ledger Entry` sle_produce
                ON  sle_produce.voucher_no = consume_se.name
                AND sle_produce.actual_qty > 0
                AND sle_produce.serial_and_batch_bundle IS NOT NULL
                AND sle_produce.is_cancelled = 0

            -- 6) 산출 Bundle 의 배치 항목
            JOIN `tabSerial and Batch Bundle` sbb_produce
                ON  sbb_produce.name = sle_produce.serial_and_batch_bundle

            JOIN `tabSerial and Batch Entry` sbe_produce
                ON  sbe_produce.parent = sbb_produce.name
                AND sbe_produce.qty > 0

            WHERE bl.depth < {max_depth}
        )
        SELECT
            bl.depth,
            bl.current_batch    AS produced_lot,
            b.item              AS item_code,
            b.item_name         AS item_name,
            b.manufacturing_date,
            b.expiry_date,
            bl.produced_qty     AS produced_qty,
            bl.work_order,
            bl.stock_entry,
            -- 산출 SLE 의 창고
            (SELECT sle2.warehouse
               FROM `tabStock Ledger Entry` sle2
               JOIN `tabSerial and Batch Bundle` sbb2
                    ON  sbb2.name = sle2.serial_and_batch_bundle
               JOIN `tabSerial and Batch Entry` sbe2
                    ON  sbe2.parent = sbb2.name
                    AND sbe2.batch_no = bl.current_batch
              WHERE sle2.voucher_no = bl.stock_entry
                AND sle2.actual_qty > 0
              LIMIT 1) AS warehouse
        FROM batch_lineage bl
        LEFT JOIN `tabBatch` b ON b.name = bl.current_batch
        WHERE bl.depth > 0
        ORDER BY bl.depth, bl.current_batch
        """,
        {"source_batch": source_batch},
        as_dict=True,
    )

    # 출하처 정보 보강 (Delivery Note 까지 따라가기)
    for row in rows:
        row["delivered_to"] = _find_delivery_destinations(row["produced_lot"])

    return rows


def _find_delivery_destinations(batch_no: str) -> str:
    """
    해당 LOT이 출하된 Delivery Note 에서 거래처(customer)와 출하일을 추출.
    여러 거래처면 줄바꿈으로 join.
    """
    rows = frappe.db.sql(
        """
        SELECT DISTINCT dn.customer_name, dn.posting_date
        FROM `tabDelivery Note Item` dni
        INNER JOIN `tabDelivery Note` dn
            ON dn.name = dni.parent
            AND dn.docstatus = 1
        WHERE dni.batch_no = %(batch)s
        ORDER BY dn.posting_date DESC
        LIMIT 5
        """,
        {"batch": batch_no},
        as_dict=True,
    )
    if not rows:
        return ""
    return "\n".join(f"{r.customer_name} ({r.posting_date})" for r in rows)


# ────────────────────────────────────────────────────────────
#   Chart & Summary
# ────────────────────────────────────────────────────────────

def _build_chart(data):
    """깊이별 LOT 개수를 막대그래프로."""
    if not data:
        return None

    depth_counts = {}
    for row in data:
        d = row["depth"]
        depth_counts[d] = depth_counts.get(d, 0) + 1

    sorted_depths = sorted(depth_counts.keys())
    return {
        "data": {
            "labels": [_("Depth {0}").format(d) for d in sorted_depths],
            "datasets": [{
                "name": _("LOTs"),
                "values": [depth_counts[d] for d in sorted_depths],
            }],
        },
        "type": "bar",
        "colors": ["#5e64ff"],
    }


def _build_summary(data, source_batch):
    """상단 요약 카드."""
    total_lots = len(data)
    affected_customers = set()
    for row in data:
        if row.get("delivered_to"):
            for line in row["delivered_to"].split("\n"):
                customer = line.split("(")[0].strip()
                if customer:
                    affected_customers.add(customer)

    return [
        {
            "label": _("Source LOT"),
            "value": source_batch,
            "datatype": "Data",
            "indicator": "blue",
        },
        {
            "label": _("Affected Finished LOTs"),
            "value": total_lots,
            "datatype": "Int",
            "indicator": "orange" if total_lots else "green",
        },
        {
            "label": _("Affected Customers"),
            "value": len(affected_customers),
            "datatype": "Int",
            "indicator": "red" if affected_customers else "green",
        },
    ]
