"""
work_order_lot.py의 순수 함수 부분을 frappe 의존 없이 단위 테스트.
실제 ERPNext 환경에서는 frappe.db 통합 테스트가 따로 필요하지만,
형식·날짜 처리 같은 순수 로직은 여기서 검증 가능.
"""
import datetime
import sys
import unittest

# work_order_lot.py 의 순수 함수만 추출 복사
def _is_valid_lot_format(lot_no):
    if not lot_no:
        return False
    parts = lot_no.split("-")
    if len(parts) != 3:
        return False
    yymmdd, code, seq = parts
    if not (len(yymmdd) == 6 and yymmdd.isdigit()):
        return False
    if not (1 <= len(code) <= 6 and code.isalnum()):
        return False
    if not (seq.isdigit() and len(seq) >= 3):
        return False
    return True

def _sanitize_code(s):
    if not s:
        return ""
    return "".join(c for c in s if c.isascii() and c.isalnum()).upper()

def _format_lot(date, line, seq):
    return f"{date.strftime('%y%m%d')}-{line}-{seq:03d}"


class TestLotFormat(unittest.TestCase):
    def test_valid_formats(self):
        cases = [
            "251207-L1-001",   # 표준
            "251207-L1-999",   # 큰 SEQ
            "251207-PKG-005",  # 라인 코드 3자
            "251207-A-001",    # 라인 코드 1자
            "251207-L1-1234",  # SEQ 4자리
        ]
        for c in cases:
            with self.subTest(c=c):
                self.assertTrue(_is_valid_lot_format(c), f"{c} should be valid")

    def test_invalid_formats(self):
        cases = [
            "",                   # 빈
            "251207-L1",          # 부분
            "abc-L1-001",         # 날짜 비숫자
            "20251207-L1-001",    # 날짜 8자리
            "251207-L_1-001",     # 라인 비영숫자
            "251207-LINE12345-001",  # 라인 7자
            "251207-L1-1",        # SEQ 1자리
            "251207-L1-AAA",      # SEQ 비숫자
        ]
        for c in cases:
            with self.subTest(c=c):
                self.assertFalse(_is_valid_lot_format(c), f"{c} should be invalid")

    def test_sanitize(self):
        self.assertEqual(_sanitize_code("Line 1"), "LINE1")
        self.assertEqual(_sanitize_code("PKG-A"), "PKGA")
        self.assertEqual(_sanitize_code("파우치-L1"), "L1")  # 한글 제거
        self.assertEqual(_sanitize_code(""), "")
        self.assertEqual(_sanitize_code(None), "")

    def test_format(self):
        d = datetime.date(2025, 12, 7)
        self.assertEqual(_format_lot(d, "L1", 1),   "251207-L1-001")
        self.assertEqual(_format_lot(d, "L1", 999), "251207-L1-999")
        d2 = datetime.date(2026, 1, 3)
        self.assertEqual(_format_lot(d2, "L2", 5),  "260103-L2-005")


class TestLotMonotonic(unittest.TestCase):
    """동시성 시나리오를 시뮬레이트: SEQ가 항상 증가하는지."""

    def test_seq_increment(self):
        """가짜 DB. 실제로는 SELECT FOR UPDATE 가 보장하지만 알고리즘 자체는 단조 증가해야."""
        existing = []
        date = datetime.date(2025, 12, 7)
        line = "L1"

        # 100건 동시에 발급 시뮬레이션
        for i in range(1, 101):
            # 가장 큰 SEQ 찾기
            max_seq = 0
            prefix = f"{date.strftime('%y%m%d')}-{line}-"
            for lot in existing:
                if lot.startswith(prefix):
                    try:
                        s = int(lot.split("-")[-1])
                        if s > max_seq:
                            max_seq = s
                    except ValueError:
                        pass
            new_lot = _format_lot(date, line, max_seq + 1)
            existing.append(new_lot)

        # 100건 모두 유일한가
        self.assertEqual(len(set(existing)), 100)
        # 마지막은 100번째
        self.assertEqual(existing[-1], "251207-L1-100")
        # 모두 형식 유효
        for lot in existing:
            self.assertTrue(_is_valid_lot_format(lot))


class TestMultiLine(unittest.TestCase):
    """라인이 다르면 SEQ가 독립."""

    def test_independent_lines(self):
        existing = ["251207-L1-001", "251207-L1-002", "251207-L2-001"]
        date = datetime.date(2025, 12, 7)

        def next_seq(line):
            prefix = f"{date.strftime('%y%m%d')}-{line}-"
            seqs = []
            for lot in existing:
                if lot.startswith(prefix):
                    seqs.append(int(lot.split("-")[-1]))
            return max(seqs) + 1 if seqs else 1

        # L1 다음은 003
        self.assertEqual(next_seq("L1"), 3)
        # L2 다음은 002
        self.assertEqual(next_seq("L2"), 2)
        # L3 처음 - 001
        self.assertEqual(next_seq("L3"), 1)


if __name__ == "__main__":
    unittest.main(verbosity=2)
