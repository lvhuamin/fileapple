"""
文本提取器 — PDF / EPUB / DOCX / TXT / 图片
输出原始文本，不处理切片/摘要
"""
import os
import logging

logger = logging.getLogger("ingestion.extractor")

SUPPORTED_EXTS = {".pdf", ".epub", ".docx", ".txt", ".md", ".png", ".jpg", ".jpeg", ".bmp", ".gif", ".tiff", ".webp"}


def extract(filepath: str) -> str | None:
    ext = os.path.splitext(filepath)[1].lower()
    if ext not in SUPPORTED_EXTS:
        logger.warning("unsupported text format: %s", ext)
        return None

    try:
        if ext == ".pdf":
            return _extract_pdf(filepath)
        elif ext == ".epub":
            return _extract_epub(filepath)
        elif ext == ".docx":
            return _extract_docx(filepath)
        elif ext in IMAGE_EXTS:
            return _extract_image_ocr(filepath)
        else:  # .txt / .md
            return _extract_text(filepath)
    except Exception as e:
        logger.error("extract failed [%s]: %s", filepath, e)
        return None


# ── PDF ──────────────────────────────────────────────────
def _extract_pdf(filepath: str) -> str:
    try:
        import pymupdf  # PyMuPDF
    except ImportError:
        import fitz as pymupdf

    doc = pymupdf.open(filepath)
    pages = []
    for page in doc:
        pages.append(page.get_text())
    doc.close()
    text = "\n".join(pages)
    logger.info("PDF extracted: %s → %d chars", os.path.basename(filepath), len(text))
    return text


# ── EPUB ─────────────────────────────────────────────────
def _extract_epub(filepath: str) -> str:
    import ebooklib
    from ebooklib import epub
    from bs4 import BeautifulSoup

    book = epub.read_epub(filepath)
    texts = []
    for item in book.get_items():
        if item.get_type() == ebooklib.ITEM_DOCUMENT:
            soup = BeautifulSoup(item.get_content(), "html.parser")
            texts.append(soup.get_text(separator="\n"))
    text = "\n".join(texts)
    logger.info("EPUB extracted: %s → %d chars", os.path.basename(filepath), len(text))
    return text


# ── DOCX ─────────────────────────────────────────────────
def _extract_docx(filepath: str) -> str:
    import docx

    doc = docx.Document(filepath)
    paragraphs = [p.text for p in doc.paragraphs]
    text = "\n".join(paragraphs)
    logger.info("DOCX extracted: %s → %d chars", os.path.basename(filepath), len(text))
    return text


# ── TXT / MD ─────────────────────────────────────────────
def _extract_text(filepath: str) -> str:
    with open(filepath, "r", encoding="utf-8", errors="replace") as f:
        text = f.read()
    logger.info("TXT extracted: %s → %d chars", os.path.basename(filepath), len(text))
    return text


# ── 图片 OCR ─────────────────────────────────────────────
# 支持: PNG, JPG, JPEG, BMP, GIF, TIFF, WEBP
IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".bmp", ".gif", ".tiff", ".webp"}

# EasyOCR 懒加载缓存
_easyocr_reader = None

def _get_easyocr_reader():
    """获取 EasyOCR reader 单例"""
    global _easyocr_reader
    if _easyocr_reader is None:
        try:
            import easyocr
            logger.info("初始化 EasyOCR reader (中文+英文)...")
            _easyocr_reader = easyocr.Reader(["ch_sim", "en"], gpu=False, verbose=False)
            logger.info("EasyOCR reader 初始化完成")
        except Exception as e:
            logger.error("EasyOCR 初始化失败: %s", e)
            raise
    return _easyocr_reader

def _extract_image_ocr(filepath: str) -> str:
    """从图片中提取文字 (OCR)"""
    reader = _get_easyocr_reader()
    try:
        results = reader.readtext(filepath)
        # 合并所有识别结果，保留位置信息
        lines = []
        for bbox, text, confidence in results:
            if confidence > 0.3:  # 置信度阈值
                lines.append(text.strip())
        text = "\n".join(filter(None, lines))
        logger.info("图片OCR提取: %s → %d chars, %d 行",
                    os.path.basename(filepath), len(text), len(lines))
        return text
    except Exception as e:
        logger.error("图片OCR提取失败 [%s]: %s", filepath, e)
        raise