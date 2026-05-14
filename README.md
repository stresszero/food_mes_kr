# food_mes_kr — ERPNext Custom App for Korean F&B

식음료(음료/액상 식품) 제조업체용 ERPNext 커스터마이징 앱.
**음료 OEM/ODM** (예: 좋은F&B 같은 스파우트파우치 음료 제조사)을 베이스로 설계되었지만,
일반 가공식품 제조업에도 70~80%는 그대로 적용됩니다.

---

## 설치 (frappe-bench 환경에서)

```bash
# 1. bench가 이미 설치되어 있다고 가정
cd ~/frappe-bench

# 2. 앱 디렉토리를 apps/ 밑에 복사
cp -r food_mes_kr apps/

# 3. setup.py 등록 (이 앱이 처음이라면)
bench --site <your-site> install-app food_mes_kr

# 4. 마이그레이션 (Custom Fields 등 fixture 적용)
bench --site <your-site> migrate

# 5. 캐시 초기화
bench --site <your-site> clear-cache
```

---

## 디렉토리 구조

```
food_mes_kr/
├── README.md
├── setup.py                          # pip 설치 메타데이터
├── requirements.txt                  # Python 의존성
├── license.txt                       # GPLv3 (ERPNext 따라감)
└── food_mes_kr/                      # 앱 패키지 (이 폴더 이름 = 앱 이름)
    ├── __init__.py                   # 앱 버전
    ├── hooks.py                      # ★ 핵심: 모든 훅·fixtures·이벤트 등록
    ├── modules.txt                   # 모듈 리스트
    ├── patches.txt                   # 일회성 데이터 마이그레이션
    ├── fixtures/                     # ★ Custom Fields, Property Setters
    │   └── custom_field.json
    ├── food_mes_kr/                  # 실제 비즈니스 로직 (모듈 디렉토리)
    │   ├── __init__.py
    │   ├── server_scripts/           # ★ Python 훅 함수
    │   │   ├── __init__.py
    │   │   ├── work_order_lot.py     # LOT 자동 채번
    │   │   └── batch_naming.py       # Batch 생성 시 LOT 적용
    │   ├── report/                   # ★ Script Reports
    │   │   ├── forward_trace/        # Forward Trace (원료 → 제품)
    │   │   │   ├── forward_trace.json
    │   │   │   ├── forward_trace.py
    │   │   │   └── forward_trace.js
    │   │   └── backward_trace/       # Backward Trace (제품 → 원료)
    │   │       ├── backward_trace.json
    │   │       ├── backward_trace.py
    │   │       └── backward_trace.js
    │   ├── doctype/                  # 신규 Custom DocType (예: 알러겐)
    │   └── print_format/             # 식약처 라벨 등
    ├── public/                       # 정적 파일 (JS/CSS)
    ├── templates/                    # Jinja 템플릿
    ├── api/                          # 외부 통합 (스마트스토어 등)
    └── patches/                      # 일회성 마이그레이션 스크립트
```

---

## 핵심 파일 위치

| 기능 | 위치 |
|---|---|
| 훅 등록 | `food_mes_kr/hooks.py` |
| Custom Fields 정의 | `food_mes_kr/fixtures/custom_field.json` |
| LOT 자동 채번 | `food_mes_kr/food_mes_kr/server_scripts/work_order_lot.py` |
| Batch에 LOT 적용 | `food_mes_kr/food_mes_kr/server_scripts/batch_naming.py` |
| Forward Trace 보고서 | `food_mes_kr/food_mes_kr/report/forward_trace/` |
| Backward Trace 보고서 | `food_mes_kr/food_mes_kr/report/backward_trace/` |

---

## 한국식 LOT 채번 규칙

기본 형식: `YYMMDD-라인코드-SEQ` (예: `251207-L1-001`)

- `YYMMDD`: Work Order의 `planned_start_date` 기준 (없으면 today())
- `라인코드`: Custom Field `production_line` (Link → Workstation)에서 가져옴.
  Workstation에 Custom Field `line_code` (Data) 추가 필요. 없으면 Workstation 이름 첫 글자 사용.
- `SEQ`: 같은 (날짜, 라인) 조합 내 일련번호 (3자리, 0 패딩)

예시:
- `251207-L1-001` ← 12월 7일, 1번 라인, 첫 번째 작업
- `251207-L1-002` ← 같은 날 같은 라인 두 번째
- `251207-L2-001` ← 같은 날 다른 라인 첫 번째

이 LOT 번호가 그대로 **완제품 Batch ID**가 됩니다 (`batch_naming.py` 참조).

---

## Trace 보고서 사용법

ERPNext 메뉴: **Stock > Reports > Forward Trace** (또는 Backward Trace)

### Forward Trace (원료 LOT → 어떤 완제품 LOT으로 갔는가)

식약처 회수 대응 시나리오: "사과농축액 LOT FRX-20251201이 오염 의심. 이게 들어간 완제품을 모두 찾아라"

→ Forward Trace에 `FRX-20251201` 입력 → 영향받은 완제품 LOT 전체 + 출하처까지 한 번에 조회

### Backward Trace (완제품 LOT → 어떤 원료 LOTs를 썼는가)

소비자 클레임 시나리오: "헬로아이 사과주스 LOT 251207-L1-001에서 이물질 발견. 어느 원료 의심?"

→ Backward Trace에 `251207-L1-001` 입력 → 사용된 모든 원료 LOT + 공급사 + 입고일 조회

---

## 의존성

- ERPNext v15+ (Frappe Framework v15+)
- MariaDB 10.6+ (재귀 CTE 지원)
- Python 3.10+

---

## 라이선스

GPLv3 (ERPNext와 동일).
이 앱을 외부에 SaaS로 제공하면 GPL 전염 효과 주의.
