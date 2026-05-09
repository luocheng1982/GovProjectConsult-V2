import re


def parse_invoice_fields(full_text: str) -> dict:
    fields = {
        "invoice_no": None,
        "invoice_date": None,
        "buyer_name": None,
        "seller_name": None,
        "total_amount": None,
        "tax_amount": None,
    }

    patterns = {
        "invoice_no": [
            r"发票号码[：: ]*([0-9]{8,20})",
            r"票据号码[：: ]*([0-9]{8,20})"
        ],
        "invoice_date": [
            r"开票日期[：: ]*([0-9]{4}[年\-/][0-9]{1,2}[月\-/][0-9]{1,2}日?)"
        ],
        "buyer_name": [
            r"购买方名称[：: ]*([^\n]+)",
            r"购\s*买\s*方[：: ]*([^\n]+)"
        ],
        "seller_name": [
            r"销售方名称[：: ]*([^\n]+)",
            r"销\s*售\s*方[：: ]*([^\n]+)"
        ],
        "total_amount": [
            r"(?:价税合计|合计|金额合计)[（\(]?大写[）\)]?.*?[¥￥]?\s*([0-9,]+(?:\.[0-9]{1,2})?)",
            r"(?:价税合计|合计|金额合计)[：: ]*([0-9,]+(?:\.[0-9]{1,2})?)"
        ],
        "tax_amount": [
            r"税额[：: ]*([0-9,]+(?:\.[0-9]{1,2})?)"
        ],
    }

    for key, regex_list in patterns.items():
        for pattern in regex_list:
            match = re.search(pattern, full_text, re.S)
            if match:
                fields[key] = match.group(1).strip()
                break

    return fields