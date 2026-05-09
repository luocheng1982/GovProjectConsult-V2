import re


def split_sections(full_text: str) -> list[dict]:
    """
    粗略按中文标题切分段落
    """
    section_patterns = [
        r"(一、[^\n]+)",
        r"(二、[^\n]+)",
        r"(三、[^\n]+)",
        r"(四、[^\n]+)",
        r"(五、[^\n]+)",
        r"(六、[^\n]+)",
        r"(七、[^\n]+)",
        r"(八、[^\n]+)",
        r"(九、[^\n]+)",
        r"(十、[^\n]+)",
    ]

    headings = []
    for pattern in section_patterns:
        headings.extend(re.findall(pattern, full_text))

    if not headings:
        return [{
            "heading": "全文",
            "content": full_text.strip()
        }]

    sections = []
    current_pos = 0
    matches = list(re.finditer(r"(?:^|\n)((?:[一二三四五六七八九十]+、[^\n]+))", full_text))

    if not matches:
        return [{
            "heading": "全文",
            "content": full_text.strip()
        }]

    for idx, match in enumerate(matches):
        heading = match.group(1).strip()
        start = match.start(1)
        end = matches[idx + 1].start(1) if idx + 1 < len(matches) else len(full_text)
        content = full_text[start:end].strip()
        sections.append({
            "heading": heading,
            "content": content
        })
        current_pos = end

    if not sections and full_text.strip():
        sections.append({
            "heading": "全文",
            "content": full_text.strip()
        })

    return sections


def parse_report_fields(full_text: str) -> dict:
    lines = [line.strip() for line in full_text.splitlines() if line.strip()]

    fields = {
        "title": lines[0] if lines else None,
        "report_no": None,
        "date": None,
        "department": None,
        "author": None,
    }

    patterns = {
        "report_no": [
            r"(?:报告编号|编号)[：: ]*([A-Za-z0-9\-_]+)"
        ],
        "date": [
            r"(?:日期|报告日期)[：: ]*([0-9]{4}[年\-/][0-9]{1,2}[月\-/][0-9]{1,2}日?)"
        ],
        "department": [
            r"(?:部门|报送部门|提交部门)[：: ]*([^\n]+)"
        ],
        "author": [
            r"(?:报告人|提交人|经办人|负责人)[：: ]*([^\n]+)"
        ],
    }

    for key, regex_list in patterns.items():
        for pattern in regex_list:
            match = re.search(pattern, full_text)
            if match:
                fields[key] = match.group(1).strip()
                break

    fields["sections"] = split_sections(full_text)
    return fields