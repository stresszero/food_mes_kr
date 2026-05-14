"""
food_mes_kr/food_mes_kr/server_scripts/batch_naming.py

ERPNext Stock Entry: Manufacture가 완제품 Batch를 자동 생성할 때,
Batch.batch_id를 Work Order의 production_lot_no로 강제 적용한다.

이렇게 해야 한국식 LOT 번호 (251207-L1-001) 가 그대로 Batch 식별자로 살아남고,
나중에 출하·라벨·트레이서빌리티에 일관되게 사용된다.

ERPNext 기본 동작:
- Item.create_new_batch=1, Item.batch_number_series 가 설정되어 있으면 그 시리즈로 자동 생성.
- 본 훅은 이 자동 생성을 가로채서 우리 LOT 번호로 덮어쓴다.
"""

import frappe
from frappe import _


def apply_work_order_lot_to_batch(doc, method=None):
    """
    Batch before_insert hook.

    Batch가 어떤 Stock Entry: Manufacture에서 만들어졌는지 추적해서,
    그 Manufacture가 가리키는 Work Order의 production_lot_no를 가져온다.
    """
    if doc.batch_id and not _looks_auto_generated(doc.batch_id):
        # 사용자가 명시적으로 batch_id를 입력했음 → 존중
        return

    work_order_name = _find_origin_work_order(doc)
    if not work_order_name:
        return

    if not _has_custom_field("Work Order", "production_lot_no"):
        return

    lot_no = frappe.db.get_value("Work Order", work_order_name, "production_lot_no")
    if not lot_no:
        return

    # 같은 batch_id가 이미 존재하면 충돌 → 접미사 추가
    final_id = _ensure_unique(lot_no)
    doc.batch_id = final_id

    # 추가 정보도 채움 (Batch 자체 필드)
    if not doc.manufacturing_date:
        mfg = frappe.db.get_value("Work Order", work_order_name, "mfg_date")
        if mfg:
            doc.manufacturing_date = mfg

    # expiry_date 는 Batch.before_save 에서 Item.shelf_life 기준으로 자동 계산됨
    # (ERPNext 기본 동작) - 우리가 손댈 필요 없음.


# ────────────────────────────────────────────────────────────
#   Helpers
# ────────────────────────────────────────────────────────────

def _find_origin_work_order(batch_doc) -> str | None:
    """
    Batch가 만들어진 출처가 Stock Entry: Manufacture 인지 확인하고,
    그 Stock Entry의 work_order 필드 반환.
    """
    if batch_doc.reference_doctype != "Stock Entry":
        return None

    if not batch_doc.reference_name:
        return None

    se_data = frappe.db.get_value(
        "Stock Entry",
        batch_doc.reference_name,
        ["purpose", "work_order"],
        as_dict=True,
    )
    if not se_data:
        return None

    if se_data.purpose != "Manufacture":
        return None

    return se_data.work_order


def _looks_auto_generated(batch_id: str) -> bool:
    """
    Frappe가 naming series로 자동 생성한 ID는 보통 'BATCH-' 같은 prefix.
    수동 입력처럼 보이면 우리가 덮어쓰지 않음.
    """
    if not batch_id:
        return True
    auto_prefixes = ("BATCH-", "BTH-", "MFG-BATCH-")
    return any(batch_id.upper().startswith(p) for p in auto_prefixes)


def _ensure_unique(lot_no: str) -> str:
    """
    같은 batch_id가 이미 존재하면 -A, -B... 접미사 추가.
    드물게 한 WO에 여러 partial 생산이 발생해 Batch가 두 번 만들어지는 경우 대비.
    """
    if not frappe.db.exists("Batch", lot_no):
        return lot_no

    for suffix in "ABCDEFGHIJKLMNOPQRSTUVWXYZ":
        candidate = f"{lot_no}-{suffix}"
        if not frappe.db.exists("Batch", candidate):
            return candidate

    # 26번 충돌은 사실상 발생 불가지만 안전장치
    frappe.throw(_("LOT 번호 충돌이 너무 많습니다: {0}").format(lot_no))


def _has_custom_field(doctype: str, fieldname: str) -> bool:
    return bool(frappe.db.exists("Custom Field", {"dt": doctype, "fieldname": fieldname}))
