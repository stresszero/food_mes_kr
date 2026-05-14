# TROUBLESHOOTING

ERPNext + 커스텀 앱 개발에서 자주 만나는 문제와 해결법.

---

## 환경 / 설치 단계

### `bench init` 실패 — Python 버전 불일치

```
ERROR: Could not find a version that satisfies the requirement frappe...
```

**원인**: ERPNext v15는 Python 3.11이 권장. 3.10 이하 또는 3.13에서는 여러 의존성이 깨짐.
**해결**:
```bash
which python3.11 || apt install python3.11 python3.11-venv
bench init --python python3.11 ...
```
devcontainer를 쓰면 이 문제가 거의 발생하지 않음.

### `bench start` 후 화면 접속 안 됨

**점검 순서**:
1. `bench start` 로그에서 모든 프로세스(web, worker, scheduler, redis)가 살아있는지
2. `/etc/hosts`에 `127.0.0.1 dev.localhost` 있는지
3. `bench --site dev.localhost set-config developer_mode 1` 적용 후 `bench restart`
4. 8000 포트 충돌 (다른 프로세스 점유)

### 한글 깨짐 (PDF 출력)

**원인**: wkhtmltopdf에 한글 폰트 없음.
**해결**:
```bash
apt install fonts-noto-cjk fonts-nanum
fc-cache -fv
```
컨테이너 재시작.

### `mariadb: command not found`

devcontainer 안에서 `bench --site dev.localhost mariadb` 실행 시.
**해결**: `apt install mariadb-client` 또는 `bench --site dev.localhost mysql`.

---

## 앱 설치 / 마이그레이션

### `Module Not Found: food_mes_kr`

**원인**: `apps/food_mes_kr` 안에 `setup.py`가 없거나, bench가 앱을 register 안 함.
**해결**:
```bash
cd ~/work/frappe-bench
bench setup requirements
# apps.txt 확인
cat sites/apps.txt
# 만약 food_mes_kr 없으면 추가
echo "food_mes_kr" >> sites/apps.txt
bench --site dev.localhost migrate
```

### Custom Field가 안 보임

**원인**: fixture가 import 안 됨.
**점검**:
```bash
# Custom Field가 DB에 들어왔나
bench --site dev.localhost mariadb
> SELECT name, dt, fieldname FROM `tabCustom Field` WHERE module='Food Mes Kr';

# 안 들어왔으면 강제 import
bench --site dev.localhost console
>>> import frappe
>>> from frappe.core.doctype.data_import.data_import import import_doc
>>> # 또는 직접:
>>> frappe.reload_doc("food_mes_kr", "fixtures", "custom_field")
```

### 마이그레이션이 영원히 멈춤

**원인**: 보통 후크 함수에서 무한루프 또는 외부 API 호출 timeout.
**진단**:
```bash
# 마이그레이션 상태 강제 종료 후
bench --site dev.localhost console
>>> frappe.db.set_global("__migration_in_progress", 0)
>>> frappe.db.commit()

# 로그 확인
tail -f logs/web.error.log
```

### `OperationalError: (1054, "Unknown column ...")`

**원인**: DocType 정의는 있으나 DB 스키마와 불일치.
**해결**:
```bash
bench --site dev.localhost migrate --skip-failing
# 또는 특정 DocType만 reload
bench --site dev.localhost reload-doctype "Work Order"
```

---

## 후크 / 서버 스크립트

### 후크가 동작하지 않음

**진단 1**: 후크 등록 확인
```bash
bench --site dev.localhost console
>>> import frappe
>>> hooks = frappe.get_hooks("doc_events")
>>> hooks.get("Work Order")
# 우리 함수가 보여야 함
```

**진단 2**: 모듈 import 가능 여부
```bash
>>> from food_mes_kr.food_mes_kr.server_scripts.work_order_lot import assign_production_lot_no
# ImportError가 뜨면 경로 또는 syntax 문제
```

**진단 3**: bench 재시작
```bash
# Python 코드 변경은 bench start가 자동 reload하지만 가끔 안 됨
bench restart
# 또는 watch만 끊고 다시:
# Ctrl+C in `bench start` terminal, then `bench start`
```

### `frappe.permissions.PermissionError` in 후크

**원인**: 자동 트리거된 후크는 시스템 사용자로 동작하지만, 일부 작업은 명시적 권한 필요.
**해결**:
```python
# 후크 함수 안에서
frappe.flags.ignore_permissions = True
# 또는
doc.flags.ignore_permissions = True
```
(보안 영향 검토 필요)

### Server Script가 실행되지 않음

**원인**: ERPNext에는 두 종류 "Server Script"가 있음:
1. **DocType 안의 컨트롤러 / hooks.py 등록 함수** — 우리가 쓰는 방식
2. **Server Script DocType** — 관리자 UI에서 등록하는 방식 (다른 것)

우리 코드는 1번 방식. hooks.py 등록 + Python 파일 + bench restart가 모두 되어 있어야.

---

## 테스트

### `frappe.tests.utils.FrappeTestCase` import 안 됨

**원인**: ERPNext 테스트는 frappe context 필요.
**해결**: 항상 `bench --site` 안에서 실행.
```bash
# 잘못된 예 (실패)
python -m unittest food_mes_kr.test_xxx

# 올바른 예
bench --site dev.localhost run-tests --app food_mes_kr --module food_mes_kr.food_mes_kr.test_xxx
```

### 테스트 사이트 별도 분리 권장

운영 사이트(dev.localhost)에서 직접 테스트 돌리면 데이터 오염. 테스트 전용 사이트 만드세요:
```bash
bench new-site test.localhost --admin-password admin
bench --site test.localhost install-app food_mes_kr
bench --site test.localhost run-tests --app food_mes_kr
```

### 테스트가 너무 느림

**팁**: `--profile` 옵션으로 병목 찾기. 보통 fixture import가 가장 무거움. 테스트 fixture는 최소화.

---

## Print Format / PDF

### PDF 출력 시 빈 페이지

**원인**: `<style>`이 `@page` 사이즈를 지정했는데 `@media print` 컨텍스트가 wkhtmltopdf와 안 맞음.
**해결**: ERPNext의 Print Format은 `--page-size A4`를 cli 인자로 받으므로, `@page` 대신 일반 `body { width: ...mm }` 사용.

### 한글 폰트가 시스템 기본으로 나옴 (예쁘지 않음)

**해결**:
```html
<style>
  body, * { font-family: 'Noto Sans KR', 'Apple SD Gothic Neo', sans-serif !important; }
</style>
```
운영 서버에 Noto Sans KR 설치 필수.

---

## 데이터 / DB

### "Cannot delete because referenced by ..."

ERPNext는 참조 무결성 강함. 강제 삭제 필요 시:
```python
frappe.db.set_value("Work Order", "WO-XXX", "docstatus", 2)
frappe.delete_doc("Work Order", "WO-XXX", ignore_permissions=True, force=True)
```
**주의**: 운영 데이터에 절대 쓰지 말 것.

### 시퀀스(LOT 번호 SEQ)가 깨짐

**원인**: 동시성 사고 또는 수동 입력으로 형식 불일치 데이터 발생.
**복구**:
```python
bench --site dev.localhost console
>>> import frappe
>>> # 형식 안 맞는 production_lot_no 찾기
>>> wo_list = frappe.db.sql("""
...     SELECT name, production_lot_no FROM `tabWork Order`
...     WHERE production_lot_no NOT REGEXP '^[0-9]{6}-[A-Z0-9]{1,6}-[0-9]{3,}$'
... """)
>>> for name, lot in wo_list:
...     print(name, lot)
```
규칙 위반 데이터를 수동 정리.

### Batch ID에 공백/특수문자

**원인**: 외부 시스템에서 import한 LOT 번호.
**해결**: import 시 검증 규칙 추가 (T1.4의 import_validator.py).

---

## Claude Code 사용 중

### Claude가 ERPNext core 파일을 수정하려 할 때

**대응**: `CLAUDE.md`의 Hard Rule 2.1을 다시 보여주세요. 또는 명시적으로 "core 수정 금지, Custom Field 또는 hook으로 해결"이라고 다시 강조.

### Claude가 존재하지 않는 Frappe API를 호출할 때

자주 발생. **검증법**:
```bash
# Claude가 제안한 API가 실재하는지 확인
bench --site dev.localhost console
>>> import frappe
>>> hasattr(frappe, '<api 이름>')
```

또는 Claude에게 "이 API가 ERPNext v15에 실재하는지 `apps/frappe/frappe/__init__.py`에서 확인해줘"라고 지시.

### Claude가 너무 많은 파일을 한 번에 변경

**대응**: 다음 세션에서 작업 범위를 더 좁게 명시.
```
이번 task에서는 다음 파일만 수정 또는 생성:
- food_mes_kr/food_mes_kr/server_scripts/<name>.py
- food_mes_kr/hooks.py (등록만)
- 단위 테스트 1개
다른 파일 건드리지 말 것.
```

---

## 운영 / 배포

### 운영 사이트에서 코드 수정 후 변경 사항이 반영 안 됨

운영은 `bench start`(개발 서버)가 아니라 `nginx + supervisord` 환경.
```bash
bench restart
# 또는
sudo supervisorctl restart all
```

### 운영 DB 스키마와 개발 DB 스키마 불일치

**원인**: 개발에서는 적용했지만 운영에 migrate 안 함.
**해결**: 배포 절차에 항상 `bench --site <prod> migrate` 포함. CI/CD로 자동화.

### "Site is read-only" 에러

`maintenance_mode=1`이 site_config에 남아있음.
```bash
bench --site <site> set-maintenance-mode off
```
