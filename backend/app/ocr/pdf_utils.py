from pathlib import Path
import fitz


def pdf_to_images(pdf_path: str, output_dir: str, zoom: float = 2.0) -> list[str]:
    """
    将 PDF 每页导出为 PNG 图片
    """
    pdf_path = Path(pdf_path)
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    if not pdf_path.exists():
        raise FileNotFoundError(f"PDF 文件不存在: {pdf_path}")

    file_size = pdf_path.stat().st_size
    if file_size == 0:
        raise ValueError(f"PDF 文件为空: {pdf_path}")

    image_paths = []

    try:
        doc = fitz.open(str(pdf_path))
    except Exception as e:
        raise ValueError(f"无法打开 PDF 文件: {str(e)}")

    if len(doc) == 0:
        doc.close()
        raise ValueError("PDF 文件页数为0或无法读取页数")

    try:
        for page_index in range(len(doc)):
            page = doc[page_index]
            matrix = fitz.Matrix(zoom, zoom)
            pix = page.get_pixmap(matrix=matrix, alpha=False)

            image_path = output_dir / f"{pdf_path.stem}_page_{page_index + 1}.png"
            pix.save(str(image_path))
            image_paths.append(str(image_path))
    finally:
        doc.close()

    return image_paths