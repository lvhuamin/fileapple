"""
智能文本切片 — 按标题/段落/句子三级分割，保证语义完整
输出切片列表，每个切片带元信息
"""
import re
import logging
from typing import List, Dict, Tuple

logger = logging.getLogger("ingestion.chunker")

# 句子分隔符（按优先级）
_SENT_SEPS = re.compile(r'(?<=[。！？；\n])\s*')


def chunk(
    text: str,
    source: str = "",
    max_tokens: int = 1000,
    overlap_tokens: int = 200,
) -> List[Dict]:
    """
    将长文本切分为知识块。

    分割策略（优先级从高到低）：
      1. 按标题分割
      2. 按段落（空行）分割
      3. 按句子分割
      4. 兜底：按字符截断（仅当单句超长时）

    overlap：只取上一片最后一个完整句子作为上下文，不重复拼接。

    返回:
        [{"index": 0, "text": "...", "char_start": 0, "char_end": 500,
          "approx_tokens": 120, "has_title": True}, ...]
    """
    if not text or not text.strip():
        logger.warning("empty text for %s", source)
        return []

    # Step 1: 按标题分割为大段
    sections = _split_by_heading(text)

    # Step 2: 对每个大段，按段落 → 句子 逐级填充
    all_units: List[Tuple[str, int, bool]] = []  # (text, char_start, has_title)
    for sec_text, sec_start, sec_has_title in sections:
        if _approx_tokens(sec_text) <= max_tokens:
            all_units.append((sec_text, sec_start, sec_has_title))
        else:
            # 大段内部：按段落分割，段落内按句子分割
            sub_units = _split_section_to_units(sec_text, sec_start, sec_has_title)
            all_units.extend(sub_units)

    # Step 3: 贪心合并 units 到 chunks
    chunks = []
    buffer = ""
    buffer_start = 0
    buffer_has_title = False

    for unit_text, unit_start, unit_has_title in all_units:
        unit_tokens = _approx_tokens(unit_text)

        # 单个 unit 就超限 → 直接作为独立 chunk（内部已尽力分割）
        if unit_tokens > max_tokens:
            # 先 flush buffer
            if buffer.strip():
                _flush_chunk(chunks, buffer, buffer_start, buffer_has_title)
                buffer = ""
                buffer_start = 0
            _flush_chunk(chunks, unit_text, unit_start, unit_has_title)
            continue

        # buffer + unit 超限 → flush buffer，unit 进新 buffer
        if buffer and _approx_tokens(buffer + "\n" + unit_text) > max_tokens:
            _flush_chunk(chunks, buffer, buffer_start, buffer_has_title)
            # 新 buffer 以当前 unit 开始（不带 overlap，避免重复）
            buffer = unit_text
            buffer_start = unit_start
            buffer_has_title = unit_has_title
        else:
            # 合并到 buffer
            if not buffer:
                buffer_start = unit_start
                buffer_has_title = unit_has_title
                buffer = unit_text
            else:
                buffer = buffer + "\n" + unit_text

    # flush 剩余
    if buffer.strip():
        _flush_chunk(chunks, buffer, buffer_start, buffer_has_title)

    # Step 4: 添加 overlap（上一片最后一个完整句子）
    if overlap_tokens > 0 and len(chunks) > 1:
        _add_overlap(chunks, overlap_tokens)

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


def _add_overlap(chunks: List[Dict], overlap_tokens: int):
    """给每个 chunk（除第一个）的开头添加上一片最后一个完整句子作为上下文"""
    for i in range(1, len(chunks)):
        prev_text = chunks[i - 1]["text"]
        # 从上一片末尾提取最后一个完整句子
        last_sentence = _extract_last_sentence(prev_text)
        if last_sentence and _approx_tokens(last_sentence) <= overlap_tokens:
            chunks[i]["text"] = last_sentence + " " + chunks[i]["text"]
            chunks[i]["overlap_from"] = i - 1


def _extract_last_sentence(text: str) -> str:
    """提取文本最后一个完整句子"""
    # 按句末标点分割
    sentences = _SENT_SEPS.split(text.strip())
    # 过滤空串
    sentences = [s.strip() for s in sentences if s.strip()]
    if sentences:
        return sentences[-1]
    return ""


# ── 段落级分割 ──────────────────────────────────────────

def _split_section_to_units(
    text: str, char_start: int, has_title: bool
) -> List[Tuple[str, int, bool]]:
    """
    将一个大段按段落 → 句子 逐级分割为语义单元。
    返回 [(unit_text, unit_char_start, has_title), ...]
    """
    units = []

    # 按空行（段落）分割
    paragraphs = re.split(r'\n\s*\n', text)

    for para in paragraphs:
        para = para.strip()
        if not para:
            continue

        para_tokens = _approx_tokens(para)

        # 段落够短，直接作为 unit
        if para_tokens <= 500:  # 段落级上限，留余量给合并
            units.append((para, char_start, has_title))
            char_start += len(para) + 2  # +2 for \n\n
            has_title = False  # 只有第一个 unit 带标题
            continue

        # 段落太长，按句子分割
        sentences = _split_by_sentences(para)
        for sent in sentences:
            units.append((sent, char_start, has_title))
            char_start += len(sent)
            has_title = False

    return units


def _split_by_sentences(text: str) -> List[str]:
    """按句子分割文本，保留句末标点"""
    parts = _SENT_SEPS.split(text)
    return [p.strip() for p in parts if p.strip()]


# ── 标题分割 ────────────────────────────────────────────

def _split_by_heading(text: str):
    """
    按 ## / ### / --- 等标题标记分割，保留标题行。
    返回 [(section_text, char_start, has_heading)]
    """
    pattern = re.compile(
        r"(^|\n)(#{1,6}\s+|第[一二三四五六七八九十\d]+[章节篇部分]|[A-Z][^。\n]{0,20}\n[-=]{3,})",
        re.MULTILINE,
    )
    sections = []
    last_end = 0
    last_has_title = False

    for m in pattern.finditer(text):
        sec_start = last_end
        sec_text = text[last_end : m.start()]
        if sec_text.strip():
            sections.append((sec_text, sec_start, last_has_title))
        last_end = m.start()
        last_has_title = True

    remainder = text[last_end:]
    if remainder.strip():
        sections.append((remainder, last_end, last_has_title))

    if not sections:
        sections = [(text, 0, False)]

    return sections


# ── token 估算 ──────────────────────────────────────────

def _approx_tokens(text: str) -> int:
    """粗略估算 token 数（中英文混合）"""
    if not text:
        return 0
    chinese_chars = len(re.findall(r'[一-鿿]', text))
    other_chars = len(text) - chinese_chars
    return int(chinese_chars / 1.5 + other_chars / 4)
