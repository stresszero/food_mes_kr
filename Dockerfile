FROM frappe/erpnext:version-15

# bench get-app 을 사용해 앱을 등록한다.
# pip install + apps.txt 추가를 bench 가 직접 처리하므로
# 수동으로 apps.txt 를 조작할 필요가 없다.
RUN bench get-app https://github.com/stresszero/food_mes_kr.git
