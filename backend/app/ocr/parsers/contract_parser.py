import re


def parse_contract_fields(full_text: str) -> dict:
    fields = {
        "contract_no": None,
        "party_a": None,
        "party_b": None,
        "amount": None,
        "sign_date": None,
    }

    patterns = {
        "contract_no": [
            r"合同编号[：: ]*([A-Za-z0-9\-_]+)"
        ],
        "party_a": [
            r"甲方[：: ]*([^\n]+)"
        ],
        "party_b": [
            r"乙方[：: ]*([^\n]+)"
        ],
        "amount": [
            r"(?:合同金额|总金额|金额)[：: ]*([¥￥]?\s?[0-9,]+(?:\.[0-9]{1,2})?)"
        ],
        "sign_date": [
            r"签订日期[：: ]*([0-9]{4}[年\-/][0-9]{1,2}[月\-/][0-9]{1,2}日?)",
            r"签署日期[：: ]*([0-9]{4}[年\-/][0-9]{1,2}[月\-/][0-9]{1,2}日?)"
        ],
    }

    for key, regex_list in patterns.items():
        for pattern in regex_list:
            match = re.search(pattern, full_text)
            if match:
                fields[key] = match.group(1).strip()
                break

    return fields