from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent.parent.parent.parent
DATA_DIR = BASE_DIR / "data"
OUTPUT_DIR = BASE_DIR / "output"

IMAGES_DIR = DATA_DIR / "images"
PDFS_DIR = DATA_DIR / "pdfs"

JSON_OUTPUT_DIR = OUTPUT_DIR / "json"
TXT_OUTPUT_DIR = OUTPUT_DIR / "txt"
MD_OUTPUT_DIR = OUTPUT_DIR / "md"
PDF_PAGES_DIR = OUTPUT_DIR / "pdf_pages"
PREPROCESS_DIR = OUTPUT_DIR / "preprocessed"

SUPPORTED_IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".bmp", ".tif", ".tiff"}
SUPPORTED_PDF_EXTS = {".pdf"}

DEFAULT_LANG = "ch"
DEFAULT_PDF_ZOOM = 2.0
DEFAULT_USE_PREPROCESS = False