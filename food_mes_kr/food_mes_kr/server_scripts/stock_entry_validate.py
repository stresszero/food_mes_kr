"""
FEFO(First Expired, First Out) 위반 검증.

출고성 Stock Entry 저장 시, 선택한 배치보다 유통기한이 빠른 재고가 같은 창고에
남아 있으면 오렌지 경고를 띄운다. 저장을 막지는 않으므로 작업자가 의도적으로
우선순위를 무시하는 경우에도 진행 가능하다.

ERPNext v15의 Serial and Batch Bundle 방식과 구버전 직접 입력 방식을 모두 지원.
"""

import frappe
from frappe import _

CONSUMPTION_TYPES = frozenset({
    "Material Issue",
    "Manufacture",
    "Material Transfer for Manufacture",
})


def warn_on_fefo_violation(doc, method=None):
    if doc.stock_entry_type not in CONSUMPTION_TYPES:
        return

    warnings = []

    for row in doc.items:
        if not row.get("s_warehouse"):
            continue

        for batch_no in _get_batch_nos_from_row(row):
            selected_expiry = frappe.db.get_value("Batch", batch_no, "expiry_date")
            if not selected_expiry:
                continue

            earlier = frappe.db.sql(
                """
                SELECT b.name, b.expiry_date, SUM(sbe.qty) AS qty
                  FROM `tabBatch` b
                  JOIN `tabSerial and Batch Entry` sbe ON sbe.batch_no = b.name
                  JOIN `tabSerial and Batch Bundle` sbb ON sbe.parent  = sbb.name
                 WHERE sbb.item_code = %(item)s
                   AND sbb.warehouse = %(warehouse)s
                   AND sbb.docstatus = 1
                   AND b.expiry_date < %(expiry)s
                   AND b.disabled    = 0
                 GROUP BY b.name
                HAVING qty > 0
                 LIMIT 5
                """,
                {
                    "item": row.item_code,
                    "warehouse": row.s_warehouse,
                    "expiry": selected_expiry,
                },
                as_dict=True,
            )

            if earlier:
                batch_list = ", ".join(
                    f"{b.name} (만료: {b.expiry_date})" for b in earlier
                )
                warnings.append(
                    f"<b>Row {row.idx} — {row.item_code}</b>: "
                    f"선택 배치 <b>{batch_no}</b> (만료: {selected_expiry})보다 "
                    f"유통기한이 빠른 배치가 남아 있습니다: {batch_list}"
                )

    if warnings:
        frappe.msgprint(
            "<br><br>".join(warnings),
            title=_("FEFO 위반 경고"),
            indicator="orange",
        )


def _get_batch_nos_from_row(row):
    """item row에서 배치 번호 목록을 반환한다.

    v15 Serial and Batch Bundle 방식과 구버전 batch_no 직접 입력 방식을 모두 처리.
    """
    # 구버전: batch_no 필드에 직접 입력된 경우
    if row.get("batch_no"):
        return [row.batch_no]

    # v15: serial_and_batch_bundle 링크로 저장된 경우
    bundle = row.get("serial_and_batch_bundle")
    if bundle:
        entries = frappe.db.get_all(
            "Serial and Batch Entry",
            filters={"parent": bundle},
            fields=["batch_no"],
        )
        return [e.batch_no for e in entries if e.batch_no]

    return []
