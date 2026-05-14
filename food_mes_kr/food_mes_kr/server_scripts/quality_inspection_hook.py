"""
Quality Inspection on_submit 훅.

readings 중 is_ccp=1 인 파라미터가 Rejected 상태이면
Non Conformance를 자동 생성하고 알림 메시지를 표시한다.
"""

import frappe
from frappe import _
from frappe.utils import today, add_days


def auto_create_non_conformance_on_ccp_failure(doc, method=None):
    failed_ccps = _get_failed_ccp_readings(doc)
    if not failed_ccps:
        return

    nc_name = _create_non_conformance(doc, failed_ccps)
    frappe.msgprint(
        _("CCP 이탈 감지 — 부적합 보고서가 자동 생성되었습니다: <b>{0}</b>").format(nc_name),
        title=_("Non Conformance 생성"),
        indicator="red",
    )


def _get_failed_ccp_readings(doc):
    """readings 중 is_ccp=1 이고 Rejected인 specification 목록 반환."""
    ccp_specs = _get_ccp_specifications(doc.item_code)
    return [
        r.specification
        for r in doc.readings
        if r.get("status") == "Rejected" and r.specification in ccp_specs
    ]


def _get_ccp_specifications(item_code):
    """Item 직접 파라미터 또는 연결된 QI Template에서 is_ccp=1인 specification 집합 반환."""
    # 1순위: Item에 직접 등록된 파라미터
    rows = frappe.db.get_all(
        "Item Quality Inspection Parameter",
        filters={"parent": item_code, "parenttype": "Item", "is_ccp": 1},
        fields=["specification"],
    )
    if rows:
        return {r.specification for r in rows}

    # 2순위: Item에 연결된 Quality Inspection Template의 파라미터
    template = frappe.db.get_value("Item", item_code, "quality_inspection_template")
    if template:
        rows = frappe.db.get_all(
            "Item Quality Inspection Parameter",
            filters={"parent": template, "parenttype": "Quality Inspection Template", "is_ccp": 1},
            fields=["specification"],
        )
        return {r.specification for r in rows}

    return set()


def _create_non_conformance(doc, failed_ccps):
    details = (
        f"Quality Inspection <b>{doc.name}</b> 제출 시 "
        f"다음 CCP 항목 이탈 감지:<br>"
        + "<br>".join(f"&nbsp;&nbsp;• {p}" for p in failed_ccps)
    )

    nc = frappe.get_doc({
        "doctype": "Non Conformance",
        "subject": f"CCP 이탈 — {doc.item_code} ({doc.name})",
        "status": "Open",
        "details": details,
        "severity": "High",
        "due_date": add_days(today(), 7),
        "linked_quality_inspection": doc.name,
    })

    if doc.get("batch_no"):
        nc.linked_batch = doc.batch_no

    # procedure 필드가 required이지만 자동생성 문서이므로 mandatory 검증 우회
    nc.insert(ignore_permissions=True, ignore_mandatory=True)
    return nc.name
