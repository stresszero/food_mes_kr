# food_mes_kr Docker 시연 환경 구축 가이드

Docker를 사용하면 Python, Node.js, MariaDB, Redis를 직접 설치하지 않아도 됩니다.  
Docker만 설치된 컴퓨터라면 어디서든 동일한 환경을 구축할 수 있습니다.

---

## 방법 비교

| 항목 | 수동 설치 | 방법 A: 볼륨 마운트 | 방법 B: 커스텀 이미지 | **방법 C: 저장소 포함 (권장)** |
|------|-----------|--------------------|--------------------|-------------------------------|
| 준비 시간 | 1~2시간 | 20~30분 | 10분 (이미지 배포 후) | **5분** |
| 필요 조건 | 패키지 직접 설치 | Docker + 앱 폴더 복사 | Docker + 이미지 pull | **Docker만** |
| Git 저장소 필요 | 불필요 | 불필요 | 필요 | **필요** |
| 설치 명령 | 다단계 | 다단계 | `docker compose up` | **`git clone` + `docker compose up` + `./setup.sh`** |
| 브라우저 마법사 | 필요 | 필요 | 필요 | **불필요 (자동화)** |
| 운영체제 | Ubuntu/WSL2 | 모든 OS | 모든 OS | **모든 OS** |

**추천**: Git 저장소가 있다면 → **방법 C**  
**Git 없이 지금 당장** → 방법 A

---

## 공통 사전 준비 — Docker 설치

### macOS / Windows

[Docker Desktop](https://www.docker.com/products/docker-desktop/) 설치 후 실행.  
Windows는 WSL2 백엔드를 활성화합니다.

### Ubuntu

```bash
curl -fsSL https://get.docker.com | sh
sudo usermod -aG docker $USER
# 로그아웃 후 다시 로그인
```

설치 확인:

```bash
docker --version        # Docker version 26.x.x
docker compose version  # Docker Compose version v2.x.x
```

---

---

## 방법 A — 볼륨 마운트 (파일 복사, Git 불필요)

### 개요

원본 컴퓨터의 `food_mes_kr` 폴더를 새 컴퓨터로 복사한 뒤,  
Docker 컨테이너가 그 폴더를 직접 읽도록 마운트하는 방식입니다.

```
[새 컴퓨터]
  ~/food_mes_kr/          ← 복사한 앱 폴더
  ~/frappe-docker/        ← frappe 공식 Docker 저장소
```

---

### A-1. frappe_docker 클론

```bash
git clone https://github.com/frappe/frappe_docker ~/frappe-docker
cd ~/frappe-docker
```

### A-2. food_mes_kr 폴더 복사

**원본 컴퓨터에서** 앱 폴더를 압축합니다:

```bash
tar -czf food_mes_kr.tar.gz -C ~/frappe-bench/apps food_mes_kr
```

압축 파일을 새 컴퓨터로 옮긴 뒤 풉니다 (USB, scp, 공유 폴더 등):

```bash
mkdir -p ~/food_mes_kr
tar -xzf food_mes_kr.tar.gz -C ~/
# 결과: ~/food_mes_kr/ 폴더 생성
```

### A-3. 환경 파일 작성

```bash
cd ~/frappe-docker

cat > demo.env <<'EOF'
FRAPPE_VERSION=version-15
ERPNEXT_VERSION=version-15
DB_PASSWORD=admin
SITE_NAME=dev.localhost
EOF
```

### A-4. Docker Compose 파일 작성

```bash
cat > compose.demo.yaml <<'EOF'
version: "3"

x-customizable-image: &customizable_image
  image: frappe/erpnext:version-15

x-depends-on-configurator: &depends_on_configurator
  depends_on:
    configurator:
      condition: service_completed_successfully

services:
  configurator:
    <<: *customizable_image
    command: >
      bash -c "
        ls apps/frappe && echo frappe found;
        bench set-config -g db_host mariadb;
        bench set-config -gp db_port 3306;
        bench set-config -g redis_cache redis://redis-cache:6379;
        bench set-config -g redis_queue redis://redis-queue:6379;
        bench set-config -g redis_socketio redis://redis-queue:6379;
        bench set-config -gp socketio_port 9000;
      "
    environment:
      DB_HOST: mariadb
      DB_PORT: "3306"
      REDIS_CACHE: redis://redis-cache:6379
      REDIS_QUEUE: redis://redis-queue:6379
      ADMIN_PASSWORD: "${DB_PASSWORD}"
    volumes:
      - sites:/home/frappe/frappe-bench/sites
      - logs:/home/frappe/frappe-bench/logs
      - ~/food_mes_kr:/home/frappe/frappe-bench/apps/food_mes_kr

  backend:
    <<: *customizable_image
    <<: *depends_on_configurator
    volumes:
      - sites:/home/frappe/frappe-bench/sites
      - logs:/home/frappe/frappe-bench/logs
      - ~/food_mes_kr:/home/frappe/frappe-bench/apps/food_mes_kr

  frontend:
    image: frappe/erpnext:version-15
    command: nginx-entrypoint.sh
    environment:
      BACKEND: backend:8000
      FRAPPE_SITE_NAME_HEADER: dev.localhost
      SOCKETIO: websocket:9000
      UPSTREAM_REAL_IP_ADDRESS: 127.0.0.1
      UPSTREAM_REAL_IP_RECURSIVE: "off"
      UPSTREAM_REAL_IP_HEADER: X-Forwarded-For
      PROXY_READ_TIMEOUT: 120
      CLIENT_MAX_BODY_SIZE: 50m
    volumes:
      - sites:/home/frappe/frappe-bench/sites
      - logs:/home/frappe/frappe-bench/logs
    ports:
      - "8080:8080"
    <<: *depends_on_configurator

  websocket:
    <<: *customizable_image
    command: node /home/frappe/frappe-bench/apps/frappe/socketio.js
    volumes:
      - sites:/home/frappe/frappe-bench/sites
      - logs:/home/frappe/frappe-bench/logs
    <<: *depends_on_configurator

  scheduler:
    <<: *customizable_image
    command: bench schedule
    volumes:
      - sites:/home/frappe/frappe-bench/sites
      - logs:/home/frappe/frappe-bench/logs
      - ~/food_mes_kr:/home/frappe/frappe-bench/apps/food_mes_kr
    <<: *depends_on_configurator

  worker-short:
    <<: *customizable_image
    command: bench worker --queue short,default
    volumes:
      - sites:/home/frappe/frappe-bench/sites
      - logs:/home/frappe/frappe-bench/logs
      - ~/food_mes_kr:/home/frappe/frappe-bench/apps/food_mes_kr
    <<: *depends_on_configurator

  worker-long:
    <<: *customizable_image
    command: bench worker --queue long,default,short
    volumes:
      - sites:/home/frappe/frappe-bench/sites
      - logs:/home/frappe/frappe-bench/logs
      - ~/food_mes_kr:/home/frappe/frappe-bench/apps/food_mes_kr
    <<: *depends_on_configurator

  mariadb:
    image: mariadb:10.6
    command:
      - --character-set-server=utf8mb4
      - --collation-server=utf8mb4_unicode_ci
      - --skip-character-set-client-handshake
      - --skip-innodb-read-only-compressed
    environment:
      MYSQL_ROOT_PASSWORD: "${DB_PASSWORD}"
    volumes:
      - mariadb-data:/var/lib/mysql

  redis-cache:
    image: redis:7-alpine

  redis-queue:
    image: redis:7-alpine

volumes:
  mariadb-data:
  sites:
  logs:
EOF
```

### A-5. 컨테이너 기동

```bash
cd ~/frappe-docker
docker compose --env-file demo.env -f compose.demo.yaml up -d

# 기동 확인 (모든 서비스 healthy 상태 대기, 약 1~2분)
docker compose --env-file demo.env -f compose.demo.yaml ps
```

### A-6. 사이트 생성 및 앱 설치

```bash
# 사이트 생성
docker compose --env-file demo.env -f compose.demo.yaml \
  exec backend \
  bench new-site dev.localhost \
    --mariadb-root-password admin \
    --admin-password admin \
    --db-name frappe_dev

# ERPNext 설치
docker compose --env-file demo.env -f compose.demo.yaml \
  exec backend \
  bench --site dev.localhost install-app erpnext

# food_mes_kr 의존성 설치 및 앱 설치
docker compose --env-file demo.env -f compose.demo.yaml \
  exec backend \
  bash -c "pip install -e apps/food_mes_kr && bench --site dev.localhost install-app food_mes_kr"

# 개발 모드
docker compose --env-file demo.env -f compose.demo.yaml \
  exec backend \
  bench --site dev.localhost set-config developer_mode 1
```

### A-7. ERPNext 초기 설정 (브라우저)

`http://localhost:8080` 에 접속 → `Administrator / admin` 으로 로그인.

설정 마법사에서 아래와 같이 입력합니다:

| 항목 | 값 |
|------|----|
| Country | Korea, Republic of |
| Company Name | **Good F&B (Demo)** |
| Company Abbreviation | **GFD** |
| Currency | KRW |

### A-8. 시연 데이터 생성

```bash
EXEC="docker compose --env-file demo.env -f compose.demo.yaml exec backend bench --site dev.localhost execute"

$EXEC food_mes_kr.food_mes_kr.demo_seed.run
$EXEC food_mes_kr.food_mes_kr.setup_barcodes.run
$EXEC food_mes_kr.food_mes_kr.demo_seed.create_fefo_test_stock
$EXEC food_mes_kr.food_mes_kr.demo_seed.create_trace_demo
$EXEC food_mes_kr.food_mes_kr.demo_seed.setup_trace_suppliers
```

완료되면 `DEMO_GUIDE.md` 기준으로 시연을 진행합니다.

---

---

## 방법 B — 커스텀 Docker 이미지 (Git 저장소 필요)

> food_mes_kr이 GitHub 등 공개/비공개 Git 저장소에 올라가 있을 때 사용합니다.  
> 이미지를 한 번 빌드해두면 다른 컴퓨터에서는 `docker compose up` 만으로 끝납니다.

### B-1. apps.json 작성

```bash
cd ~/frappe-docker

cat > apps.json <<EOF
[
  {
    "url": "https://github.com/frappe/erpnext",
    "branch": "version-15"
  },
  {
    "url": "https://github.com/<your-org>/food_mes_kr",
    "branch": "main"
  }
]
EOF
```

비공개 저장소라면 GitHub Personal Access Token을 URL에 포함시킵니다:

```json
{
  "url": "https://<TOKEN>@github.com/<your-org>/food_mes_kr",
  "branch": "main"
}
```

### B-2. 커스텀 이미지 빌드

```bash
cd ~/frappe-docker

docker build \
  --no-cache \
  --build-arg=FRAPPE_PATH=https://github.com/frappe/frappe \
  --build-arg=FRAPPE_BRANCH=version-15 \
  --secret=id=apps_json,src=apps.json \
  --tag=food-mes-demo:latest \
  --file=images/layered/Containerfile .
```

> 네트워크 속도에 따라 10~20분 소요됩니다.

### B-3. 이미지 배포 (선택)

Docker Hub 또는 사내 레지스트리에 올려두면 다른 컴퓨터에서 pull해서 사용할 수 있습니다:

```bash
docker tag food-mes-demo:latest <your-dockerhub-id>/food-mes-demo:latest
docker push <your-dockerhub-id>/food-mes-demo:latest
```

### B-4. 환경 파일 작성

```bash
cat > custom.env <<'EOF'
CUSTOM_IMAGE=food-mes-demo
CUSTOM_TAG=latest
DB_PASSWORD=admin
SITE_NAME=dev.localhost
EOF
```

### B-5. 컨테이너 기동 (빌드한 이미지로)

```bash
docker compose \
  --env-file custom.env \
  -f compose.yaml \
  -f overrides/compose.mariadb.yaml \
  -f overrides/compose.redis.yaml \
  -f overrides/compose.noproxy.yaml \
  up -d
```

다른 컴퓨터에서 이미지를 pull해서 쓰는 경우 `custom.env`의 `CUSTOM_IMAGE`를 레지스트리 주소로 변경하면 됩니다.

### B-6. 사이트 생성 및 앱 설치

```bash
docker compose exec backend \
  bench new-site dev.localhost \
    --mariadb-root-password admin \
    --admin-password admin \
    --db-name frappe_dev

docker compose exec backend bench --site dev.localhost install-app erpnext
docker compose exec backend bench --site dev.localhost install-app food_mes_kr
docker compose exec backend bench --site dev.localhost set-config developer_mode 1
```

### B-7. ERPNext 초기 설정 + 시연 데이터

방법 A의 A-7, A-8 단계와 동일합니다.

---

---

## 방법 C — 저장소에 compose 포함 (Git 클론 후 바로 실행) ★ 권장

> `compose.yml`, `Dockerfile`, `setup.sh` 가 이미 저장소에 포함되어 있습니다.  
> Git 저장소만 있으면 Docker 외 아무것도 설치하지 않아도 됩니다.

### 전체 흐름

```
git clone → docker compose up -d → ./setup.sh → 시연 시작
```

브라우저 설정 마법사 없이 `setup.sh` 하나로 완전 자동화됩니다.

---

### C-1. 저장소 클론

```bash
git clone https://github.com/<your-org>/food_mes_kr
cd food_mes_kr
```

### C-2. 컨테이너 기동 (최초 1회 이미지 빌드 포함)

```bash
docker compose up -d
```

처음 실행 시 `frappe/erpnext:version-15` 베이스 이미지 위에 food_mes_kr을 포함한  
이미지를 자동으로 빌드합니다. 네트워크 속도에 따라 **5~15분** 소요됩니다.

이후 실행부터는 캐시된 이미지를 사용하므로 수초 내 기동됩니다.

빌드 진행 상황 확인:

```bash
docker compose logs -f configurator
# "bench set-config" 출력 후 종료되면 준비 완료
```

### C-3. 시연 환경 초기화 (최초 1회)

```bash
./setup.sh
```

아래 작업이 자동으로 순서대로 실행됩니다:

| 단계 | 작업 |
|------|------|
| 1 | MariaDB · 백엔드 준비 대기 |
| 2 | `dev.localhost` 사이트 생성 |
| 3 | ERPNext · food_mes_kr 앱 설치 |
| 4 | 회사·계정과목 생성 (브라우저 마법사 대체) |
| 5 | 시연 데이터 5종 생성 |

완료 메시지 예시:

```
╔══════════════════════════════════════╗
║   ✅  설치 완료!                     ║
╠══════════════════════════════════════╣
║  URL  : http://localhost:8080        ║
║  계정 : Administrator / admin        ║
╚══════════════════════════════════════╝
```

### C-4. 시연 시작

브라우저에서 `http://localhost:8080` 접속 → `Administrator / admin` 로그인.  
`DEMO_GUIDE.md` 의 시연 #1부터 진행합니다.

---

### setup.sh 재실행 안전성

`setup.sh` 는 멱등(idempotent)으로 작성되어 있습니다.  
이미 설정된 단계는 자동으로 건너뛰므로 **재실행해도 안전합니다**.

```bash
# 컨테이너를 재시작한 경우
docker compose up -d
./setup.sh   # 이미 된 단계는 건너뜀
```

### 코드 변경 후 이미지 재빌드

food_mes_kr 코드를 수정한 경우 이미지를 다시 빌드합니다:

```bash
docker compose build
docker compose up -d
```

---

## 컨테이너 관리 명령어

방법 C 기준 (`compose.yml` 이 현재 디렉터리에 있는 경우):

```bash
# 중지 (데이터 보존)
docker compose stop

# 재시작
docker compose start

# 백엔드 로그 실시간 확인
docker compose logs -f backend

# 완전 삭제 (데이터 포함, 초기화)
docker compose down -v
```

방법 A 사용 시에는 명령어에 `--env-file demo.env -f compose.demo.yaml` 을 추가합니다.

---

## 문제 해결

### `port 8080 is already in use`

다른 프로세스가 8080을 사용 중입니다. `compose.yml`의 ports를 변경합니다:

```yaml
ports:
  - "8081:8080"  # 왼쪽 숫자만 변경
```

### `food_mes_kr` 앱이 메뉴에 안 보임

```bash
docker compose exec backend bench --site dev.localhost clear-cache
```

브라우저 새로고침 후 확인합니다.

### `setup.sh` 실행 중 `bench: command not found`

setup.sh는 Docker 컨테이너 내부의 bench를 호출합니다.  
`docker compose up -d` 로 컨테이너가 먼저 기동되어 있어야 합니다.

### MariaDB 연결 실패 / `setup.sh` 가 무한 대기

```bash
docker compose ps
# mariadb 상태가 healthy 인지 확인

docker compose logs mariadb
# 오류 메시지 확인
```

컨테이너가 정상이면 1~2분 대기 후 setup.sh가 자동으로 이어집니다.

### `bootstrap_site` 실패 — 설정 마법사 오류

setup.sh 실행 중 bootstrap_site 단계에서 오류가 나면 수동으로 진행합니다:

```bash
# 브라우저에서 http://localhost:8080 접속 → 설정 마법사 완료 후
docker compose exec -T backend bench --site dev.localhost execute \
  food_mes_kr.food_mes_kr.demo_seed.run
# 이후 나머지 seed 명령어 실행
```

### WSL2에서 `localhost:8080` 접속 안 됨

Windows 브라우저에서는 `localhost:8080`으로 접속합니다 (WSL2는 자동 포트 포워딩).  
안 되면 WSL2 IP를 직접 사용합니다:

```bash
wsl hostname -I | awk '{print $1}'
# 출력된 IP로 http://<IP>:8080 접속
```
