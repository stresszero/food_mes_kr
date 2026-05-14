# food_mes_kr — Claude Code 개발 가이드

이 문서는 앞서 만든 `food_mes_kr` 커스텀 앱을 **Claude Code와 함께 실제 개발해 나가기 위한 작업 매뉴얼**입니다.

---

## 목차

1. [개발 환경 구축](#1-개발-환경-구축)
2. [`food_mes_kr` 앱 설치](#2-food_mes_kr-앱-설치)
3. [Claude Code 셋업](#3-claude-code-셋업)
4. [개발 진행 단계](#4-개발-진행-단계)
5. [컨텍스트 관리](#5-컨텍스트-관리)
6. [부록: 권장 도구와 팁](#6-부록)

---

## 1. 개발 환경 구축

### 1.1 권장 환경

| 항목 | 권장 |
|---|---|
| OS | Ubuntu 22.04 / macOS 13+ / Windows 11 + WSL2 |
| RAM | 최소 8GB, 권장 16GB |
| 디스크 | 최소 20GB 여유 |
| 방식 | **Docker + devcontainer** (강력 권장) |

직접 host에 frappe-bench를 설치하는 방식은 Python·Node·MariaDB·Redis 버전을 모두 정확히 맞춰야 해서 깨지기 쉽습니다. **devcontainer 방식이 표준**입니다.

### 1.2 사전 설치 소프트웨어

| 도구 | 용도 | 설치 |
|---|---|---|
| **Docker Desktop** (또는 Docker Engine + Compose) | 컨테이너 실행 | https://www.docker.com/products/docker-desktop |
| **Git** | 소스 관리 | `apt install git` / `brew install git` |
| **VS Code** | IDE (devcontainer 핵심) | https://code.visualstudio.com |
| **VS Code Extension: Dev Containers** | devcontainer 지원 | VS Code 확장 마켓에서 "Dev Containers" 검색 |
| **Claude Code** | AI 페어 프로그래밍 | https://docs.claude.com/en/docs/claude-code/quickstart |
| **DBeaver** (선택) | MariaDB 직접 조회 | https://dbeaver.io |

WSL2를 쓰는 Windows 사용자: WSL2 안에 Ubuntu를 두고, Docker Desktop은 "Use the WSL 2 based engine" 활성화한 뒤 작업은 모두 WSL2 셸에서. (Git Bash나 PowerShell이 아닌 WSL2 셸을 써야 권한·줄바꿈 문제가 없습니다.)

### 1.3 frappe_docker로 ERPNext v15 셋업

frappe 공식 Docker 저장소가 가장 안정적입니다.

```bash
# 1) 작업 디렉토리 (이 안에 모든 게 들어감)
mkdir -p ~/work && cd ~/work

# 2) frappe_docker 클론
git clone https://github.com/frappe/frappe_docker.git
cd frappe_docker

# 3) devcontainer 설정 복사
cp -R devcontainer-example .devcontainer

# 4) VS Code Tasks 복사 (옵션이지만 편리)
cp -R development/vscode-example development/.vscode

# 5) VS Code로 열기
code .
```

VS Code가 열리면 우측 하단에 **"Reopen in Container"** 알림이 뜹니다. 클릭하면 자동으로:
- `frappe/bench:latest` 이미지 빌드
- MariaDB, Redis, Frappe 컨테이너 기동
- VS Code가 컨테이너 안 환경에 접속

처음 한 번은 5~10분 걸립니다. 끝나면 VS Code 좌측 하단에 `Dev Container: Frappe Bench Container` 표시.

### 1.4 frappe-bench 초기화 (컨테이너 안에서)

VS Code 터미널을 열면 이미 컨테이너 안입니다 (`frappe@xxxxxx:/workspace/development$`). 여기서:

```bash
# 1) frappe-bench 초기화
bench init --skip-redis-config-generation \
           --skip-assets \
           --python python3.11 \
           --frappe-branch version-15 \
           frappe-bench

cd frappe-bench

# 2) 호스트 이름 설정 (devcontainer 안의 서비스 이름)
bench set-config -g db_host mariadb
bench set-config -g redis_cache redis://redis-cache:6379
bench set-config -g redis_queue redis://redis-queue:6379
bench set-config -g redis_socketio redis://redis-queue:6379

# 3) 새 사이트 생성  ←  여기서 site 이름이 정해짐
bench new-site dev.localhost \
    --no-mariadb-socket \
    --mariadb-root-password 123 \
    --admin-password admin

# 4) ERPNext 앱 다운로드 + 설치
bench get-app --branch version-15 erpnext
bench --site dev.localhost install-app erpnext

# 5) 개발 모드 ON (Custom Field 변경이 hot-reload 됨)
bench --site dev.localhost set-config developer_mode 1
bench --site dev.localhost clear-cache

# 6) 사이트를 기본 사이트로
bench use dev.localhost
```

### 1.5 서버 기동

```bash
bench start
```

브라우저에서 `http://dev.localhost:8000` 접속. 로그인:
- ID: `Administrator`
- PW: `admin`

ERPNext 첫 화면이 보이면 환경 구축 완료입니다.

> 💡 **`bench start`는 포그라운드 프로세스**입니다. 이 터미널 창은 서버 로그용으로 두고, 작업은 새 터미널에서 진행하세요.

---

## 2. `food_mes_kr` 앱 설치

### 2.1 `<site>`에 무엇을 넣어야 하나?

위에서 `bench new-site dev.localhost`로 만든 사이트 이름이 바로 `<site>`입니다. **사이트 = ERPNext의 가상 호스트(테넌트)**입니다.

```bash
# 따라서 이렇게 됩니다:
bench --site dev.localhost install-app food_mes_kr
```

ERPNext는 멀티테넌트라 한 bench 안에 여러 사이트(각각 다른 회사용)를 만들 수 있습니다. 개발 단계에서는 `dev.localhost` 하나로 충분합니다. 나중에 시연용으로 `demo.localhost`, 운영용으로 실제 도메인 `mes.example.com` 같은 사이트를 추가하는 식.

> ⚠️ `dev.localhost`는 그냥 관례적 이름입니다. 운영체제 host 파일에 등록되어 있어야 브라우저로 접속 가능. devcontainer 방식이면 자동 처리됩니다. WSL2/Linux에서 직접 설치한 경우 `/etc/hosts`에 `127.0.0.1 dev.localhost` 추가.

### 2.2 앱 설치 절차

```bash
# 1) bench 디렉토리로
cd ~/work/frappe_docker/development/frappe-bench
# (devcontainer 안에서는: cd /workspace/development/frappe-bench)

# 2) 앱 압축 해제 또는 git clone
#    옵션 A: tar.gz 받았을 경우
cd apps
tar -xzf ~/Downloads/food_mes_kr.tar.gz
cd ..

#    옵션 B: 자체 git 저장소에 올렸을 경우 (권장)
bench get-app https://github.com/<your-org>/food_mes_kr.git --branch main

# 3) 사이트에 설치
bench --site dev.localhost install-app food_mes_kr

# 4) 마이그레이션 (Custom Field 등 fixture 적용)
bench --site dev.localhost migrate

# 5) 캐시 초기화
bench --site dev.localhost clear-cache

# 6) 시연 데이터 시드 (선택)
bench --site dev.localhost execute food_mes_kr.food_mes_kr.demo_seed.run
```

설치 검증: ERPNext에 로그인 → Manufacturing → Work Order → 새로 만들면 `Production LOT No (제조번호)` 필드가 보이고 자동 채번됨.

### 2.3 Git 저장소로 관리하기 (강력 권장)

Claude Code는 git diff 기반으로 변경사항을 추적하므로 **반드시 git 저장소로 관리**하세요.

```bash
cd apps/food_mes_kr
git init
git add .
git commit -m "Initial: food_mes_kr v0.1.0 prototype"

# 원격 저장소 (GitHub Private 권장)
git remote add origin https://github.com/<your-org>/food_mes_kr.git
git push -u origin main
```

ERPNext 본체와 frappe_docker는 손대지 않으니 git 추적 대상이 아닙니다. **`food_mes_kr`만 우리 저장소.**

---

## 3. Claude Code 셋업

### 3.1 설치 및 인증

```bash
# Claude Code CLI 설치 (Node.js 18+ 필요)
npm install -g @anthropic-ai/claude-code

# 인증
claude
# → 브라우저에서 Anthropic 로그인
```

### 3.2 작업 디렉토리

Claude Code는 **`food_mes_kr/` 디렉토리에서 실행**해야 합니다. 그래야 코드 컨텍스트가 정확합니다.

```bash
cd ~/work/frappe_docker/development/frappe-bench/apps/food_mes_kr
claude
```

### 3.3 핵심 파일: `CLAUDE.md`

Claude Code는 작업 디렉토리의 `CLAUDE.md`를 자동으로 읽어서 모든 대화의 시스템 컨텍스트로 사용합니다. **이 파일이 잘 쓰여 있을수록 결과 품질이 직선적으로 올라갑니다.**

별첨 파일 `CLAUDE.md`를 `food_mes_kr/` 루트에 두세요. 이 파일이 Claude에게 알려주는 것:
- 이 앱의 목적과 도메인 (한국 식음료 MES)
- 디렉토리 구조와 각 파일의 역할
- 코드 컨벤션 (ERPNext 따름)
- 절대 하지 말아야 할 것 (코어 수정, browser storage 등)
- 테스트 방법
- LOT 채번 규칙 등 도메인 규칙

---

## 4. 개발 진행 단계

전체 로드맵을 4개 페이즈, 16개 작업 단위(Task)로 나누었습니다. **태스크 단위로 Claude Code에 의뢰** → **사람이 검토·테스트** → **commit** 사이클을 권장합니다.

### 4.1 의존 관계 도식

```
[Phase 1: 마스터 데이터]
  T1.1 알러겐 마스터 ─────┐
  T1.2 식품유형 분류 ─────┤
  T1.3 라인/교대 ──────────┤
  T1.4 데이터 import 템플릿┘
                          ↓
[Phase 2: 생산 실행]
  T2.1 LOT 채번 보강 (이미 있음, 보강만)
  T2.2 FEFO 자동 출고 ──┐
  T2.3 Job Card 측정값 입력 ─┤
  T2.4 작업자 태블릿 화면 ────┤
                            ↓
[Phase 3: 품질·HACCP]
  T3.1 CCP 매핑 (Quality Inspection 확장)
  T3.2 CCP 이탈 시 자동 NC 생성    ──┐
  T3.3 NC → CAPA 워크플로우         ─┤
  T3.4 Forward/Backward Trace 보고서 (이미 있음, 검증/보강)
                                   ↓
[Phase 4: 라벨·외부 통합]
  T4.1 식약처 표시기준 라벨 (Print Format)
  T4.2 ZPL 라벨 프린터 출력
  T4.3 스마트스토어 주문 sync (선택)
  T4.4 ERP 회계 연동 (대형 작업, 별도 프로젝트)
```

**병렬 가능한 작업**:
- Phase 1의 T1.1~T1.4는 서로 독립 → 4개 동시 병렬 가능
- Phase 2의 T2.2와 T2.3은 독립 → 병렬 가능
- Phase 3의 T3.1과 T3.4는 독립

**순차 의존**:
- Phase 1 완료 후에야 Phase 2 가능 (라인·교대 마스터가 LOT 채번에 필요)
- T3.2 (자동 NC)는 T3.1 (CCP 매핑) 후에만 가능
- T4.2 (ZPL)는 T4.1 (Print Format) 후

### 4.2 태스크별 산출물과 사전 설정

각 Task는 다음 4가지를 갖춥니다:
1. **목표** (한 문장)
2. **산출물** (생성될 파일 목록)
3. **사전 설정** (개발 시작 전 준비할 것)
4. **수락 기준** (DoD: Definition of Done)

#### Phase 1: 마스터 데이터

##### T1.1 알러겐 마스터 DocType
- **목표**: 식약처 22종 알러겐을 마스터로 관리하고 Item에 연결
- **산출물**:
  - `food_mes_kr/food_mes_kr/doctype/allergen/allergen.json` (DocType 정의)
  - `food_mes_kr/food_mes_kr/doctype/allergen/allergen.py` (컨트롤러)
  - `food_mes_kr/fixtures/allergen.json` (22종 시드 데이터)
  - `Item`의 `allergen_flags` Custom Field를 Small Text → **Table MultiSelect**로 변경
- **사전 설정**:
  - 식약처 알러기 유발물질 22종 리스트를 텍스트로 준비 (별도 첨부 자료)
- **수락 기준**:
  - Item 화면에서 알러겐 다중 선택 가능
  - 알러겐이 라벨 Print Format에 자동 표시
  - migrate 후 fixture 자동 import

##### T1.2 식품유형 분류 코드 DocType
- **목표**: 식약처 식품 분류 코드(예: 04101 과채주스)를 마스터로
- **산출물**:
  - `food_mes_kr/food_mes_kr/doctype/kc_food_category/kc_food_category.json`
  - `Item.kc_food_code`를 Data → Link로 변경
- **사전 설정**: 식품공전 식품유형 분류표 CSV
- **수락 기준**: 식품유형으로 Item 필터·집계 가능

##### T1.3 라인·교대 마스터 정비
- **목표**: Workstation에 line_code, Shift Type 정비
- **산출물**:
  - `Workstation` Custom Field 보강 (line_code는 이미 있음, capacity_per_hour 추가)
  - `Shift Type` 표준 값 fixture (1교대 06-14, 2교대 14-22, 3교대 22-06)
  - 시드 스크립트
- **사전 설정**: 고객사 라인 수와 교대 정책
- **수락 기준**: Work Order 발행 시 production_shift 선택 가능

##### T1.4 데이터 Import 템플릿
- **목표**: 고객 데이터(Item, BOM, Customer)를 엑셀로 받아서 일괄 입력
- **산출물**:
  - `food_mes_kr/food_mes_kr/doctype/data_import_template/` (CSV 템플릿 + 검증 로직)
  - 또는 ERPNext 표준 Data Import + 사용 가이드 문서
- **사전 설정**: 고객사 기존 마스터 (있으면)

#### Phase 2: 생산 실행

##### T2.1 LOT 채번 (이미 구현됨, 보강만)
- **보강 내용**: 사용자별 prefix 옵션, 멀티 회사 지원, 재발행 기능

##### T2.2 FEFO 자동 출고
- **목표**: 원료 출고 시 유통기한 임박순으로 자동 LOT 선택
- **산출물**:
  - `food_mes_kr/food_mes_kr/server_scripts/fefo_picker.py`
  - Stock Settings에 토글 추가
- **사전 설정**: ERPNext의 `Auto Create Serial and Batch Bundle` 기능 동작 확인
- **수락 기준**: Stock Entry: Material Transfer for Manufacture에서 자동으로 만료일 임박 LOT 선택

##### T2.3 Job Card 측정값 입력
- **목표**: 작업자가 공정 시작/완료 시 온도·시간·pH 등 입력
- **산출물**:
  - `Job Card` Custom Fields 추가 (`actual_temperature`, `actual_duration`, `ph_value`, `brix`)
  - `Job Card`에 자동 Quality Inspection 연결 로직
- **사전 설정**: 공정별 측정 항목 정의
- **수락 기준**: 측정값이 Quality Inspection으로 자동 흘러감

##### T2.4 작업자 태블릿 화면 (Plant Floor 보강)
- **목표**: 작업자가 태블릿에서 한 화면에서 시작→측정→완료
- **산출물**:
  - `food_mes_kr/public/js/operator_tablet.js` (Client Script)
  - 또는 별도 Web Page (`/operator/tablet`)
- **사전 설정**: 태블릿 화면 와이어프레임 (간단히 손그림이라도)
- **수락 기준**: 비숙련자가 5분 교육으로 사용 가능

#### Phase 3: 품질·HACCP

##### T3.1 CCP 매핑
- **목표**: Quality Inspection Parameter에 `is_ccp=1` 표시 + CCP 전용 보고서
- **산출물**:
  - `food_mes_kr/food_mes_kr/report/haccp_ccp_log/` (CCP 모니터링 로그)
  - `Item Quality Inspection Parameter`의 `is_ccp` 필드는 이미 있음 (활용)
- **사전 설정**: 고객사 HACCP 관리계획서

##### T3.2 CCP 이탈 시 자동 NC 생성
- **목표**: Quality Inspection Submit 시 CCP 항목 NG면 Non Conformance 자동 생성
- **산출물**:
  - `food_mes_kr/food_mes_kr/server_scripts/quality_inspection_hook.py`
  - `hooks.py`에 등록 (이미 placeholder 있음)
- **수락 기준**:
  - CCP 항목이 min/max 벗어나면 NC 자동 생성
  - 생성된 NC가 해당 Batch에 자동 링크
  - Quality Manager에게 알림 메일

##### T3.3 NC → CAPA 워크플로우
- **목표**: NC를 정식 CAPA 흐름으로 (시정조치 → 검증 → 마감)
- **산출물**:
  - Workflow DocType 정의 (Open → Investigation → CA Planned → CA Done → Verified → Closed)
  - 단계별 권한
- **사전 설정**: 고객사 CAPA 절차서

##### T3.4 Trace 보고서 (이미 구현됨, 검증·보강)
- **보강**: Delivery Note까지 따라가는 출하처 표시, Recall Notice PDF 출력

#### Phase 4: 라벨·외부 통합

##### T4.1 식약처 표시기준 라벨 (Print Format)
- **산출물**:
  - `food_mes_kr/food_mes_kr/print_format/kc_food_label/` (Jinja 템플릿)
  - 출력 항목: 품명, 식품유형, 제조연월일, 유통기한, 원재료명, 영양성분, 알러기 표시
- **사전 설정**: 식약처 식품등의 표시기준 PDF
- **참고**: 식품 라벨은 디자이너가 만든 Adobe Illustrator 양식이 있는 경우가 많아, 그걸 SVG/HTML로 변환

##### T4.2 ZPL 라벨 프린터 출력
- **산출물**:
  - `food_mes_kr/food_mes_kr/api/zpl.py` (Batch 받아 ZPL 문자열 반환)
  - 클라이언트 JS에서 fetch로 호출
- **사전 설정**: 라벨 프린터 모델·DPI

##### T4.3 스마트스토어 주문 동기화 (선택)
- **산출물**: `food_mes_kr/food_mes_kr/api/smartstore_sync.py`
- **사전 설정**: 네이버 커머스 API 인증

##### T4.4 ERP 회계 연동 (별도 프로젝트로 분리 권장)

---

## 5. 컨텍스트 관리

Claude Code는 토큰 윈도우 안에서 작동하므로, **세션 단위로 컨텍스트를 정리**하면 결과 품질이 크게 좋아집니다.

### 5.1 세션 구분 원칙

**1세션 = 1태스크.** 위 16개 태스크를 각각 별도 세션에서 처리. 한 세션 안에서 여러 태스크를 처리하면 컨텍스트가 오염되어 후반 결과가 저하됩니다.

### 5.2 세션 시작 시 항상 하는 것

```
# 새 Claude Code 세션 시작 시
1. /clear 또는 새 터미널
2. cd apps/food_mes_kr
3. claude
4. 첫 메시지로 다음 정보 제공:
   - 어떤 태스크인지 (예: "T2.3 Job Card 측정값 입력")
   - 관련 기존 파일 경로 (예: "food_mes_kr/server_scripts/work_order_lot.py 패턴을 따라")
   - 도메인 정보 (예: "살균 공정의 측정값은 온도, 시간, pH 3가지")
   - DoD (예: "측정값이 Quality Inspection으로 자동 흘러가야 함")
```

### 5.3 프롬프트 템플릿

별첨 파일 `prompts/` 폴더에 16개 태스크별 프롬프트 템플릿을 두었습니다. 각 템플릿은:
- **Context**: 도메인 배경
- **Task**: 무엇을 만들 것인가
- **Constraints**: 기술적 제약
- **Reference**: 참고할 기존 파일
- **Acceptance**: DoD

### 5.4 세션 종료 시 항상 하는 것

```bash
# 변경사항 검토
git diff
git status

# 테스트 실행 (있는 것)
bench --site dev.localhost run-tests --app food_mes_kr

# 동작 확인
bench --site dev.localhost migrate
bench --site dev.localhost clear-cache
# → 브라우저에서 직접 시연 시나리오 실행

# 커밋
git add .
git commit -m "T2.3: Job Card 측정값 입력 필드 + QI 자동 연결"

# 다음 세션 메모 (선택)
echo "T2.3 done. T2.4(태블릿 UX)는 T2.3에서 만든 측정값 필드를 사용함." >> NOTES.md
```

### 5.5 컨텍스트 폭발 방지 팁

- **대용량 파일은 통째로 보여주지 말 것**: ERPNext core 코드를 읽어달라고 하지 말고, 필요한 함수 이름만 알려주고 Claude가 직접 `view`로 읽게 하기
- **/compact 명령**: 세션이 길어지면 Claude Code의 `/compact`로 컨텍스트 요약
- **하나의 큰 작업 → 여러 세션**: 예) "Phase 3 전체"를 한 번에 의뢰하지 말고 T3.1, T3.2, T3.3 각각 분리

---

## 6. 부록

### 6.1 추가로 필요한 환경

#### 6.1.1 데이터 보호
- **`.gitignore`**: `__pycache__`, `*.pyc`, `node_modules`, `.env`, `local_*` 추가
- **secrets**: API 키 등은 `frappe-bench/sites/<site>/site_config.json`의 별도 키에. git에 커밋 금지
- **고객 데이터**: 고객사에서 받은 실제 SKU·BOM은 별도 사이트(`customer.localhost`)에 두고 git 추적 제외

#### 6.1.2 백업 정책
```bash
# 매일 자동 백업 (cron)
bench --site dev.localhost backup --with-files

# 백업 위치: sites/<site>/private/backups/
# 운영 사이트는 S3 등 외부 동기화 필수
```

#### 6.1.3 환경 분리
| 환경 | 사이트 | 용도 |
|---|---|---|
| dev | `dev.localhost` | Claude Code 작업 |
| demo | `demo.localhost` | 시연용 (가짜 데이터) |
| staging | `staging.<domain>` | 고객 검수 |
| production | `<actual domain>` | 운영 |

### 6.2 디버깅 도구

- **로그**: `frappe-bench/logs/web.log`, `worker.log`, `scheduler.log`
- **에러 화면 확장**: `Error Log` DocType (관리자 메뉴)
- **DB 직접 조회**: `bench --site dev.localhost mariadb` → SQL 직접 실행
- **Python 콘솔**: `bench --site dev.localhost console` → frappe context로 REPL

### 6.3 테스트 작성

ERPNext는 unittest 기반.
```python
# food_mes_kr/food_mes_kr/server_scripts/test_work_order_lot.py
import frappe
import unittest

class TestWorkOrderLot(unittest.TestCase):
    def test_lot_auto_assigned(self):
        wo = frappe.get_doc({
            "doctype": "Work Order",
            "production_item": "FG-HELLO-APPLE",
            "qty": 1000,
            # ...
        }).insert()
        self.assertIsNotNone(wo.production_lot_no)
        self.assertRegex(wo.production_lot_no, r'^\d{6}-[A-Z0-9]+-\d{3}$')
```

```bash
bench --site dev.localhost run-tests --app food_mes_kr --module "food_mes_kr.food_mes_kr.server_scripts.test_work_order_lot"
```

### 6.4 운영 배포 시 체크리스트

상세는 본 가이드 범위 밖이지만 미리 알아둘 점:
- HTTPS (Let's Encrypt)
- nginx + supervisord (frappe_docker production 이미지에 포함)
- 외부 백업 (S3, NAS)
- 모니터링 (Prometheus + Grafana 또는 Frappe Insights)
- 사용자 라이선스 카운트 (ERPNext 자체는 무제한이지만 도덕적·계약적 관리)

### 6.5 자주 만나는 문제

별첨 `TROUBLESHOOTING.md` 참조.

### 6.6 도움 받기

- ERPNext 공식 문서: https://docs.erpnext.com
- Frappe Framework 문서: https://docs.frappe.io
- 한국 사용자 모임: https://discuss.frappe.io 의 #korean 태그 (활동 활발함)
- 커스텀 앱 만들기 튜토리얼: https://frappeframework.com/docs/user/en/tutorial

---

## 첨부 파일 목록

같은 디렉토리에 함께 있는 파일들:

1. **`CLAUDE.md`** — Claude Code가 매 세션마다 자동으로 읽는 프로젝트 가이드
2. **`prompts/T1.1_allergen_doctype.md`** ~ **`T4.4_*.md`** — 16개 태스크별 프롬프트 템플릿
3. **`devcontainer.json`** — VS Code devcontainer 추천 설정
4. **`TROUBLESHOOTING.md`** — 흔한 오류 해결법
5. **`.gitignore`** — git 제외 패턴
