"""
Forward/Backward Trace 의 재귀 CTE 쿼리 알고리즘을 SQLite로 시뮬레이션하여 검증.

시나리오 (좋은F&B 같은 음료 OEM):
  사과농축액 LOT FRX-001  ─┐
                            ├→ Stock Entry SE-001 (Manufacture)  → 헬로아이 사과주스 LOT 251207-L1-001
  비타민C       LOT VITC-A ─┘                                        (1000팩)

  헬로아이 사과주스 LOT 251207-L1-001  ─┐
                                          ├→ Stock Entry SE-002 (Manufacture)  → 박스 LOT BOX-001
  박스      LOT BOX-RAW-1               ─┘                                       (50박스)

  Forward Trace ('FRX-001') → 251207-L1-001, BOX-001 (depth 1, 2)
  Backward Trace ('BOX-001') → 251207-L1-001 (depth 1), FRX-001, VITC-A, BOX-RAW-1 (depth 2)
"""

import sqlite3
import unittest


# ────────────────────────────────────────────────────────────
#   테스트 데이터 셋업
# ────────────────────────────────────────────────────────────

SCHEMA = """
CREATE TABLE `tabStock Entry` (
    name TEXT PRIMARY KEY,
    purpose TEXT,
    docstatus INTEGER,
    work_order TEXT
);

CREATE TABLE `tabStock Ledger Entry` (
    name TEXT PRIMARY KEY,
    voucher_type TEXT,
    voucher_no TEXT,
    batch_no TEXT,
    actual_qty REAL,
    is_cancelled INTEGER DEFAULT 0,
    warehouse TEXT
);

CREATE TABLE `tabBatch` (
    name TEXT PRIMARY KEY,
    item TEXT,
    item_name TEXT,
    supplier TEXT,
    manufacturing_date TEXT,
    expiry_date TEXT,
    batch_qty REAL,
    reference_doctype TEXT,
    reference_name TEXT
);
"""

SEED = """
-- Stock Entries
INSERT INTO `tabStock Entry` VALUES ('SE-001', 'Manufacture', 1, 'WO-001');
INSERT INTO `tabStock Entry` VALUES ('SE-002', 'Manufacture', 1, 'WO-002');

-- Batches
INSERT INTO `tabBatch` VALUES ('FRX-001', 'RM-APPLE-CONC', '사과농축액', '낙원농원', '2025-10-01', '2026-10-01', 0, 'Purchase Receipt', 'PR-001');
INSERT INTO `tabBatch` VALUES ('VITC-A', 'RM-VITC', '비타민C', 'DSM코리아', '2025-09-01', '2027-09-01', 0, 'Purchase Receipt', 'PR-002');
INSERT INTO `tabBatch` VALUES ('251207-L1-001', 'FG-HELLO-APPLE', '헬로아이 사과주스', NULL, '2025-12-07', '2026-09-03', 1000, 'Stock Entry', 'SE-001');
INSERT INTO `tabBatch` VALUES ('BOX-RAW-1', 'PKG-BOX', '20입 박스 원지', '한솔포장', '2025-11-01', '2030-11-01', 0, 'Purchase Receipt', 'PR-003');
INSERT INTO `tabBatch` VALUES ('BOX-001', 'FG-HELLO-APPLE-BOX', '헬로아이 사과주스 20입 박스', NULL, '2025-12-07', '2026-09-03', 50, 'Stock Entry', 'SE-002');

-- SE-001 (사과농축액 + 비타민C → 헬로아이 사과주스)
INSERT INTO `tabStock Ledger Entry` VALUES ('SLE-1', 'Stock Entry', 'SE-001', 'FRX-001', -12.0, 0, '원료창고');
INSERT INTO `tabStock Ledger Entry` VALUES ('SLE-2', 'Stock Entry', 'SE-001', 'VITC-A', -0.05, 0, '원료창고');
INSERT INTO `tabStock Ledger Entry` VALUES ('SLE-3', 'Stock Entry', 'SE-001', '251207-L1-001', 1000.0, 0, '완제품창고');

-- SE-002 (헬로아이 사과주스 1000팩 + 박스원지 → 박스완제품 50박스)
INSERT INTO `tabStock Ledger Entry` VALUES ('SLE-4', 'Stock Entry', 'SE-002', '251207-L1-001', -1000.0, 0, '완제품창고');
INSERT INTO `tabStock Ledger Entry` VALUES ('SLE-5', 'Stock Entry', 'SE-002', 'BOX-RAW-1', -50.0, 0, '원료창고');
INSERT INTO `tabStock Ledger Entry` VALUES ('SLE-6', 'Stock Entry', 'SE-002', 'BOX-001', 50.0, 0, '완제품창고');
"""


# 실제 production 쿼리에서 frappe-specific 부분 제외
FORWARD_SQL = """
WITH RECURSIVE batch_lineage (source_batch, current_batch, depth, work_order, stock_entry) AS (
    SELECT
        :source_batch AS source_batch,
        :source_batch AS current_batch,
        0 AS depth,
        NULL AS work_order,
        NULL AS stock_entry

    UNION ALL

    SELECT
        bl.source_batch,
        produce_sle.batch_no AS current_batch,
        bl.depth + 1,
        consume_se.work_order,
        consume_se.name AS stock_entry
    FROM batch_lineage bl
    INNER JOIN `tabStock Ledger Entry` consume_sle
        ON consume_sle.batch_no = bl.current_batch
        AND consume_sle.actual_qty < 0
        AND consume_sle.voucher_type = 'Stock Entry'
        AND consume_sle.is_cancelled = 0
    INNER JOIN `tabStock Entry` consume_se
        ON consume_se.name = consume_sle.voucher_no
        AND consume_se.docstatus = 1
        AND consume_se.purpose = 'Manufacture'
    INNER JOIN `tabStock Ledger Entry` produce_sle
        ON produce_sle.voucher_no = consume_se.name
        AND produce_sle.actual_qty > 0
        AND produce_sle.batch_no IS NOT NULL
        AND produce_sle.is_cancelled = 0
    WHERE bl.depth < 6
)
SELECT
    bl.depth,
    bl.current_batch    AS produced_lot,
    b.item              AS item_code,
    b.item_name         AS item_name,
    b.batch_qty         AS produced_qty,
    bl.work_order,
    bl.stock_entry
FROM batch_lineage bl
LEFT JOIN `tabBatch` b ON b.name = bl.current_batch
WHERE bl.depth > 0
ORDER BY bl.depth, bl.current_batch;
"""

BACKWARD_SQL = """
WITH RECURSIVE upstream (target_batch, current_batch, depth, stock_entry, consumed_qty) AS (
    SELECT
        :finished_batch AS target_batch,
        :finished_batch AS current_batch,
        0 AS depth,
        NULL AS stock_entry,
        0 AS consumed_qty

    UNION ALL

    SELECT
        u.target_batch,
        consume_sle.batch_no AS current_batch,
        u.depth + 1,
        produce_se.name AS stock_entry,
        ABS(consume_sle.actual_qty) AS consumed_qty
    FROM upstream u
    INNER JOIN `tabStock Ledger Entry` produce_sle
        ON produce_sle.batch_no = u.current_batch
        AND produce_sle.actual_qty > 0
        AND produce_sle.voucher_type = 'Stock Entry'
        AND produce_sle.is_cancelled = 0
    INNER JOIN `tabStock Entry` produce_se
        ON produce_se.name = produce_sle.voucher_no
        AND produce_se.docstatus = 1
        AND produce_se.purpose = 'Manufacture'
    INNER JOIN `tabStock Ledger Entry` consume_sle
        ON consume_sle.voucher_no = produce_se.name
        AND consume_sle.actual_qty < 0
        AND consume_sle.batch_no IS NOT NULL
        AND consume_sle.is_cancelled = 0
    WHERE u.depth < 6
)
SELECT
    u.depth,
    u.current_batch    AS material_lot,
    b.item             AS item_code,
    b.item_name        AS item_name,
    b.supplier         AS supplier,
    u.consumed_qty
FROM upstream u
LEFT JOIN `tabBatch` b ON b.name = u.current_batch
WHERE u.depth > 0
ORDER BY u.depth, u.current_batch;
"""


class TestTraceQueries(unittest.TestCase):
    def setUp(self):
        self.conn = sqlite3.connect(":memory:")
        self.conn.row_factory = sqlite3.Row
        self.conn.executescript(SCHEMA)
        self.conn.executescript(SEED)

    def tearDown(self):
        self.conn.close()

    def test_forward_from_apple_concentrate(self):
        """사과농축액 FRX-001 → 헬로아이 사과주스 251207-L1-001 (depth 1) → 박스 BOX-001 (depth 2)"""
        cur = self.conn.execute(FORWARD_SQL, {"source_batch": "FRX-001"})
        rows = [dict(r) for r in cur.fetchall()]

        produced_lots = [r["produced_lot"] for r in rows]
        self.assertIn("251207-L1-001", produced_lots)
        self.assertIn("BOX-001", produced_lots)
        self.assertEqual(len(rows), 2)

        # depth 검증
        depths = {r["produced_lot"]: r["depth"] for r in rows}
        self.assertEqual(depths["251207-L1-001"], 1)
        self.assertEqual(depths["BOX-001"], 2)

    def test_forward_from_vitamin_c(self):
        """비타민C VITC-A 도 동일하게 박스까지 추적되어야 함."""
        cur = self.conn.execute(FORWARD_SQL, {"source_batch": "VITC-A"})
        rows = [dict(r) for r in cur.fetchall()]
        produced = {r["produced_lot"] for r in rows}
        self.assertEqual(produced, {"251207-L1-001", "BOX-001"})

    def test_forward_from_unrelated_batch(self):
        """관계없는 LOT 입력 시 결과 없음."""
        cur = self.conn.execute(FORWARD_SQL, {"source_batch": "DOES-NOT-EXIST"})
        rows = cur.fetchall()
        self.assertEqual(len(rows), 0)

    def test_backward_from_box(self):
        """박스 BOX-001 ← 사과주스 LOT (depth 1) ← 사과농축액·비타민C (depth 2)"""
        cur = self.conn.execute(BACKWARD_SQL, {"finished_batch": "BOX-001"})
        rows = [dict(r) for r in cur.fetchall()]
        materials = [r["material_lot"] for r in rows]

        # 직접 원료 (depth 1): 사과주스 LOT, 박스원지
        # 간접 원료 (depth 2): 사과농축액, 비타민C
        self.assertIn("251207-L1-001", materials)
        self.assertIn("BOX-RAW-1", materials)
        self.assertIn("FRX-001", materials)
        self.assertIn("VITC-A", materials)

        # depth 검증
        depths = {r["material_lot"]: r["depth"] for r in rows}
        self.assertEqual(depths["251207-L1-001"], 1)
        self.assertEqual(depths["BOX-RAW-1"], 1)
        self.assertEqual(depths["FRX-001"], 2)
        self.assertEqual(depths["VITC-A"], 2)

    def test_backward_from_intermediate(self):
        """중간 반제품 251207-L1-001 의 원료 추적: 사과농축액·비타민C 만 (박스 원지는 안 나옴)"""
        cur = self.conn.execute(BACKWARD_SQL, {"finished_batch": "251207-L1-001"})
        rows = [dict(r) for r in cur.fetchall()]
        materials = {r["material_lot"] for r in rows}
        self.assertEqual(materials, {"FRX-001", "VITC-A"})

    def test_consumed_qty_correct(self):
        """소비된 수량이 정확히 보고되는지 (역추적에서)."""
        cur = self.conn.execute(BACKWARD_SQL, {"finished_batch": "251207-L1-001"})
        rows = {r["material_lot"]: r["consumed_qty"] for r in cur.fetchall()}
        self.assertEqual(rows["FRX-001"], 12.0)   # 사과농축액 12L
        self.assertEqual(rows["VITC-A"], 0.05)    # 비타민C 50g

    def test_cancelled_sle_excluded(self):
        """is_cancelled=1 인 SLE는 추적에서 제외되어야 함."""
        # 새 시나리오: 추가로 취소된 거래 삽입
        self.conn.executescript("""
            INSERT INTO `tabStock Entry` VALUES ('SE-CANCELLED', 'Manufacture', 1, 'WO-X');
            INSERT INTO `tabBatch` VALUES ('GHOST-LOT', 'FG-X', 'Ghost', NULL, '2025-12-07', '2026-12-07', 100, 'Stock Entry', 'SE-CANCELLED');
            INSERT INTO `tabStock Ledger Entry` VALUES ('SLE-X1', 'Stock Entry', 'SE-CANCELLED', 'FRX-001', -1, 1, '원료창고');
            INSERT INTO `tabStock Ledger Entry` VALUES ('SLE-X2', 'Stock Entry', 'SE-CANCELLED', 'GHOST-LOT', 100, 1, '완제품창고');
        """)
        cur = self.conn.execute(FORWARD_SQL, {"source_batch": "FRX-001"})
        produced = {r["produced_lot"] for r in cur.fetchall()}
        self.assertNotIn("GHOST-LOT", produced)


if __name__ == "__main__":
    unittest.main(verbosity=2)
