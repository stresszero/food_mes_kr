"""
food_mes_kr/food_mes_kr/server_scripts/work_order_lot.py

Work Order 생성 시 한국식 LOT 번호(YYMMDD-LINE-SEQ)를 자동 채번한다.
이 LOT 번호는 나중에 완제품 Batch ID로 그대로 적용됨 (batch_naming.py 참조).

설계 포인트:
1. 동시성 안전: 같은 (날짜, 라인) 조합에 두 WO가 동시에 생성되어도 SEQ가 충돌하지 않도록
   FOR UPDATE 잠금 사용.
2. 멱등성: production_lot_no가 이미 세팅되어 있으면 건드리지 않음 (재시도/import 시 안전).
3. 라인 코드 추출: 우선 Custom Field `production_line`(Link Workstation) 에서 가져오고,
   없으면 Operations 테이블의 첫 workstation에서 추출. 이마저 없으면 'X'.
4. 한국 시간대(Asia/Seoul) 기준 날짜 사용. UTC 자정 직전 작업이 다음 날로 넘어가는 사고 방지.
"""

import frappe
from frappe import _
from frappe.utils import getdate, add_days, get_datetime
import datetime
import zoneinfo  # Python 3.9+

KST = zoneinfo.ZoneInfo("Asia/Seoul")


# ────────────────────────────────────────────────────────────
#   Hook Entry Points  (hooks.py 에서 등록한 함수들)
# ────────────────────────────────────────────────────────────

def assign_production_lot_no(doc, method=None):
    """
    Work Order before_insert hook.

    이미 production_lot_no가 있으면 그대로 두고, 없으면 채번한다.
    Custom Field가 없는 환경에서는 조용히 건너뛴다 (앱이 막 설치된 직후 안전장치).
    """
    if not _has_custom_field("Work Order", "production_lot_no"):
        return

    if doc.get("production_lot_no"):
        return  # 이미 있음 - 멱등성 보장

    line_code = _resolve_line_code(doc)
    base_date = _resolve_base_date(doc)

    doc.production_lot_no = _generate_lot_no(base_date, line_code)

    # 추가로 mfg_date / best_before_date 미리 계산
    if _has_custom_field("Work Order", "mfg_date"):
        doc.mfg_date = base_date

    if _has_custom_field("Work Order", "best_before_date"):
        shelf = frappe.db.get_value("Item", doc.production_item, "shelf_life_in_days")
        if shelf:
            doc.best_before_date = add_days(base_date, int(shelf))


def finalize_production_lot(doc, method=None):
    """
    Work Order before_submit hook.

    Submit 시점에 LOT가 비어있다면 다시 채번 시도. (Draft에서 수동 삭제된 경우 등)
    또한 LOT 형식 검증.
    """
    if not _has_custom_field("Work Order", "production_lot_no"):
        return

    if not doc.production_lot_no:
        # 다시 채번
        line_code = _resolve_line_code(doc)
        base_date = _resolve_base_date(doc)
        doc.production_lot_no = _generate_lot_no(base_date, line_code)

    # 형식 검증 (수동 입력 가능성 대비)
    if not _is_valid_lot_format(doc.production_lot_no):
        frappe.throw(
            _("Production LOT 번호 형식이 올바르지 않습니다: {0}. "
              "기대 형식: YYMMDD-LINE-SEQ (예: 251207-L1-001)").format(doc.production_lot_no)
        )


# ────────────────────────────────────────────────────────────
#   Core Logic
# ────────────────────────────────────────────────────────────

def _generate_lot_no(base_date: datetime.date, line_code: str) -> str:
    """
    동시성 안전한 LOT 번호 생성.

    같은 (date_prefix, line_code) 에 대해 SELECT ... FOR UPDATE 로 락을 걸어
    동시 생성되는 두 WO가 SEQ 충돌을 일으키지 않게 한다.

    트랜잭션 내에서 실행되므로 (Frappe가 doc 저장을 트랜잭션으로 감쌈),
    이 락은 트랜잭션 종료 시 자동 해제됨.
    """
    date_prefix = base_date.strftime("%y%m%d")  # YYMMDD
    prefix = f"{date_prefix}-{line_code}-"

    # 같은 prefix를 가진 가장 큰 SEQ 찾기 (FOR UPDATE로 락)
    # MariaDB/PostgreSQL 모두 동작.
    rows = frappe.db.sql(
        """
        SELECT production_lot_no
        FROM `tabWork Order`
        WHERE production_lot_no LIKE %(prefix)s
        ORDER BY production_lot_no DESC
        LIMIT 1
        FOR UPDATE
        """,
        {"prefix": f"{prefix}%"},
        as_dict=True,
    )

    next_seq = 1
    if rows:
        last_lot = rows[0].production_lot_no
        try:
            last_seq = int(last_lot.split("-")[-1])
            next_seq = last_seq + 1
        except (ValueError, IndexError):
            # 형식 깨진 데이터가 섞여있을 때 안전장치
            next_seq = 1

    return f"{prefix}{next_seq:03d}"


def _resolve_line_code(doc) -> str:
    """
    라인 코드 추출 우선순위:
    1. Custom Field `production_line` (Link → Workstation) 의 line_code
    2. Operations 테이블 첫 행의 workstation 의 line_code
    3. Workstation 이름 첫 두 글자 영숫자
    4. 'XX'  (최종 fallback)
    """
    workstation_name = None

    # 1: Custom Field
    if doc.get("production_line"):
        workstation_name = doc.production_line

    # 2: Operations
    if not workstation_name and doc.get("operations"):
        for op in doc.operations:
            if op.get("workstation"):
                workstation_name = op.workstation
                break

    if not workstation_name:
        return "XX"

    # Workstation에 line_code Custom Field가 있다면 그걸 우선
    if _has_custom_field("Workstation", "line_code"):
        line_code = frappe.db.get_value("Workstation", workstation_name, "line_code")
        if line_code:
            return _sanitize_code(line_code)

    # fallback: 워크스테이션 이름의 영숫자 첫 2~3 글자
    return _sanitize_code(workstation_name)[:3] or "XX"


def _resolve_base_date(doc) -> datetime.date:
    """
    LOT 날짜 결정:
    1. planned_start_date 있으면 → 그날
    2. 없으면 한국시간 today()
    """
    if doc.get("planned_start_date"):
        return getdate(doc.planned_start_date)
    return datetime.datetime.now(KST).date()


def _is_valid_lot_format(lot_no: str) -> bool:
    """YYMMDD-CODE-NNN 형식인지 단순 검증 (CODE는 ASCII 영숫자만 허용)."""
    if not lot_no:
        return False
    parts = lot_no.split("-")
    if len(parts) != 3:
        return False
    yymmdd, code, seq = parts
    if not (len(yymmdd) == 6 and yymmdd.isdigit()):
        return False
    if not (1 <= len(code) <= 6):
        return False
    if not all(c.isascii() and c.isalnum() for c in code):
        return False
    if not (seq.isdigit() and len(seq) >= 3):
        return False
    return True


def _sanitize_code(s: str) -> str:
    """ASCII 영숫자만 추출하여 대문자로.

    주의: Python의 str.isalnum()은 한글·일본어 등 유니코드 문자도 True를 반환하므로
    그대로 쓰면 LOT 번호에 한글이 들어가는 사고가 난다. ASCII 범위로 명시적으로 제한.
    """
    if not s:
        return ""
    return "".join(c for c in s if c.isascii() and c.isalnum()).upper()


def _has_custom_field(doctype: str, fieldname: str) -> bool:
    """
    Custom Field 존재 여부를 캐시해서 확인.
    fixtures가 아직 import되지 않은 직후에도 앱이 깨지지 않게 한다.
    """
    return bool(frappe.db.exists("Custom Field", {"dt": doctype, "fieldname": fieldname}))


# ────────────────────────────────────────────────────────────
#   Whitelisted Method (수동 재채번이 필요한 경우)
# ────────────────────────────────────────────────────────────

@frappe.whitelist()
def regenerate_lot_no(work_order: str) -> str:
    """
    관리자가 UI에서 호출 가능한 재채번 함수.
    호출 예: bench --site <site> execute food_mes_kr.food_mes_kr.server_scripts.work_order_lot.regenerate_lot_no --kwargs "{'work_order': 'MFG-WO-2025-00001'}"
    """
    doc = frappe.get_doc("Work Order", work_order)
    if doc.docstatus == 1:
        frappe.throw(_("Submitted Work Order의 LOT은 재채번할 수 없습니다."))

    line_code = _resolve_line_code(doc)
    base_date = _resolve_base_date(doc)
    new_lot = _generate_lot_no(base_date, line_code)

    doc.db_set("production_lot_no", new_lot)
    return new_lot
