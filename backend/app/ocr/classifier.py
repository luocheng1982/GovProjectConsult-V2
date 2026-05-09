def detect_doc_type(text: str) -> str:
    """
    简单粗分类：
    contract / invoice / report / unknown
    """
    normalized = text.replace(" ", "").replace("\n", "")

    invoice_keywords = [
        "发票号码", "开票日期", "价税合计", "税额", "购买方", "销售方"
    ]
    contract_keywords = [
        "合同编号", "甲方", "乙方", "合同金额", "签订日期", "协议"
    ]
    report_keywords = [
        "事项报告", "情况报告", "报告", "事项说明", "情况说明", "处理建议", "背景"
    ]

    if any(k in normalized for k in invoice_keywords):
        return "invoice"
    if any(k in normalized for k in contract_keywords):
        return "contract"
    if any(k in normalized for k in report_keywords):
        return "report"
    return "unknown"