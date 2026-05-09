from pathlib import Path
from app.ocr.ocr_engine import OCREngine
from app.ocr.pdf_utils import pdf_to_images
from app.ocr.preprocess import preprocess_image
from app.ocr.classifier import detect_doc_type
from app.ocr.parsers.contract_parser import parse_contract_fields
from app.ocr.parsers.invoice_parser import parse_invoice_fields
from app.ocr.parsers.report_parser import parse_report_fields
from app.ocr.utils import ensure_dir, save_json, save_text
from app.ocr.config import (
    PDF_PAGES_DIR,
    PREPROCESS_DIR,
    JSON_OUTPUT_DIR,
    TXT_OUTPUT_DIR,
    MD_OUTPUT_DIR,
    DEFAULT_LANG,
    DEFAULT_PDF_ZOOM,
    DEFAULT_USE_PREPROCESS,
)
import concurrent.futures


def build_output_text(ocr_json: dict) -> str:
    chunks = []
    for page in ocr_json.get("pages", []):
        page_no = page.get("page_index", 0) + 1
        chunks.append(f"===== PAGE {page_no} =====")
        for item in page.get("texts", []):
            text = item.get("text", "")
            if text:
                chunks.append(text)
        chunks.append("")
    return "\n".join(chunks).strip()


def build_output_md(ocr_json: dict, fields: dict = None) -> str:
    chunks = []
    # 添加标题
    chunks.append(f"# {ocr_json.get('source_name', 'Document')}")
    chunks.append("")
    
    # 添加字段信息
    if fields:
        chunks.append("## Document Fields")
        for key, value in fields.items():
            if value:
                chunks.append(f"- **{key}**: {value}")
        chunks.append("")
    
    # 添加每页内容
    for page in ocr_json.get("pages", []):
        page_no = page.get("page_index", 0) + 1
        chunks.append(f"## Page {page_no}")
        chunks.append("")
        for item in page.get("texts", []):
            text = item.get("text", "")
            if text:
                chunks.append(text)
        chunks.append("")
    return "\n".join(chunks).strip()


def parse_by_doc_type(doc_type: str, full_text: str) -> dict:
    if doc_type == "contract":
        return parse_contract_fields(full_text)
    if doc_type == "invoice":
        return parse_invoice_fields(full_text)
    if doc_type == "report":
        return parse_report_fields(full_text)
    return {}


def process_single_page(args):
    # 导入需要的模块
    from app.ocr.ocr_engine import OCREngine
    from app.ocr.preprocess import preprocess_image
    from pathlib import Path
    
    img_path, idx, use_preprocess, preprocess_dir = args
    
    # 初始化 OCREngine
    engine = OCREngine()
    
    actual_img_path = img_path
    if use_preprocess:
        actual_img_path = preprocess_image(img_path, preprocess_dir)
    
    raw_result = engine.predict(actual_img_path)
    page_json = engine.normalize_result(raw_result, source_name=Path(actual_img_path).name)
    
    if page_json.get("pages"):
        # 强制把单页 OCR 结果的 page_index 改为原 PDF 的真实页号
        page_json["pages"][0]["page_index"] = idx
    
    return actual_img_path, page_json


class OCRService:
    """
    OCR 服务类，提供文档识别功能
    """
    
    def __init__(self, lang: str = DEFAULT_LANG):
        """
        初始化 OCR 服务
        
        Args:
            lang: OCR 语言，默认中文 (ch)
        """
        self.lang = lang
        self.engine = OCREngine()
    
    def process_file(self, file_path: str, doc_type: str = None, use_preprocess: bool = DEFAULT_USE_PREPROCESS, zoom: float = DEFAULT_PDF_ZOOM) -> dict:
        """
        处理文件（PDF 或图片）
        
        Args:
            file_path: 文件路径
            doc_type: 文档类型，可选值：contract, invoice, report
            use_preprocess: 是否使用预处理
            zoom: PDF 转图片的缩放倍数
        
        Returns:
            包含识别结果的字典
        """
        path = Path(file_path)
        ext = path.suffix.lower()
        
        if ext in [".jpg", ".jpeg", ".png", ".bmp", ".tif", ".tiff"]:
            return self.process_image(file_path, doc_type, use_preprocess)
        elif ext == ".pdf":
            return self.process_pdf(file_path, doc_type, use_preprocess, zoom)
        else:
            raise ValueError(f"不支持的文件类型: {ext}")
    
    def process_image(self, image_path: str, doc_type: str = None, use_preprocess: bool = DEFAULT_USE_PREPROCESS) -> dict:
        """
        处理图片文件
        
        Args:
            image_path: 图片路径
            doc_type: 文档类型
            use_preprocess: 是否使用预处理
        
        Returns:
            包含识别结果的字典
        """
        image_path = Path(image_path)
        if not image_path.exists():
            raise FileNotFoundError(f"图片不存在: {image_path}")
        
        # 确保输出目录存在
        ensure_dir(PREPROCESS_DIR)
        ensure_dir(JSON_OUTPUT_DIR)
        ensure_dir(TXT_OUTPUT_DIR)
        ensure_dir(MD_OUTPUT_DIR)
        
        actual_image_path = str(image_path)
        if use_preprocess:
            actual_image_path = preprocess_image(str(image_path), str(PREPROCESS_DIR))
        
        # 执行 OCR
        raw_result = self.engine.predict(actual_image_path)
        ocr_json = self.engine.normalize_result(raw_result, source_name=image_path.name)
        full_text = self.engine.merge_text(ocr_json)
        
        # 检测文档类型
        final_doc_type = doc_type or detect_doc_type(full_text)
        fields = parse_by_doc_type(final_doc_type, full_text)
        
        # 构建结果
        result = {
            "source_file": str(image_path),
            "processed_image": actual_image_path,
            "doc_type": final_doc_type,
            "ocr_text_count": self.engine.count_text_items(ocr_json),
            "full_text": full_text,
            "fields": fields,
            "ocr": ocr_json,
        }
        
        # 保存结果
        stem = image_path.stem
        save_json(result, JSON_OUTPUT_DIR / f"{stem}.json")
        save_text(build_output_text(ocr_json), TXT_OUTPUT_DIR / f"{stem}.txt")
        save_text(build_output_md(ocr_json, fields), MD_OUTPUT_DIR / f"{stem}.md")
        
        return result
    
    def process_pdf(self, pdf_path: str, doc_type: str = None, use_preprocess: bool = DEFAULT_USE_PREPROCESS, zoom: float = DEFAULT_PDF_ZOOM) -> dict:
        """
        处理 PDF 文件

        Args:
            pdf_path: PDF 路径
            doc_type: 文档类型
            use_preprocess: 是否使用预处理
            zoom: PDF 转图片的缩放倍数

        Returns:
            包含识别结果的字典
        """
        import traceback
        pdf_path = Path(pdf_path)
        if not pdf_path.exists():
            raise FileNotFoundError(f"PDF 不存在: {pdf_path}")

        ensure_dir(PDF_PAGES_DIR)
        ensure_dir(PREPROCESS_DIR)
        ensure_dir(JSON_OUTPUT_DIR)
        ensure_dir(TXT_OUTPUT_DIR)
        ensure_dir(MD_OUTPUT_DIR)

        try:
            page_images = pdf_to_images(str(pdf_path), str(PDF_PAGES_DIR), zoom=zoom)
        except ValueError as ve:
            raise ValueError(f"PDF 文件无法解析: {str(ve)}") from ve
        except Exception as e:
            raise ValueError(f"PDF 转换为图片失败: {str(e)}\n{traceback.format_exc()}") from e
        
        # 使用线程池并行处理页面
        num_workers = min(4, len(page_images))  # 限制线程数，避免资源耗尽
        
        # 准备参数
        preprocess_dir = str(PREPROCESS_DIR)
        task_args = [(img_path, idx, use_preprocess, preprocess_dir) for idx, img_path in enumerate(page_images)]
        
        # 并行处理
        results = []
        with concurrent.futures.ThreadPoolExecutor(max_workers=num_workers) as executor:
            # 提交所有任务
            future_to_task = {executor.submit(process_single_page, args): args for args in task_args}
            
            # 收集结果
            for future in concurrent.futures.as_completed(future_to_task):
                try:
                    result = future.result()
                    results.append(result)
                except Exception as exc:
                    print(f'处理任务时发生错误: {exc}')
        
        # 收集结果
        merged_pages = []
        processed_images = []
        
        for actual_img_path, page_json in results:
            processed_images.append(actual_img_path)
            if page_json.get("pages"):
                merged_pages.extend(page_json["pages"])
        
        # 合并结果
        final_ocr_json = {
            "source_name": pdf_path.name,
            "pages": merged_pages
        }
        
        # 处理文本和字段
        full_text = self.engine.merge_text(final_ocr_json)
        final_doc_type = doc_type or detect_doc_type(full_text)
        fields = parse_by_doc_type(final_doc_type, full_text)
        
        # 构建结果
        result = {
            "source_file": str(pdf_path),
            "processed_images": processed_images,
            "doc_type": final_doc_type,
            "page_count": len(page_images),
            "ocr_text_count": self.engine.count_text_items(final_ocr_json),
            "full_text": full_text,
            "fields": fields,
            "ocr": final_ocr_json,
        }
        
        # 保存结果
        stem = pdf_path.stem
        save_json(result, JSON_OUTPUT_DIR / f"{stem}.json")
        save_text(build_output_text(final_ocr_json), TXT_OUTPUT_DIR / f"{stem}.txt")
        save_text(build_output_md(final_ocr_json, fields), MD_OUTPUT_DIR / f"{stem}.md")
        
        return result


OCR_EXTERNAL_VENV_PYTHON = r"D:\TREA\07_Project-PDF-OCR\paddleocr_env\Scripts\python.exe"
OCR_EXTERNAL_SCRIPT = r"""
import sys
sys.path.insert(0, r'D:\\TREA\\07_Project-PDF-OCR')
sys.path.insert(0, r'D:\\TREA\\GovProjectConsult - V2\\backend')
from app.ocr.ocr_service import OCRService

service = OCRService(lang='ch')
result = service.process_file(r'%s', doc_type=None, use_preprocess=%s, zoom=%s)
import json
print('OCR_RESULT_START')
print(json.dumps({
    'full_text': result.get('full_text', ''),
    'doc_type': result.get('doc_type', ''),
    'page_count': result.get('page_count', 0),
    'ocr_text_count': result.get('ocr_text_count', 0)
}, ensure_ascii=False))
print('OCR_RESULT_END')
"""


def ocr_process(file_path: str, doc_type: str = None, use_preprocess: bool = DEFAULT_USE_PREPROCESS, lang: str = DEFAULT_LANG, zoom: float = DEFAULT_PDF_ZOOM) -> dict:
    """
    OCR 处理统一入口函数

    Args:
        file_path: 文件路径
        doc_type: 文档类型，可选值：contract, invoice, report
        use_preprocess: 是否使用预处理
        lang: OCR 语言，默认中文 (ch)
        zoom: PDF 转图片的缩放倍数

    Returns:
        包含识别结果的字典
    """
    import subprocess
    import json

    script = OCR_EXTERNAL_SCRIPT % (file_path.replace('\\', '\\\\'), 'True' if use_preprocess else 'False', zoom)

    try:
        result = subprocess.run(
            [OCR_EXTERNAL_VENV_PYTHON, "-c", script],
            capture_output=True,
            text=True,
            timeout=300
        )

        if result.returncode != 0:
            raise RuntimeError(f"OCR子进程执行失败: {result.stderr}")

        output = result.stdout
        start_idx = output.find('OCR_RESULT_START')
        end_idx = output.find('OCR_RESULT_END')

        if start_idx != -1 and end_idx != -1:
            json_str = output[start_idx + 16:end_idx].strip()
            parsed = json.loads(json_str)
            return parsed

        raise RuntimeError(f"OCR输出解析失败: {output}")
    except subprocess.TimeoutExpired:
        raise TimeoutError("OCR处理超时")
