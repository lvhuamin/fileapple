"""
提取文件内容 (PDF/EPUB/DOCX/TXT/MD) — 167 兼容版
优先用 pypdf（纯 Python，167 上已装），fallback 到 pymupdf（如果装了）
"""
import os
import logging

logger = logging.getLogger(__name__)


def _extract_text_from_file(filepath: str) -> str:
    """主入口: 按扩展名分发"""
    if not os.path.exists(filepath):
        logger.error("file not found: %s", filepath)
        return ""

    ext = os.path.splitext(filepath)[1].lower()
    if ext == ".pdf":
        return _extract_pdf(filepath)
    elif ext in (".epub",):
        return _extract_epub(filepath)
    elif ext == ".docx":
        return _extract_docx(filepath)
    elif ext in (".txt", ".md"):
        return _extract_text(filepath)
    else:
        logger.warning("unsupported file type: %s", filepath)
        return ""


# ── PDF ──────────────────────────────────────────────────
def _extract_pdf(filepath: str) -> str:
    """优先 pypdf（纯 Python），fallback pymupdf（如果装了）"""
    text_parts = []
    try:
        # 167 优先路径
        from pypdf import PdfReader
        reader = PdfReader(filepath)
        for page in reader.pages:
            try:
                text_parts.append(page.extract_text() or "")
            except Exception as e:
                logger.warning("pypdf page extract fail: %s", e)
                continue
        text = "\n".join(text_parts)
        logger.info("PDF (pypdf) extracted: %s → %d chars", os.path.basename(filepath), len(text))
        return text
    except ImportError:
        pass
    except Exception as e:
        logger.warning("pypdf failed, fallback to pymupdf: %s", e)

    # fallback: pymupdf
    try:
        import pymupdf
    except ImportError:
        try:
            import fitz as pymupdf
        except ImportError:
            logger.error("no PDF lib available (pypdf/pymupdf not installed)")
            return ""

    doc = pymupdf.open(filepath)
    pages = [page.get_text() for page in doc]
    doc.close()
    text = "\n".join(pages)
    logger.info("PDF (pymupdf) extracted: %s → %d chars", os.path.basename(filepath), len(text))
    return text


# ── EPUB ─────────────────────────────────────────────────
def _extract_epub(filepath: str) -> str:
    try:
        from ebooklib import epub, ITEM_DOCUMENT
        book = epub.read_epub(filepath)
        items = []
        for item in book.get_items_of_type(ITEM_DOCUMENT):
            content = item.get_content().decode("utf-8", errors="ignore")
            # 简单去标签
            import re
            content = re.sub(r"<[^>]+>", "", content)
            items.append(content)
        text = "\n".join(items)
        logger.info("EPUB extracted: %s → %d chars", os.path.basename(filepath), len(text))
        return text
    except Exception as e:
        logger.error("EPUB extract failed [%s]: %s", filepath, e)
        return ""


# ── DOCX ─────────────────────────────────────────────────
def _extract_docx(filepath: str) -> str:
    try:
        import docx
        d = docx.Document(filepath)
        paragraphs = [p.text for p in d.paragraphs]
        text = "\n".join(paragraphs)
        logger.info("DOCX extracted: %s → %d chars", os.path.basename(filepath), len(text))
        return text
    except ImportError:
        logger.error("python-docx not installed")
        return ""
    except Exception as e:
        logger.error("DOCX extract failed [%s]: %s", filepath, e)
        return ""


# ── TXT / MD ─────────────────────────────────────────────
def _extract_text(filepath: str) -> str:
    try:
        with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
            text = f.read()
        logger.info("TXT/MD extracted: %s → %d chars", os.path.basename(filepath), len(text))
        return text
    except Exception as e:
        logger.error("TXT/MD read failed [%s]: %s", filepath, e)
        return ""


# ── 公共 API ─────────────────────────────────────────────
def extract(filepath: str) -> str:
    """主入口 - v3 协议"""
    return _extract_text_from_file(filepath)
