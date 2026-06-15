"""
智能文本切片 — 支持重叠、按段落/标题分割
输出切片列表，每个切片带元信息
"""
import re
import logging
from typing import List, Dict

logger = logging.getLogger("ingestion.chunker")


def chunk(
    text: str,
    source: str = "",
    max_tokens: int = 1000,
    overlap_tokens: int = 200,
) -> List[Dict]:
    """
    将长文本切分为知识块。
    按标题/段落自然分割，再按 token 上限截断。

    返回:
    [
        {
            "index": 0,
            "text": "...",
            "char_start": 0,
            "char_end": 500,
            "approx_tokens": 120,
            "has_title": True
        },
        ...
    ]
    """
    if not text or not text.strip():
        logger.warning("empty text for %s", source)
        return []

    # 按标题/空行分割为自然段落
    sections = _split_by_heading(text)

    chunks = []
    buffer = ""
    buffer_start = 0

    for sec_text, sec_start, sec_has_title in sections:
        sec_tokens = _approx_tokens(sec_text)

        # 如果单段本身超过上限，强制按 token 分割
        if sec_tokens > max_tokens:
            # 先 flush 现有 buffer
            if buffer.strip():
                _flush_chunk(chunks, buffer, buffer_start, sec_has_title)
            sub_pieces = _split_text_by_tokens(sec_text, max_tokens)
            for i, piece in enumerate(sub_pieces):
                has_title = sec_has_title and i == 0
                piece_start = sec_start + sec_text.index(piece)
                # 非首片：保留 overlap
                if i > 0:
                    overlap = _tail_by_tokens(chunks[-1]["text"], overlap_tokens) if chunks else ""
                    piece = overlap + piece
                    piece_start = piece_start - len(overlap)
                _flush_chunk(chunks, piece, piece_start, has_title)
            buffer = ""
            buffer_start = 0
            continue

        # buffer + 当前段超过上限 → 先 flush buffer
        if buffer and _approx_tokens(buffer + sec_text) > max_tokens:
            _flush_chunk(chunks, buffer, buffer_start, sec_has_title)
            # 保留末尾 overlap 作为新 buffer
            overlap_text = _tail_by_tokens(buffer, overlap_tokens)
            if overlap_text:
                buffer = overlap_text
                buffer_start = buffer_start + len(buffer) - len(overlap_text)
            else:
                buffer = ""
                buffer_start = 0

        if not buffer:
            buffer_start = sec_start
        buffer += sec_text

    # 最后一段
    if buffer.strip():
        _flush_chunk(chunks, buffer, buffer_start, False)

    logger.info("chunked %s: %d chars → %d chunks", source, len(text), len(chunks))
    return chunks


def _flush_chunk(chunks: list, text: str, start: int, has_title: bool):
    """向 chunks 列表追加一个切片"""
    text = text.strip()
    if not text:
        return
    chunks.append({
        "index": len(chunks),
        "text": text,
        "char_start": start,
        "char_end": start + len(text),
        "approx_tokens": _approx_tokens(text),
        "has_title": has_title,
    })


# ── 辅助函数 ────────────────────────────────────────────

def _split_by_heading(text: str):
    """
    按 ## / ### / --- 等标题标记分割，保留标题行。
    返回 [(section_text, char_start, has_heading)]
    """
    # 匹配 markdown 标题或数字编号标题
    pattern = re.compile(r"(^|\n)(#{1,6}\s+|第[一二三四五六七八九十\d]+[章节篇部分]|[A-Z][^。\n]{0,20}\n[-=]{3,})", re.MULTILINE)
    sections = []
    last_end = 0
    last_has_title = False

    for m in pattern.finditer(text):
        sec_start = last_end
        sec_text = text[last_end:m.start()]
        if sec_text.strip():
            sections.append((sec_text, sec_start, last_has_title))
        last_end = m.start()
        last_has_title = True

    # 剩余部分
    remainder = text[last_end:]
    if remainder.strip():
        sections.append((remainder, last_end, last_has_title))

    if not sections:
        sections = [(text, 0, False)]

    return sections


def _split_text_by_tokens(text: str, max_tokens: int) -> List[str]:
    """将文本强制按 token 上限分割成多段，忽略段落边界"""
    chunks = []
    while text:
        # 保留 low water mark 用于 overlap
        chunk = _take_by_tokens(text, max_tokens)
        chunks.append(chunk)
        # 截掉已取部分
        text = text[len(chunk):]
    return chunks


def _take_by_tokens(text: str, target_tokens: int) -> str:
    """从文本头部截取约 target_tokens 的字符"""
    if _approx_tokens(text) <= target_tokens:
        return text
    # 按比例估算字符数，保守取 80%
    ratio = target_tokens / max(_approx_tokens(text), 1)
    cut = int(len(text) * ratio * 0.8)
    # 回退到最近的分句处
    for sep in ("。", "！", "？", "\n", ".", "!", "?"):
        pos = text.rfind(sep, 0, cut)
        if pos > cut * 0.5:
            return text[:pos + 1]
    return text[:cut]


def _approx_tokens(text: str) -> int:
    """粗略估算 token 数（中英文混合）"""
    if not text:
        return 0
    # 中文约 1.5 chars/token，英文约 4 chars/token
    chinese_chars = len(re.findall(r'[一-鿿]', text))
    other_chars = len(text) - chinese_chars
    return int(chinese_chars / 1.5 + other_chars / 4)


def _tail_by_tokens(text: str, target_tokens: int) -> str:
    """从末尾保留约 target_tokens 的文本"""
    if _approx_tokens(text) <= target_tokens:
        return text
    # 按比例截取
    ratio = target_tokens / max(_approx_tokens(text), 1)
    cut_pos = max(0, int(len(text) * (1 - ratio * 1.2)))
    return text[cut_pos:]