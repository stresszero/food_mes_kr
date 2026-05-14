"""
식품 MES 시연용 바코드 등록 스크립트.

완제품(FG-): EAN-13  — 소비자 유통 제품 국제 표준 (한국 GS1 prefix 880)
원  료(RM-): CODE-128 — 산업용 물류 바코드 (자유 형식 영숫자)

실행:
  bench --site dev.localhost execute food_mes_kr.food_mes_kr.setup_barcodes.run
"""

import frappe


# ── 바코드 정의 ──────────────────────────────────────────────
#
# EAN-13 체크 digit은 아래 helper로 자동 계산.
# CODE-128 값은 스캐너가 읽어 그대로 문자열로 전달됨 (체크 digit 불필요).

ITEM_BARCODES = [
    # 완제품 — EAN-13 (GS1 한국 prefix 880)
    # 880 + 제조사코드(12345) + 제품번호(0001/0002) + check
    {"item_code": "FG-HELLO-APPLE",   "barcode_type": "EAN",      "prefix12": "880123450001"},
    {"item_code": "FG-HELLO-PEAR",    "barcode_type": "EAN",      "prefix12": "880123450002"},

    # 원료 — CODE-128
    {"item_code": "RM-APPLE-CONC",    "barcode_type": "CODE-128", "barcode": "RMAPL001"},
    {"item_code": "RM-PEAR-DORAJI",   "barcode_type": "CODE-128", "barcode": "RMPER001"},
    {"item_code": "RM-VITC",          "barcode_type": "CODE-128", "barcode": "RMVTC001"},
    {"item_code": "RM-WATER",         "barcode_type": "CODE-128", "barcode": "RMWTR001"},
    {"item_code": "RM-POUCH-80ML",    "barcode_type": "CODE-128", "barcode": "RMPCH001"},
]


def _ean13_check_digit(prefix12: str) -> str:
    """EAN-13 체크 digit 계산 (앞 12자리 → 13번째 자리 반환)."""
    digits = [int(c) for c in prefix12]
    total = sum(d * (1 if i % 2 == 0 else 3) for i, d in enumerate(digits))
    return str((10 - total % 10) % 10)


def run():
    added = []
    skipped = []

    for spec in ITEM_BARCODES:
        item_code = spec["item_code"]

        # 바코드 값 결정
        if spec["barcode_type"] == "EAN":
            barcode = spec["prefix12"] + _ean13_check_digit(spec["prefix12"])
        else:
            barcode = spec["barcode"]

        # 이미 같은 Item에 같은 바코드 있으면 skip (멱등)
        exists = frappe.db.exists(
            "Item Barcode", {"parent": item_code, "barcode": barcode}
        )
        if exists:
            skipped.append(f"  SKIP  {item_code:25s}  {barcode}")
            continue

        # Item 문서에 바코드 child row 추가
        item_doc = frappe.get_doc("Item", item_code)
        item_doc.append("barcodes", {
            "barcode": barcode,
            "barcode_type": spec["barcode_type"],
        })
        item_doc.save(ignore_permissions=True)

        added.append(f"  ADD   {item_code:25s}  {spec['barcode_type']:10s}  {barcode}")

    frappe.db.commit()

    print("\n=== 바코드 등록 결과 ===")
    for line in added:
        print(line)
    for line in skipped:
        print(line)
    print(f"\n등록: {len(added)}건 / 스킵: {len(skipped)}건")
