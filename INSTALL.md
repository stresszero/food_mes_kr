# food_mes_kr 시연 환경 설치 가이드

다른 컴퓨터에서 처음부터 시연 환경을 구축하는 절차입니다.  
완료 후 `DEMO_GUIDE.md`의 시연 #1~#5를 그대로 실행할 수 있습니다.

---

## 대상 환경

| 항목 | 권장 사양 |
|------|----------|
| OS | Ubuntu 22.04 LTS / 24.04 LTS (또는 Windows WSL2 동일 버전) |
| CPU | 4코어 이상 |
| RAM | 8GB 이상 (16GB 권장) |
| 디스크 | 20GB 이상 여유 |

> **Windows 사용자**: WSL2 Ubuntu 22.04를 설치한 뒤 아래 모든 명령어를 WSL 터미널에서 실행합니다.  
> WSL2 설치: `wsl --install -d Ubuntu-22.04` (PowerShell 관리자 모드)

---

## 1단계 — 시스템 패키지 설치

```bash
sudo apt update && sudo apt upgrade -y

sudo apt install -y \
  git curl wget \
  python3-dev python3-pip python3-venv \
  build-essential \
  libssl-dev libffi-dev \
  mariadb-server mariadb-client \
  redis-server \
  xvfb libfontconfig wkhtmltopdf \
  libmysqlclient-dev

# Node.js 18 (nvm 사용)
curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.40.1/install.sh | bash
source ~/.bashrc
nvm install 18
nvm use 18
nvm alias default 18

# yarn
npm install -g yarn
```

---

## 2단계 — MariaDB 설정

```bash
sudo mysql_secure_installation
# 질문 답변:
#   Enter current password for root: (엔터)
#   Switch to unix_socket authentication: n
#   Change the root password: y  → 비밀번호 입력 (예: admin)
#   Remove anonymous users: y
#   Disallow root login remotely: y
#   Remove test database: y
#   Reload privilege tables: y
```

MariaDB 문자셋 설정:

```bash
sudo tee -a /etc/mysql/mariadb.conf.d/50-server.cnf > /dev/null <<'EOF'

[mysqld]
character-set-client-handshake = FALSE
character-set-server = utf8mb4
collation-server = utf8mb4_unicode_ci

[mysql]
default-character-set = utf8mb4
EOF

sudo systemctl restart mariadb
```

---

## 3단계 — frappe-bench 설치

```bash
pip3 install frappe-bench

# PATH 적용 (설치 후 처음 한 번)
source ~/.bashrc
# 또는 로그아웃 후 다시 로그인
```

설치 확인:

```bash
bench --version
# 출력 예: 5.x.x
```

---

## 4단계 — Bench 초기화 (Frappe + ERPNext)

```bash
cd ~

bench init \
  --frappe-branch version-15 \
  --python $(which python3) \
  frappe-bench

cd ~/frappe-bench

bench get-app --branch version-15 erpnext
```

> 네트워크 속도에 따라 10~30분 소요됩니다.

---

## 5단계 — food_mes_kr 앱 추가

### 방법 A — Git 저장소가 있는 경우 (권장)

```bash
cd ~/frappe-bench
bench get-app https://github.com/<your-org>/food_mes_kr.git
```

### 방법 B — 폴더를 직접 복사하는 경우

원본 컴퓨터에서:

```bash
# 원본 컴퓨터에서 앱 폴더를 압축
tar -czf food_mes_kr.tar.gz -C ~/frappe-bench/apps food_mes_kr
```

새 컴퓨터에서:

```bash
# 압축 파일을 ~/frappe-bench/apps/ 에 풀기
tar -xzf food_mes_kr.tar.gz -C ~/frappe-bench/apps/

# 앱 의존성 설치
cd ~/frappe-bench
./env/bin/pip install -e apps/food_mes_kr
```

---

## 6단계 — 사이트 생성

```bash
cd ~/frappe-bench

bench new-site dev.localhost \
  --mariadb-root-password <2단계에서_설정한_비밀번호> \
  --admin-password admin \
  --db-name frappe_dev

# ERPNext 설치
bench --site dev.localhost install-app erpnext

# food_mes_kr 설치
bench --site dev.localhost install-app food_mes_kr

# 개발 모드 활성화
bench --site dev.localhost set-config developer_mode 1
bench --site dev.localhost clear-cache
```

---

## 7단계 — ERPNext 초기 설정 (브라우저)

서버를 기동합니다:

```bash
cd ~/frappe-bench
bench start
```

브라우저에서 `http://dev.localhost:8000` 접속 후 `Administrator / admin` 으로 로그인합니다.

처음 접속 시 설정 마법사가 나타납니다. 아래 값으로 입력합니다:

| 항목 | 값 |
|------|----|
| Language | Korean (한국어) 또는 English |
| Country | Korea, Republic of |
| Company Name | **Good F&B (Demo)** |
| Company Abbreviation | **GFD** |
| Currency | KRW |
| Chart of Accounts | Standard |

> **Company Name과 Abbreviation을 정확히 입력해야 합니다.**  
> 이후 시연 데이터에서 창고명(`원료창고 - GFD` 등)이 이 약어를 사용합니다.

마법사를 완료한 뒤 다음 모듈이 활성화되어 있는지 확인합니다:
- Manufacturing
- Stock
- Buying

---

## 8단계 — 시연 데이터 생성

새 터미널을 열고 아래 명령어를 순서대로 실행합니다.

```bash
cd ~/frappe-bench

# 1. 기본 데이터 (품목, 창고, BOM, 작업지시서)
bench --site dev.localhost execute food_mes_kr.food_mes_kr.demo_seed.run

# 2. 바코드 등록
bench --site dev.localhost execute food_mes_kr.food_mes_kr.setup_barcodes.run

# 3. FEFO 경고 테스트용 재고 (시연 #3)
bench --site dev.localhost execute food_mes_kr.food_mes_kr.demo_seed.create_fefo_test_stock

# 4. 역추적 시연용 제조 이력 (시연 #5)
bench --site dev.localhost execute food_mes_kr.food_mes_kr.demo_seed.create_trace_demo

# 5. 원료 배치 공급업자 등록 (시연 #5 Supplier 컬럼)
bench --site dev.localhost execute food_mes_kr.food_mes_kr.demo_seed.setup_trace_suppliers
```

각 명령어가 에러 없이 완료되면 다음 단계로 넘어갑니다.

---

## 9단계 — 동작 확인

```bash
# 서버 응답 확인
curl -s -o /dev/null -w "%{http_code}" http://dev.localhost:8000
# 200 이면 정상

# 품목 생성 확인
bench --site dev.localhost execute frappe.db.sql \
  --kwargs '{"query": "SELECT name FROM `tabItem` WHERE item_code LIKE \"FG-%\" OR item_code LIKE \"RM-%\"", "as_dict": 1}'
# FG-HELLO-APPLE, RM-APPLE-CONC 등이 보이면 정상

# 역추적 데이터 확인
bench --site dev.localhost execute frappe.db.sql \
  --kwargs '{"query": "SELECT batch_id, item FROM `tabBatch` WHERE batch_id LIKE \"TRACE%\" OR batch_id LIKE \"260%\"", "as_dict": 1}'
# TRACE-APPLE-001, 260513-L1-001 등이 보이면 정상
```

문제없으면 `DEMO_GUIDE.md` 를 열고 시연을 진행합니다.

---

## 문제 해결

### `bench` 명령어를 찾을 수 없음

```bash
export PATH="$HOME/.local/bin:$PATH"
# 또는
source ~/.bashrc
```

### MariaDB 접속 오류 (`Access denied`)

```bash
sudo mysql -u root
# MariaDB 프롬프트에서:
ALTER USER 'root'@'localhost' IDENTIFIED BY '새비밀번호';
FLUSH PRIVILEGES;
```

### `bench start` 후 포트 8000 접속 안 됨 (WSL2)

WSL2에서는 `localhost` 대신 실제 IP가 필요할 수 있습니다:

```bash
hostname -I | awk '{print $1}'
# 출력된 IP로 http://<IP>:8000 접속
```

또는 Windows hosts 파일(`C:\Windows\System32\drivers\etc\hosts`)에 추가:

```
127.0.0.1  dev.localhost
```

### `demo_seed.run` 실행 시 `회사가 먼저 셋업되어 있어야 합니다`

7단계 설정 마법사를 완료한 뒤 다시 실행합니다.  
마법사를 건너뛴 경우 브라우저에서 `Setup Wizard`를 검색해 재실행합니다.

### `FEFO 경고 안 뜸` / `Backward Trace 결과 없음`

해당 seed 명령어를 다시 실행합니다. seed 함수는 모두 멱등(idempotent)이므로 중복 실행해도 안전합니다.

---

## 버전 참고

이 가이드는 아래 버전에서 검증되었습니다.

| 컴포넌트 | 버전 |
|---------|------|
| Frappe | v15.107.0 |
| ERPNext | v15.106.0 |
| Python | 3.12 |
| Node.js | 18 |
| MariaDB | 10.11 |
| Redis | 7.0 |
| wkhtmltopdf | 0.12.6.1 (patched qt) |
