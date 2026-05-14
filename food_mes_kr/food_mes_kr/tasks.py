"""
food_mes_kr/food_mes_kr/tasks.py

scheduler_events에 등록된 정기 작업.
"""

import frappe
from frappe.utils import add_days, today


def notify_expiring_batches():
    """
    매일 1회: 유통기한이 7일 이내로 임박한 Batch를 찾아서 Quality Manager에게 알림.

    실무에서는 거래처별 잔여 유통기한 요구가 다름:
    - 대형마트: 잔여 유통기한 1/3 이상 보장 요구
    - 자사몰: 1/2 이상
    이 룰을 Custom DocType 'Customer Shelf Life Policy' 로 분리할 수 있음.
    """
    threshold_date = add_days(today(), 7)

    expiring = frappe.db.sql(
        """
        SELECT
            b.name AS batch,
            b.item,
            b.item_name,
            b.expiry_date,
            b.batch_qty
        FROM `tabBatch` b
        WHERE b.expiry_date IS NOT NULL
          AND b.expiry_date BETWEEN %(today)s AND %(threshold)s
          AND b.batch_qty > 0
        ORDER BY b.expiry_date
        """,
        {"today": today(), "threshold": threshold_date},
        as_dict=True,
    )

    if not expiring:
        return

    # 메일 본문
    rows_html = "\n".join(
        f"<tr><td>{r.batch}</td><td>{r.item_name}</td>"
        f"<td>{r.expiry_date}</td><td>{r.batch_qty}</td></tr>"
        for r in expiring
    )
    body = f"""
        <h3>유통기한 임박 LOT ({len(expiring)}건)</h3>
        <table border="1" cellpadding="6">
          <tr><th>LOT</th><th>품목</th><th>유통기한</th><th>잔량</th></tr>
          {rows_html}
        </table>
    """

    # 'Quality Manager' 역할 보유자 모두에게 발송
    recipients = frappe.db.sql_list(
        """
        SELECT DISTINCT u.name
        FROM `tabUser` u
        INNER JOIN `tabHas Role` r ON r.parent = u.name
        WHERE r.role = 'Quality Manager' AND u.enabled = 1
        """
    )

    if not recipients:
        return

    frappe.sendmail(
        recipients=recipients,
        subject=f"[ALERT] 유통기한 임박 LOT {len(expiring)}건",
        message=body,
        reference_doctype="Batch",
        reference_name=expiring[0].batch,
    )
