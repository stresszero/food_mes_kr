#!/usr/bin/env bash
# food_mes_kr 시연 환경 최초 설정 스크립트
# 실행 전 `docker compose up -d` 가 완료되어 있어야 합니다.
#
# 사용법: ./setup.sh
# 재실행: 멱등(idempotent) — 이미 설정된 경우 해당 단계를 건너뜁니다.

set -euo pipefail

# .env 파일이 있으면 로드 (없으면 기본값 사용)
if [ -f .env ]; then
    set -a; source .env; set +a
fi

DB_PASSWORD="${DB_PASSWORD:-admin}"
ADMIN_PASSWORD="${ADMIN_PASSWORD:-admin}"

BENCH="docker compose exec -T backend bench"

# ─────────────────────────────────────────────
# 0. 컨테이너 준비 대기
# ─────────────────────────────────────────────

echo ""
echo "╔══════════════════════════════════════╗"
echo "║   food_mes_kr  Demo Setup            ║"
echo "╚══════════════════════════════════════╝"
echo ""

echo "⏳ MariaDB 준비 대기..."
until docker compose exec -T mariadb mariadb-admin ping -h localhost --password="${DB_PASSWORD}" --silent 2>/dev/null; do
    printf "."
    sleep 3
done
echo " ✓"

echo "⏳ Frappe 백엔드 준비 대기..."
until docker compose exec -T backend bench version &>/dev/null 2>&1; do
    printf "."
    sleep 3
done
echo " ✓"

echo ""

# ─────────────────────────────────────────────
# 1. 사이트 생성
# ─────────────────────────────────────────────

# 사이트 디렉터리 존재 여부로 판단 (bench 명령 의존 없음)
if docker compose exec -T backend test -d sites/dev.localhost; then
    echo "1/5 사이트가 이미 존재합니다. 건너뜀."
else
    echo "1/5 사이트 생성 중..."
    $BENCH new-site dev.localhost \
        --mariadb-root-password "${DB_PASSWORD}" \
        --admin-password "${ADMIN_PASSWORD}" \
        --db-name frappe_dev
    echo "    ✓ dev.localhost 생성"
fi

# ─────────────────────────────────────────────
# 2. 앱 설치
# ─────────────────────────────────────────────

echo "2/5 앱 설치 중..."

# food_mes_kr 이 apps.txt 에 없으면 추가 (Dockerfile 캐시 문제 대비)
docker compose exec -T backend bash -c \
    "grep -qxF food_mes_kr apps.txt || echo food_mes_kr >> apps.txt"

# bench install-app 은 이미 설치된 앱을 자체적으로 건너뜀 (멱등)
$BENCH --site dev.localhost install-app erpnext
$BENCH --site dev.localhost install-app food_mes_kr

$BENCH --site dev.localhost set-config developer_mode 1
echo "    ✓ 앱 설치 완료"

# ─────────────────────────────────────────────
# 3. 회사·기초 데이터 생성 (설정 마법사 대체)
# ─────────────────────────────────────────────

echo "3/5 ERPNext 초기화 (회사·계정과목 생성)..."
$BENCH --site dev.localhost execute \
    food_mes_kr.food_mes_kr.demo_seed.bootstrap_site
echo "    ✓ Good F&B (Demo) 준비"

# ─────────────────────────────────────────────
# 4. 시연 데이터 생성
# ─────────────────────────────────────────────

echo "4/5 기본 시연 데이터 생성 중..."
$BENCH --site dev.localhost execute food_mes_kr.food_mes_kr.demo_seed.run
$BENCH --site dev.localhost execute food_mes_kr.food_mes_kr.setup_barcodes.run
$BENCH --site dev.localhost execute food_mes_kr.food_mes_kr.demo_seed.create_fefo_test_stock
$BENCH --site dev.localhost execute food_mes_kr.food_mes_kr.demo_seed.create_trace_demo
$BENCH --site dev.localhost execute food_mes_kr.food_mes_kr.demo_seed.setup_trace_suppliers
echo "    ✓ 시연 데이터 준비"

# ─────────────────────────────────────────────
# 5. 캐시 초기화
# ─────────────────────────────────────────────

echo "5/5 캐시 초기화..."
$BENCH --site dev.localhost clear-cache
echo "    ✓"

# ─────────────────────────────────────────────
# 완료
# ─────────────────────────────────────────────

echo ""
echo "╔══════════════════════════════════════╗"
echo "║   ✅  설치 완료!                     ║"
echo "╠══════════════════════════════════════╣"
echo "║  URL  : http://localhost:8080        ║"
echo "║  계정 : Administrator / admin        ║"
echo "╚══════════════════════════════════════╝"
echo ""
echo "이제 DEMO_GUIDE.md 를 열고 시연을 시작하세요."
