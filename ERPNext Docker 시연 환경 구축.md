# ERPNext Docker 시연 환경 구축 가이드

Docker를 사용하면 Python, Node.js, MariaDB, Redis를 직접 설치하지 않아도 됩니다.  
Docker만 설치된 컴퓨터라면 어디서든 동일한 환경을 구축할 수 있습니다.

## 사전 준비 — Docker 설치

### Windows
- Docker 설치 전 WSL2 및 Ubuntu 배포판을 설치해야 합니다.
- 윈도우에서 [Docker Desktop](https://www.docker.com/products/docker-desktop/) 설치.  
- 설치 후 Docker Desktop 실행 → Settings → General
  - ✅ Use the WSL 2 based engine 체크
- Settings → Resources → WSL Integration
  - ✅ 사용 중인 Ubuntu 배포판 토글 활성화 (예: Ubuntu-22.04)

### Ubuntu

```bash
# Ubuntu 터미널에서 docker 설치 및 버전 확인
docker --version
docker run hello-world
```

## 방법 C: Docker 시연 환경 구축 방법

> `compose.yml`, `Dockerfile`, `setup.sh` 가 이미 github 저장소에 포함되어 있습니다.  
> Git 저장소만 있으면 Docker 외 아무것도 설치하지 않아도 됩니다.

### 전체 흐름

```
git clone → docker compose up -d → ./setup.sh → 시연 시작
```

ERPNext의 초기 설정 과정없이 `setup.sh` 하나로 완전 자동화됩니다.

---

### C-1. 저장소 클론

```bash
cd ~
git clone https://github.com/stresszero/food_mes_kr
cd food_mes_kr
```

### C-2. 컨테이너 기동 (최초 1회 이미지 빌드 포함)

```bash
docker compose up -d
```

처음 실행 시 `frappe/erpnext:version-15` 베이스 이미지 위에 food_mes_kr을 포함한  
이미지를 자동으로 빌드합니다. 네트워크 속도에 따라 **5~15분** 소요됩니다.

이후 실행부터는 캐시된 이미지를 사용하므로 수초 내 기동됩니다.


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

food_mes_kr 코드를 수정한 경우 Docker 이미지를 다시 빌드합니다:

```bash
docker compose build
docker compose up -d
```

fixtures(커스텀 번역, Custom Field 등) 변경이 포함된 경우 migrate를 추가로 실행합니다:

```bash
docker compose exec -T backend bench --site dev.localhost migrate
```

> `bench install-app`은 이미 설치된 앱을 건너뛰므로 fixtures 재동기화가 필요할 때는
> `bench migrate`를 직접 실행해야 합니다.

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
