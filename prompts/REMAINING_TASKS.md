# 나머지 태스크 Stubs

각 태스크마다 별도 `.md` 파일로 저장하기 전, **빠른 시작을 위해 짧은 형태로 모아둔 파일**입니다. 실제 작업 시 해당 섹션만 잘라서 별도 파일로 만들고 `<…>` 부분을 채워 사용하세요.

T1.1, T2.3, T3.2, T4.1은 풀 버전 별도 파일에 있습니다 (참고 패턴).

---

## T1.2 — 식품유형 분류 코드 DocType

### Context
식약처 식품공전의 식품유형 분류 코드(예: 04101 과채주스)를 마스터로 관리. 현재 `Item.kc_food_code`가 자유 입력 텍스트 → 오타·일관성 문제.

### Task
- 신규 DocType `KC Food Category`: code(unique), name_ko, name_en, parent_category(self-link), description, regulations_summary
- 식약처 식품공전 1차 분류 시드 (음료류, 과자류, 빙과류, 면류 등 20여 개)
- `Item.kc_food_code`를 Data → Link 변환

### Reference
- T1.1과 같은 DocType 생성 패턴
- 식약처 식품공전 PDF (사용자 제공 필요)

### DoD
- Item에서 식품유형 검색 가능
- 식품유형으로 Item 필터링 가능
- 라벨 Print Format에서 식품유형명 표시

---

## T1.3 — 라인·교대 마스터 정비

### Context
LOT 채번이 정확히 동작하려면 Workstation의 line_code와 Shift Type이 정확해야 함. 또한 Production Plan 시 라인별 capacity 산정 필요.

### Task
- `Workstation`에 Custom Field 추가: `capacity_per_hour` (Float), `line_type` (Select: Filling/Mixing/Sterilization/Packing/Other)
- `Shift Type` 표준 시드: 1교대(06-14), 2교대(14-22), 3교대(22-06)
- Workstation에 line_code 미입력 시 LOT 채번 경고

### Reference
- 기존 fixtures/custom_field.json 패턴
- `food_mes_kr/server_scripts/work_order_lot.py`의 `_resolve_line_code()` 로직

### DoD
- Work Order 발행 시 production_shift 선택 가능
- line_code 없는 Workstation에는 빨간 경고 indicator
- Capacity 기반 일일 생산 가능량 보고서 (간단 Script Report 1개)

---

## T1.4 — 데이터 Import 템플릿

### Context
고객사 도입 시 기존 마스터(Item, BOM, Customer)를 한 번에 import해야 함. ERPNext 표준 Data Import는 강력하지만 컬럼 명세가 명확하지 않으면 실수 잦음.

### Task
- CSV 템플릿 4종 작성 (`templates/data_import/` 디렉토리):
  - `01_items.csv` — Item 마스터 (필수 컬럼만, 알러겐·식품유형 포함)
  - `02_boms.csv` — BOM (Item별 레시피)
  - `03_customers.csv` — 고객사 (OEM 거래처용 필드 포함)
  - `04_workstations.csv` — 라인·작업장
- 각 CSV에 헤더 주석 (#)으로 사용법
- import 전 검증 함수 (`food_mes_kr/api/import_validator.py`):
  - 필수 컬럼 체크
  - 알러겐 코드 유효성 체크
  - UOM 변환 가능 여부 체크
- 사용자 매뉴얼 markdown 1장 (`docs/data_import_guide.md`)

### DoD
- 템플릿 4개로 50개 가짜 Item을 무오류 import 성공
- 검증 함수가 잘못된 데이터에 대해 명확한 한국어 에러 메시지

---

## T2.1 — LOT 채번 보강

### Context
T1단계 완료 후 운영하면서 발견될 케이스:
- 회사가 여러 곳 (멀티 회사 ERP)
- LOT 번호 형식을 거래처가 지정 (예: 거래처별 prefix)
- 발행 후 재발행 필요 (출고 전 LOT 변경)

### Task
- `food_mes_kr/food_mes_kr/server_scripts/work_order_lot.py` 보강:
  - Customer별 LOT prefix 정책 — `Customer` Custom Field `lot_prefix_template`
  - 멀티 회사: company code 포함 옵션
  - `regenerate_lot_no` 화이트리스트 함수에 권한 체크 추가 (Manager 이상만)

### DoD
- 거래처별 다른 LOT 형식이 정상 발행
- 권한 없는 사용자의 재발행 시도 차단
- 단위 테스트: 멀티 회사 + 거래처 prefix 케이스

---

## T2.2 — FEFO 자동 출고

### Context
원료 출고 시 유통기한 임박 LOT을 자동 선택. ERPNext는 FEFO 옵션이 있지만 기본값이 FIFO이고 Material Transfer for Manufacture에서는 자동 적용이 빠지는 경우 있음.

### Task
- `food_mes_kr/food_mes_kr/server_scripts/fefo_picker.py`
  - Stock Entry: Material Transfer for Manufacture의 `validate` 훅
  - 각 row에 batch_no가 비어 있고 Item이 has_batch_no=1이면, 만료일 임박 + 충분한 재고 LOT 자동 선택
- Stock Settings에 `enforce_fefo_for_food_items` 토글 (Custom Field)
- 위반 경고 (이미 다른 LOT 선택했는데 더 빨리 만료될 LOT이 있는 경우): warning만, block은 안 함

### DoD
- 토글 ON 상태에서 Material Transfer 생성 → batch_no 자동 채워짐
- 만료된 LOT은 자동 선택 안 됨
- 강제 선택 시 경고 표시
- 단위 테스트: 3개 LOT 중 가장 빨리 만료되는 게 선택되는지

---

## T2.4 — 작업자 태블릿 화면

### Context
현장 작업자는 ERPNext desk UI를 어렵게 느낌. 한 작업의 시작/측정/완료를 큰 버튼 한 화면에 모아야 함.

### Task
- 옵션 A (간단): `food_mes_kr/public/js/operator_tablet.js`로 Job Card 화면을 태블릿 모드로 단순화
- 옵션 B (정공법): 별도 Web Page `/operator/tablet/<job_card_name>`
- 큰 글자, 큰 버튼, 측정값 텐키 입력
- 측정값 비정상 시 빨간 화면

### Reference
- ERPNext Plant Floor: `apps/erpnext/erpnext/manufacturing/doctype/plant_floor/`
- 우리 T2.3 측정값 구조

### DoD
- 비숙련 작업자가 5분 교육으로 작업 가능
- 작업자 권한으로 Job Card 외 다른 정보 노출 안 됨 (보안)
- 한 라인의 모든 작업이 한 화면에 보이는 라인 대시보드도 포함

---

## T3.1 — CCP 매핑 + 모니터링 보고서

### Context
HACCP 인증 회사는 매일/매주 CCP 모니터링 로그를 출력해야 함. 식약처 정기 점검 시 첫 요구사항.

### Task
- `food_mes_kr/food_mes_kr/report/haccp_ccp_log/` Script Report
  - 필터: 기간, Workstation, CCP 항목
  - 컬럼: 측정시각, LOT, CCP, 측정값, 한계, 결과(Pass/Fail), 이탈 시 NC 링크, 시정조치 여부
- HACCP 관리계획서 매뉴얼 import — Custom DocType `HACCP Plan`, `HACCP CCP`
  - HACCP Plan은 회사·라인·제품 단위
  - 각 CCP는 Item Quality Inspection Parameter와 연결

### DoD
- 한 달치 CCP 로그 30초 이내 출력
- PDF export 시 식약처 점검용 양식 형태
- HACCP Plan 업데이트 시 이력 추적 (audit log 활용)

---

## T3.3 — NC → CAPA 워크플로우

### Context
NC가 발생하면 시정조치(CA) → 예방조치(PA) → 효과성 검증(EV) → 마감 단계가 정해져 있어야 함. 단계별 다른 사람이 다른 권한으로 처리.

### Task
- ERPNext Workflow DocType 사용:
  - Open → Investigation → CA Planned → CA Done → Verification → Closed
- 각 단계별 권한 (역할 기반):
  - Quality Inspector: Open → Investigation
  - Quality Manager: Investigation → CA Planned → CA Done → Verification
  - Plant Manager: Verification → Closed (검증)
- 단계 전환 시 알림
- 단계별 due_date 자동 계산 (각 단계 5영업일 등 정책 가능)

### DoD
- 권한 없는 사용자의 단계 전환 차단
- 미마감 NC 통계 대시보드
- 7일 이상 정체된 NC 자동 escalation 메일

---

## T3.4 — Trace 보고서 보강

### Context
이미 Forward/Backward Trace는 작동. 다음을 보강:
- Delivery Note까지 따라가서 출하처·출하일자 표시 (Forward에 일부 있음, 보강)
- "회수 통지서" PDF 자동 생성
- 회수 대상 거래처 필터로 분리

### Task
- `food_mes_kr/food_mes_kr/print_format/recall_notice/` (Batch 대상 Print Format)
- Forward Trace 보고서에 "회수 통지서 발행" 버튼 추가 (이미 JS placeholder 있음)
- 회수 통지서 본문은 식약처 회수 양식에 맞춤

### DoD
- 임의 LOT 입력 → 영향 거래처 자동 추출 → 회수 통지서 PDF 일괄 생성
- 한 거래처에는 한 번만 발행 (중복 방지)

---

## T4.2 — ZPL 라벨 프린터 출력

### Context
박스 라벨, 파렛트 라벨은 보통 Zebra 프린터로 ZPL 직접 보냄. PDF 인쇄는 너무 느림.

### Task
- `food_mes_kr/food_mes_kr/api/zpl.py`
  - `@frappe.whitelist()` 함수 `generate_zpl(batch_name, label_type)`
  - label_type: 'box' (ITF-14), 'pallet' (SSCC), 'product' (EAN-13)
  - ZPL 문자열 반환
- 클라이언트 JS: Batch 화면에 "ZPL 인쇄" 버튼 → fetch → 로컬 프린터로 직접 전송 (USB/네트워크)
- ZPL 코드는 라벨 프린터 모델별로 미세 조정 필요 → 설정에 모델·DPI

### Constraints
- 직접 USB 통신은 브라우저에서 어려우므로 **로컬 ZPL 게이트웨이 1차 권장** (Print Node 같은 서비스, 또는 자체 작은 Python daemon)
- 라벨 프린터 IP 직접 통신도 옵션

### DoD
- 박스 라벨 1장 1초 이내 출력
- ZPL 코드 unit test (생성된 문자열 형식 검증)

---

## T4.3 — 스마트스토어 주문 동기화 (선택, 자사몰 있는 경우만)

### Context
자사몰(네이버 스마트스토어) 주문을 자동으로 ERPNext Sales Order로 변환. 수기 입력 인력비 절감 목적.

### Task
- `food_mes_kr/food_mes_kr/api/smartstore_sync.py`
  - 네이버 커머스 API (Commerce API) 인증
  - 주기적 polling (scheduler 5분)
  - 신규 주문 → ERPNext Sales Order 생성
  - 주문 상태 업데이트 → ERPNext에 반영
- Customer 매핑 룰 (없으면 신규 생성)
- 멱등성 (같은 주문 두 번 처리 안 됨)

### Constraints
- API 키는 site_config.json에. git 금지.
- 네이버 API rate limit 준수.
- 주문 누락 발생 시 슬랙/이메일 알림.

### DoD
- 스마트스토어 신규 주문 5분 이내 ERPNext 반영
- 14일치 주문 batch 재import 수동 실행 가능
- API 장애 시 자동 재시도 + 알림

---

## T4.4 — ERP 회계 연동 (별도 프로젝트로 강력 권장)

### Context
한국 회계 (e-Tax 전자세금계산서, 한국 표준 계정과목, 부가세 신고)는 ERPNext 표준에 부재. 별도 한국 지역화 앱 또는 외부 회계 SaaS와 연동.

###권장 접근
이 task는 **본 프로젝트 범위에 넣지 말고 별도 프로젝트로**:
- 옵션 A: erpnext-korea 같은 한국 지역화 앱 도입 (있다면)
- 옵션 B: 더존, SAP B1 같은 외부 회계 ERP와 인터페이스
- 옵션 C: 자체 한국 지역화 앱 개발 (큰 프로젝트)

### 본 프로젝트에서 할 일은
- ERPNext의 매출/매입 데이터를 외부로 export할 API endpoint 정도만 (`/api/method/food_mes_kr.api.export.invoices_for_etax`)
- 본격 연동은 별도 SOW(Statement of Work)
