"""
food_mes_kr/hooks.py

이 파일이 ERPNext와 우리 커스텀 앱을 연결하는 단일 진입점입니다.
- doc_events: 어느 DocType의 어느 이벤트에 어떤 함수를 부를지
- fixtures: bench migrate 시 자동 import할 메타데이터 (Custom Fields 등)
- 기타: 스케줄러 작업, 권한, 라우팅 등

코어 ERPNext 코드는 절대 수정하지 않고, 모두 여기서 후킹합니다.
"""

app_name = "food_mes_kr"
app_title = "Food MES Korea"
app_publisher = "Your Company"
app_description = "Korean F&B (food & beverage) MES extensions for ERPNext."
app_email = "dev@example.com"
app_license = "GPLv3"

jinja = {
    "methods": ["food_mes_kr.food_mes_kr.utils.get_qr_png"],
}

# ─────────────────────────────────────────────────────────────────
# Document Events  (= ERPNext의 라이프사이클 훅)
# ─────────────────────────────────────────────────────────────────
# - validate     : 저장 전 검증
# - before_insert: INSERT 직전
# - after_insert : INSERT 직후
# - before_save  : UPDATE/INSERT 전
# - on_submit    : Submit (docstatus 0→1)
# - on_cancel    : Cancel (docstatus 1→2)
#
# 같은 이벤트에 여러 함수를 걸려면 list로 작성. ERPNext가 순서대로 호출함.

doc_events = {
    "Work Order": {
        # WO 생성 직전에 한국식 LOT 번호 자동 채번
        "before_insert": "food_mes_kr.food_mes_kr.server_scripts.work_order_lot.assign_production_lot_no",
        # WO Submit 시 LOT 번호 확정 + 유통기한 미리 계산
        "before_submit": "food_mes_kr.food_mes_kr.server_scripts.work_order_lot.finalize_production_lot",
    },
    "Batch": {
        # Stock Entry: Manufacture 가 Batch를 자동 생성할 때, batch_id를 WO의 production_lot_no로 설정
        "before_insert": "food_mes_kr.food_mes_kr.server_scripts.batch_naming.apply_work_order_lot_to_batch",
    },
    "Stock Entry": {
        # 출고 시 FEFO 위반 검증 (선택적)
        "validate": "food_mes_kr.food_mes_kr.server_scripts.stock_entry_validate.warn_on_fefo_violation",
    },
    "Quality Inspection": {
        # CCP 이탈 시 Non Conformance 자동 생성
        "on_submit": "food_mes_kr.food_mes_kr.server_scripts.quality_inspection_hook.auto_create_non_conformance_on_ccp_failure",
    },
}

# ─────────────────────────────────────────────────────────────────
# Fixtures
# ─────────────────────────────────────────────────────────────────
# bench migrate 시 자동 import. JSON 파일은 fixtures/ 디렉토리에.
# 여기 등록하면 "어느 환경에서나 동일한 Custom Fields"가 보장됨.

fixtures = [
    {
        "doctype": "Custom Field",
        "filters": [
            ["name", "in", [
                # Item 마스터 - 식품 표시 정보
                "Item-allergen_flags",
                "Item-is_halal",
                "Item-is_organic",
                "Item-kc_food_code",
                "Item-storage_temp_min",
                "Item-storage_temp_max",
                "Item-customer_owned",
                # Workstation - 라인 코드
                "Workstation-line_code",
                # Work Order - 한국식 LOT
                "Work Order-production_lot_no",
                "Work Order-production_line",
                "Work Order-production_shift",
                "Work Order-mfg_date",
                "Work Order-best_before_date",
                # Item Quality Inspection Parameter - CCP 표시
                "Item Quality Inspection Parameter-is_ccp",
                # Non Conformance - CAPA 강화
                "Non Conformance-severity",
                "Non Conformance-due_date",
                "Non Conformance-assigned_to",
                "Non Conformance-linked_quality_inspection",
                "Non Conformance-linked_batch",
                "Non Conformance-effectiveness_check",
            ]]
        ],
    },
    {
        "doctype": "Property Setter",
        "filters": [["module", "=", "Food Mes Kr"]],
    },
    {
        "doctype": "Custom DocPerm",
        "filters": [["module", "=", "Food Mes Kr"]],
    },
]

# ─────────────────────────────────────────────────────────────────
# 스케줄러 (cron)
# ─────────────────────────────────────────────────────────────────
scheduler_events = {
    "daily": [
        # 매일 한 번: 유통기한 임박(7일 이하) Batch 알림
        "food_mes_kr.food_mes_kr.tasks.notify_expiring_batches",
    ],
    "hourly": [
        # 매시간: HACCP 모니터링 누락된 작업지시 알림
        # "food_mes_kr.food_mes_kr.tasks.check_haccp_monitoring_gaps",
    ],
}

# ─────────────────────────────────────────────────────────────────
# Permissions / Roles
# ─────────────────────────────────────────────────────────────────
# Food Safety Manager 같은 신규 Role은 fixture로 정의하고 여기서 참조

# ─────────────────────────────────────────────────────────────────
# Override standard methods (꼭 필요할 때만 사용)
# ─────────────────────────────────────────────────────────────────
# override_doctype_class = {
#     "Work Order": "food_mes_kr.food_mes_kr.overrides.work_order.CustomWorkOrder"
# }

# ─────────────────────────────────────────────────────────────────
# 정적 자원
# ─────────────────────────────────────────────────────────────────
# app_include_css = "/assets/food_mes_kr/css/food_mes_kr.css"
# app_include_js = "/assets/food_mes_kr/js/food_mes_kr.js"

# Plant Floor 화면에 식품 전용 위젯 추가하고 싶을 때:
# doctype_js = {"Job Card": "public/js/job_card_food_extensions.js"}
