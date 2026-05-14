FROM frappe/erpnext:version-15

# food_mes_kr 앱 복사 및 설치
# .dockerignore 가 __pycache__, *.egg-info 등을 제외한다
COPY --chown=frappe:frappe . /home/frappe/frappe-bench/apps/food_mes_kr/

RUN pip install --no-cache-dir -e /home/frappe/frappe-bench/apps/food_mes_kr
