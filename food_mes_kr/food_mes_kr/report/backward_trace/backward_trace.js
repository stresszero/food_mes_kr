// food_mes_kr/food_mes_kr/report/backward_trace/backward_trace.js

frappe.query_reports["Backward Trace"] = {
    "filters": [
        {
            "fieldname": "finished_batch",
            "label": __("Finished LOT (완제품 LOT)"),
            "fieldtype": "Link",
            "options": "Batch",
            "reqd": 1,
            "description": __("역추적 시작점 완제품 LOT. 예: '251207-L1-001'")
        },
        {
            "fieldname": "max_depth",
            "label": __("Max Depth"),
            "fieldtype": "Int",
            "default": 6
        }
    ]
};
