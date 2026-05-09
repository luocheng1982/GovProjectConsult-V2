from pathlib import Path
from paddleocr import PaddleOCR


class OCREngine:
    def __init__(self, lang: str = "ch"):
        # 使用轻量级移动端模型，关闭附加模块以提高速度
        self.ocr = PaddleOCR(
            text_detection_model_name='PP-OCRv5_mobile_det',  # 使用移动端检测模型
            text_recognition_model_name='PP-OCRv5_mobile_rec',  # 使用移动端识别模型
            use_textline_orientation=False,  # 关闭角度分类
            use_doc_orientation_classify=False,  # 关闭文档方向分类
            use_doc_unwarping=False,  # 关闭文档校正
            text_det_limit_side_len=960  # 降低检测边长，提高速度
        )

    def predict(self, image_path: str):
        return self.ocr.predict(input=image_path)

    def normalize_result(self, result, source_name: str = "") -> dict:
        """
        尽量兼容 PaddleOCR 3.x 的输出结构。
        输出统一格式：
        {
          "source_name": "...",
          "pages": [
            {
              "page_index": 0,
              "texts": [
                {"text":"...", "score":0.99, "box":[...]}
              ]
            }
          ]
        }
        """
        pages = []

        for page_idx, page in enumerate(result):
            if hasattr(page, "res"):
                raw = page.res
            elif isinstance(page, dict):
                raw = page
            else:
                raw = {}

            rec_texts = raw.get("rec_texts", [])
            rec_scores = raw.get("rec_scores", [])
            rec_boxes = raw.get("rec_boxes", [])

            page_data = {
                "page_index": page_idx,
                "texts": []
            }

            for i, text in enumerate(rec_texts):
                score = None
                box = None

                if i < len(rec_scores):
                    try:
                        score = float(rec_scores[i])
                    except Exception:
                        score = None

                if i < len(rec_boxes):
                    box_item = rec_boxes[i]
                    if hasattr(box_item, "tolist"):
                        box = box_item.tolist()
                    else:
                        box = box_item

                page_data["texts"].append({
                    "text": str(text),
                    "score": score,
                    "box": box
                })

            pages.append(page_data)

        return {
            "source_name": source_name,
            "pages": pages
        }

    @staticmethod
    def merge_text(ocr_json: dict) -> str:
        lines = []
        for page in ocr_json.get("pages", []):
            for item in page.get("texts", []):
                text = item.get("text", "").strip()
                if text:
                    lines.append(text)
        return "\n".join(lines)

    @staticmethod
    def count_text_items(ocr_json: dict) -> int:
        total = 0
        for page in ocr_json.get("pages", []):
            total += len(page.get("texts", []))
        return total