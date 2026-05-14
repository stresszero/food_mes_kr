// food_mes_kr/food_mes_kr/report/forward_trace/forward_trace.js
//
// Script Report 의 사용자 입력 필터 정의.
// 사용자가 입력한 값은 server-side execute() 함수의 filters dict 로 전달된다.

frappe.query_reports["Forward Trace"] = {
    "filters": [
        {
            "fieldname": "source_batch",
            "label": __("Source LOT (원료/반제품 LOT)"),
            "fieldtype": "Link",
            "options": "Batch",
            "reqd": 1,
            "description": __("추적 시작 LOT 입력. 예: 사과농축액 LOT 'FRX-2025-1102'")
        },
        {
            "fieldname": "max_depth",
            "label": __("Max Depth (재귀 한계)"),
            "fieldtype": "Int",
            "default": 6,
            "description": __("BOM 다단(원료→반제품→완제품) 깊이. 기본 6.")
        }
    ],

    // 깊이에 따라 색상 변화 (가독성)
    "formatter": function (value, row, column, data, default_formatter) {
        value = default_formatter(value, row, column, data);
        if (column.fieldname === "depth" && data) {
            const colors = ["", "#888", "#5e64ff", "#0089ff", "#00b8a9", "#f5a623", "#d9534f"];
            const c = colors[Math.min(data.depth || 0, colors.length - 1)];
            value = `<span style="color:${c}; font-weight:600;">${value}</span>`;
        }
        return value;
    },

    // CSV 내보내기 시 출하처 칼럼 줄바꿈을 ' / '로 치환
    onload: function (report) {
        report.page.add_inner_button(__("Export Recall Notice"), function () {
            const source = frappe.query_report.get_filter_value("source_batch");
            if (!source) {
                frappe.msgprint(__("먼저 Source LOT을 입력하세요."));
                return;
            }
            // 별도 회수통지서 출력 (PDF) - Print Format 연결
            frappe.set_route("print", "Batch", source, "Recall Notice");
        });
    }
};
