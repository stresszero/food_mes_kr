# Food MES 시연 가이드

**대상**: 식품 제조회사 방문 시연  
**시스템**: Good F&B (Demo) — ERPNext v15 기반 식품 MES  
**URL**: http://dev.localhost:8000  
**계정**: Administrator / admin

---

## 시연 전 준비

### 1. 서버 기동 확인

```bash
cd ~/frappe-bench
bench start
```

새 터미널에서 접속 확인:
```bash
curl -s -o /dev/null -w "%{http_code}" http://dev.localhost:8000
# 200 이면 정상
```

### 2. 시연 데이터 초기화 (최초 1회 또는 데이터가 없을 때)

```bash
# 기본 시연 데이터 (품목, 창고, BOM, 첫 작업지시서)
bench --site dev.localhost execute food_mes_kr.food_mes_kr.demo_seed.run

# FEFO 경고 테스트용 재고 (시연 #3)
bench --site dev.localhost execute food_mes_kr.food_mes_kr.demo_seed.create_fefo_test_stock

# 역추적 시연용 제조 이력 생성 (시연 #5)
bench --site dev.localhost execute food_mes_kr.food_mes_kr.demo_seed.create_trace_demo

# 원료 배치에 공급업자 등록 (시연 #5 Supplier 컬럼 표시용)
bench --site dev.localhost execute food_mes_kr.food_mes_kr.demo_seed.setup_trace_suppliers

# 바코드 등록
bench --site dev.localhost execute food_mes_kr.food_mes_kr.setup_barcodes.run
```

### 3. 바코드 이미지 준비 (시연 #1, #2)

아래 숫자를 온라인 바코드 생성기(예: barcode.tec-it.com)에서 미리 이미지로 출력하거나 모바일 화면에 띄워 준비한다.

| 품목 | 바코드 번호 | 형식 |
|------|------------|------|
| 사과농축액 (RM-APPLE-CONC) | `RMAPL001` | CODE-39 |
| 헬로아이 사과주스 80mL | `8801234500012` | EAN-13 |
| 헬로아이 배도라지 80mL | `8801234500029` | EAN-13 |

---

## 시연 #1 — 바코드 스캔 원료 입고

**한 줄 요약**: 스캐너(또는 카메라)로 바코드를 읽으면 품목이 자동 입력됩니다.  
**실무 포인트**: 수작업 오타 없이 입고 처리 속도가 3배 이상 향상됩니다.

### 순서

1. 상단 메뉴 **Stock → Stock Transactions → Purchase Receipt** 클릭  
   (또는 검색창에 "Purchase Receipt" 입력)

2. **\[+ New\]** 버튼 클릭

3. Supplier 필드에 `Demo Supplier` 입력 후 선택  
   (없으면 Items 테이블 아래 **Scan Barcode** 필드만 시연 가능)

4. 화면 하단 Items 테이블 위에 있는 **Scan Barcode** 입력란 클릭

5. 카메라 아이콘 클릭 → 카메라 팝업 등장  
   > 또는 입력란에 직접 `RMAPL001` 타이핑 후 Enter (바코드 리더기 연결 시 동일 동작)

6. 준비한 `RMAPL001` 바코드 이미지를 카메라에 인식  
   **→ 사과농축액(RM-APPLE-CONC) 행이 자동 추가됨**

7. 수량(Qty) `100`, 단가(Rate) `5000` 입력, 창고는 `원료창고 - GFD` 선택

8. **\[Save\]** → **\[Submit\]**  
   → "Purchase Receipt submitted" 메시지 확인

**체크포인트**: Stock Ledger에서 사과농축액 +100 kg 증가 확인  
> Stock → Stock Reports → Stock Balance → Item: RM-APPLE-CONC

---

## 시연 #2 — 작업지시서 생성 + LOT 자동 채번

**한 줄 요약**: 작업지시서를 저장하는 순간 오늘 날짜·라인·순번으로 LOT 번호가 자동 부여됩니다.  
**실무 포인트**: 수기 LOT 장부 없이 한국식 `YYMMDD-LINE-SEQ` 규칙이 자동 적용됩니다.

### 순서

1. **Manufacturing → Work Order → \[+ New\]**

2. 필수 항목 입력:
   | 필드 | 값 |
   |------|----|
   | Item (완제품) | `FG-HELLO-APPLE` |
   | Qty to Manufacture | `500` |
   | Company | `Good F&B (Demo)` |
   | Planned Start Date | 오늘 날짜 |
   | Production Line | `L1` |

3. **\[Save\]** 클릭  
   **→ Custom Fields 섹션의 Production LOT No 필드에 `260513-L1-001` 형식의 LOT 번호가 자동 입력됨**

4. LOT 번호를 청중에게 강조:  
   - `26` = 연도, `05` = 월, `13` = 일  
   - `L1` = 파우치 라인 #1  
   - `001` = 당일 첫 번째 생산 배치

5. **\[Submit\]** 클릭 → LOT 번호 확정

**체크포인트**: 같은 날 두 번째 WO를 저장하면 `260513-L1-002`로 순번이 자동 증가하는지 확인

> **참고**: 라인코드는 Workstation(작업장)의 `line_code` Custom Field에서 가져옵니다.

---

## 시연 #3 — FEFO 위반 경고 (선입선출 안전장치)

**한 줄 요약**: 유통기한이 더 짧은 재고가 남아있는데 나중 배치를 사용하려 하면 경고가 뜹니다.  
**실무 포인트**: FEFO(선입선출) 위반으로 인한 식품 안전 사고를 사전에 방지합니다.

### 사전 확인

```bash
# FEFO 테스트 재고 존재 확인 (FEFO-TEST-A, FEFO-TEST-B 모두 보여야 함)
bench --site dev.localhost execute "frappe.db.sql" \
  --kwargs '{"query": "SELECT batch_id, expiry_date FROM `tabBatch` WHERE batch_id LIKE \"FEFO%\"", "as_dict": 1}'
```

| 배치 | 유통기한 | 비고 |
|------|---------|------|
| FEFO-TEST-A | 2026-06-01 | **더 짧음 → 먼저 써야 함** |
| FEFO-TEST-B | 2026-12-31 | 나중 배치 |

### 순서

1. **Stock → Stock Transactions → Stock Entry → \[+ New\]**

2. Stock Entry Type: **Material Issue**

3. Items 테이블에 행 추가:
   | 필드 | 값 |
   |------|----|
   | Item Code | `RM-APPLE-CONC` (사과농축액) |
   | Source Warehouse | `원료창고 - GFD` |
   | Qty | `10` |
   | Batch No | `FEFO-TEST-B` ← 일부러 나중 배치 선택 |

4. **\[Save\]** 클릭  
   **→ 주황색 경고 메시지 등장:**  
   > "FEFO 경고: RM-APPLE-CONC 에 더 빠른 만료일 배치(FEFO-TEST-A, 만료: 2026-06-01)가 재고에 있습니다."

5. 저장은 허용되지만 경고가 기록됨 (차단이 아닌 알림 방식)

**체크포인트**: FEFO-TEST-A를 선택하면 경고가 사라지는지 확인

---

## 시연 #4 — 실시간 재고 현황 조회

**한 줄 요약**: 품목별·창고별·배치별 잔여 재고를 실시간으로 확인합니다.  
**실무 포인트**: 재고 파악을 위해 ERP를 별도 조회하거나 엑셀을 열 필요가 없습니다.

### 순서 A — 재고 잔액 보고서

1. **Stock → Stock Reports → Stock Balance**

2. 필터 설정:
   | 필터 | 값 |
   |------|----|
   | Company | `Good F&B (Demo)` |
   | Warehouse | `원료창고 - GFD` |

3. **\[Refresh\]** 클릭  
   → 원료 품목별 현재 수량·단가·총액 표시

4. 특정 품목 클릭 → Stock Ledger 드릴다운으로 이동 흐름 설명

### 순서 B — 배치별 재고 조회

1. **Stock → Stock Reports → Batch-Wise Balance History**

2. Item: `RM-APPLE-CONC`, Warehouse: `원료창고 - GFD` 입력 후 **\[Refresh\]**  
   → 배치별 잔량과 유통기한 목록 확인

**체크포인트**: FEFO-TEST-A와 FEFO-TEST-B의 유통기한과 잔량이 구분되어 표시되는지 확인

---

## 시연 #5 — 완제품 역추적 보고서 (Backward Trace)

**한 줄 요약**: 완제품 클레임 발생 시 "어느 원료 배치를 썼는가"를 수초 만에 추적합니다.  
**실무 포인트**: 수기 장부 기반 추적에 걸리던 수 시간이 5초로 단축됩니다.

### 사전 준비

이미 `create_trace_demo` 를 실행했다면 생성된 완제품 LOT 번호를 확인합니다:

```bash
bench --site dev.localhost execute "frappe.db.sql" \
  --kwargs '{"query": "SELECT batch_id, item FROM `tabBatch` WHERE item = \"FG-HELLO-APPLE\" ORDER BY creation DESC LIMIT 3", "as_dict": 1}'
```

출력 예시:
```
[{'batch_id': '260513-L1-001', 'item': 'FG-HELLO-APPLE'}]
```

### 순서

1. **Stock → Reports → Backward Trace**  
   (메뉴가 보이지 않으면 검색창에 "Backward Trace" 입력)

2. 필터:
   | 필터 | 값 |
   |------|----|
   | Batch / LOT No | `260513-L1-001` (위에서 확인한 번호) |

3. **\[Refresh\]** 클릭

4. 결과 설명:
   - **원료 LOT 목록**: 어떤 사과농축액 배치(TRACE-APPLE-001)와 비타민C 배치(TRACE-VITC-001)가 사용되었는지
   - **입고 경로**: 각 원료가 어느 발주에서 들어왔는지
   - **제조일자 / 유통기한**: 배치별 날짜 확인

5. **활용 시나리오 설명**:  
   > "만약 고객으로부터 이 제품 배치에서 이물이 발견되었다는 클레임이 들어왔을 때, 같은 원료 배치를 사용한 다른 생산 로트가 있는지 Forward Trace로 즉시 확인해 회수 범위를 결정할 수 있습니다."

**체크포인트**: 원료 배치(TRACE-APPLE-001, TRACE-VITC-001)가 결과에 포함되는지 확인

---

## 전체 시연 흐름 요약

```
원료 입고 (바코드 스캔)
    ↓
작업지시서 생성 → LOT 자동 채번
    ↓
재고 출고 → FEFO 경고 (안전장치)
    ↓
재고 현황 실시간 조회
    ↓
완제품 클레임 → 역추적으로 원료 LOT 즉시 확인
```

전체 시연 소요 시간: **약 15~20분**

---

## 문제 해결

| 증상 | 확인 사항 |
|------|----------|
| 바코드 스캔 후 품목이 안 뜸 | `setup_barcodes.run` 재실행 후 확인 |
| LOT 번호가 자동 생성 안 됨 | `bench --site dev.localhost migrate` 후 재시도 |
| FEFO 경고 안 뜸 | `create_fefo_test_stock` 재실행, FEFO-TEST-B 선택 여부 확인 |
| Backward Trace 결과 없음 | `create_trace_demo` 재실행, 생성된 LOT 번호 확인 |
| 페이지 로딩 느림 | `bench --site dev.localhost clear-cache` 실행 |
