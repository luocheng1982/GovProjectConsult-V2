from pathlib import Path
import cv2


def preprocess_image(image_path: str, output_dir: str) -> str:
    """
    简单图像预处理：
    - 灰度
    - 高斯去噪
    - 自适应二值化

    返回预处理后的图片路径
    """
    image_path = Path(image_path)
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    img = cv2.imread(str(image_path))
    if img is None:
        raise ValueError(f"无法读取图片: {image_path}")

    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    blur = cv2.GaussianBlur(gray, (3, 3), 0)
    binary = cv2.adaptiveThreshold(
        blur,
        255,
        cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
        cv2.THRESH_BINARY,
        31,
        10,
    )

    output_path = output_dir / f"{image_path.stem}_preprocessed.png"
    cv2.imwrite(str(output_path), binary)
    return str(output_path)