import io
import os
import tempfile
import docx
from pypdf import PdfReader
import openpyxl
from fastapi import UploadFile
import sys

from app.core.logger import log_error

# 外部OCR服务配置
OCR_SERVICE_PATH = r"D:\TREA\07_Project-PDF-OCR"

async def extract_text_from_file(file: UploadFile) -> str:
    content = await file.read()
    filename = file.filename.lower()
    
    print(f"接收到文件: {filename}, 大小: {len(content)} bytes")
    
    try:
        if filename.endswith(".pdf"):
            return _extract_pdf(content, filename)
        elif filename.endswith(".docx"):
            return _extract_docx(content)
        elif filename.endswith(".doc"):
            return _extract_doc(content, filename)
        elif filename.endswith(".xlsx") or filename.endswith(".xls"):
            return _extract_excel(content)
        elif filename.endswith(".txt") or filename.endswith(".md"):
            return content.decode("utf-8")
        elif filename.endswith(".jpg") or filename.endswith(".jpeg") or filename.endswith(".png") or filename.endswith(".bmp") or filename.endswith(".tif") or filename.endswith(".tiff"):
            return _extract_image(content, filename)
        else:
            return f"Error: Unsupported file type for {filename}"
    except Exception as e:
        print(f"提取文本时出错: {str(e)}")
        return f"Error extracting text from {filename}: {str(e)}"

def _extract_pdf(content: bytes, filename: str) -> str:
    print(f"处理PDF文件: {filename}, 大小: {len(content)} bytes")
    
    # 首先尝试使用原有的PDF解析方法
    try:
        print("尝试使用原有的PDF解析方法...")
        reader = PdfReader(io.BytesIO(content))
        text_chunks = []
        for page in reader.pages:
            page_text = page.extract_text()
            if page_text:
                text_chunks.append(page_text)
        text = "\n".join(text_chunks).strip()
        if text:
            print(f"原方法成功提取到文本，长度: {len(text)}")
            # 如果原方法成功提取到文本，直接返回
            return text
        else:
            print("原方法未提取到任何文本")
    except Exception as e:
        print(f"原PDF解析方法失败: {str(e)}")
    
    # 尝试使用集成的OCR服务
    try:
        print("尝试使用集成的OCR服务...")
        # 导入集成的OCR服务
        from app.ocr.ocr_service import ocr_process
        
        print("集成OCR服务导入成功")
        
        # 保存临时文件到当前目录，避免路径问题
        temp_dir = os.path.join(os.path.dirname(__file__), "..", "..", "temp")
        os.makedirs(temp_dir, exist_ok=True)
        print(f"临时目录: {temp_dir}")
        
        temp_filename = f"temp_{os.getpid()}_{filename}"
        tmp_path = os.path.join(temp_dir, temp_filename)
        print(f"临时文件路径: {tmp_path}")
        
        try:
            # 写入临时文件
            with open(tmp_path, "wb") as f:
                f.write(content)
            
            # 验证文件是否正确写入
            if not os.path.exists(tmp_path):
                print("错误: 临时文件不存在")
                return "Error: 临时文件创建失败"
            
            file_size = os.path.getsize(tmp_path)
            print(f"临时文件大小: {file_size} bytes")
            
            if file_size == 0:
                print("错误: 临时文件为空")
                return "Error: 临时文件创建失败"
            
            # 尝试使用集成OCR服务
            print("调用集成OCR服务...")
            # 先检查OCR服务是否能够读取文件
            if not os.access(tmp_path, os.R_OK):
                print(f"错误: OCR服务无法读取临时文件: {tmp_path}")
                return "Error: OCR服务无法读取临时文件"
            
            # 尝试使用OCR服务，添加超时控制
            import concurrent.futures

            try:
                # 使用线程池执行OCR处理，设置300秒超时（OCR处理可能需要较长时间）
                with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
                    future = executor.submit(ocr_process, tmp_path, use_preprocess=True, zoom=2.0)
                    try:
                        # 等待OCR处理完成
                        result = future.result(timeout=300)

                        print("集成OCR服务调用成功")
                        # 打印结果摘要，避免打印过大的结果
                        result_summary = {k: v for k, v in result.items() if k != "ocr" and k != "full_text"}
                        print(f"集成OCR服务返回结果摘要: {result_summary}")

                        full_text = result.get("full_text", "")
                        if full_text:
                            print(f"集成OCR服务成功提取到文本，长度: {len(full_text)}")
                            return full_text
                        else:
                            print("集成OCR服务未识别出任何文字")
                            return "Error: OCR 服务未识别出任何文字，请检查文件清晰度。"
                    except concurrent.futures.TimeoutError:
                        error_msg = "OCR 处理超时（超过5分钟），文件可能过大或模糊"
                        print(error_msg)
                        log_error("OCR_TIMEOUT", error_msg, f"file={filename}")
                        return f"Error: {error_msg}"
                    except ValueError as ve:
                        print(f"集成OCR服务执行错误: {str(ve)}")
                        log_error("OCR_VALUE_ERROR", str(ve), f"file={filename}")
                        return f"Error: OCR 解析 PDF 失败: {str(ve)}"
                    except Exception as e:
                        print(f"集成OCR服务执行错误: {str(e)}")
                        log_error("OCR_EXEC_ERROR", str(e), f"file={filename}")
                        return f"Error: OCR 处理失败: {str(e)}"
            except Exception as e:
                print(f"集成OCR服务错误: {str(e)}")
                log_error("OCR_SERVICE_ERROR", str(e), f"file={filename}")
                return f"Error: OCR 服务调用失败: {str(e)}"
        finally:
            # 清理临时文件
            try:
                if os.path.exists(tmp_path):
                    os.unlink(tmp_path)
                    print(f"临时文件已清理: {tmp_path}")
            except OSError as e:
                print(f"清理临时文件失败: {str(e)}")
    except Exception as e:
        print(f"集成OCR服务初始化失败: {str(e)}")
        log_error("OCR_INIT", str(e), f"file={filename}")
        return f"Error: OCR 服务初始化失败: {str(e)}"

def _extract_image(content: bytes, filename: str) -> str:
    # 尝试使用集成的OCR服务
    try:
        print("尝试使用集成的OCR服务处理图片...")
        # 导入集成的OCR服务
        from app.ocr.ocr_service import ocr_process
        
        # 保存临时文件到当前目录，避免路径问题
        temp_dir = os.path.join(os.path.dirname(__file__), "..", "..", "temp")
        os.makedirs(temp_dir, exist_ok=True)
        
        temp_filename = f"temp_{os.getpid()}_{filename}"
        tmp_path = os.path.join(temp_dir, temp_filename)
        
        try:
            # 写入临时文件
            with open(tmp_path, "wb") as f:
                f.write(content)
            
            # 验证文件是否正确写入
            if not os.path.exists(tmp_path) or os.path.getsize(tmp_path) == 0:
                return "Error: 临时文件创建失败"
            
            # 使用集成OCR服务处理图片
            result = ocr_process(tmp_path, use_preprocess=True)
            full_text = result.get("full_text", "")
            if full_text:
                return full_text
            else:
                return "Error: OCR 服务未识别出任何文字，请检查图片清晰度。"
        except Exception as e:
            return f"Error: 图片 OCR 解析失败: {str(e)}"
        finally:
            # 清理临时文件
            try:
                if os.path.exists(tmp_path):
                    os.unlink(tmp_path)
            except OSError:
                pass
    except Exception as e:
        # 集成OCR服务不可用
        return f"Error: 图片 OCR 服务不可用，请检查依赖安装: {str(e)}"

def _extract_docx(content: bytes) -> str:
    try:
        doc = docx.Document(io.BytesIO(content))
        text = []
        for para in doc.paragraphs:
            text.append(para.text)
        return "\n".join(text)
    except Exception as e:
        raise Exception(f"DOCX parsing failed: {str(e)}")


def _extract_doc(content: bytes, filename: str) -> str:
    """提取 Word 97-2003 (.doc) 格式文件的文本，使用 pypandoc 或 Windows COM 回退。"""
    pypandoc_err = None
    try:
        import pypandoc
        # 确保 Pandoc 可用（pypandoc-binary 会提供，否则需单独安装）
        pypandoc.get_pandoc_version()
        with tempfile.NamedTemporaryFile(suffix=".doc", delete=False) as tmp:
            tmp.write(content)
            tmp_path = tmp.name
        try:
            text = pypandoc.convert_file(tmp_path, "plain", extra_args=["--wrap=none"])
            return text.strip() if text else ""
        finally:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass
    except ImportError as e:
        pypandoc_err = f"pypandoc 未安装: {e}"
    except Exception as e:
        pypandoc_err = str(e)

    # Windows 回退：使用 Win32 COM 通过 Microsoft Word 打开 .doc
    try:
        import win32com.client
        import pythoncom
        with tempfile.NamedTemporaryFile(suffix=".doc", delete=False) as tmp:
            tmp.write(content)
            tmp_path = tmp.name
        try:
            pythoncom.CoInitialize()
            word = win32com.client.Dispatch("Word.Application")
            word.Visible = False
            word.DisplayAlerts = False
            doc = word.Documents.Open(os.path.abspath(tmp_path), ReadOnly=True)
            text = doc.Range().Text.replace("\r", "\n")
            doc.Close(SaveChanges=False)
            word.Quit()
            return text.strip() if text else ""
        finally:
            try:
                pythoncom.CoUninitialize()
            except Exception:
                pass
            try:
                os.unlink(tmp_path)
            except OSError:
                pass
    except ImportError:
        return (
            "Error: 无法解析 .doc 文件。"
            "请执行: pip install pypandoc pypandoc-binary（推荐，含 Pandoc），"
            "或安装 pywin32 且本机安装 Microsoft Word。"
            + (f" [pypandoc 失败: {pypandoc_err}]" if pypandoc_err else "")
        )
    except Exception as e:
        return f"Error: 解析 .doc 文件失败: {str(e)}"

def _extract_excel(content: bytes) -> str:
    try:
        wb = openpyxl.load_workbook(io.BytesIO(content), data_only=True)
        text = []
        for sheet in wb.worksheets:
            text.append(f"--- Sheet: {sheet.title} ---")
            for row in sheet.iter_rows(values_only=True):
                # Filter None values and convert to string
                row_text = [str(cell) for cell in row if cell is not None]
                if row_text:
                    text.append(" ".join(row_text))
        return "\n".join(text)
    except Exception as e:
        raise Exception(f"Excel parsing failed: {str(e)}")
