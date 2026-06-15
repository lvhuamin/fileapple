"""
知识提炼器 — 调用 LLM 对文本做摘要 + 知识点提取
输出结构化知识单元（knowledge unit）
"""
import json
import logging
from typing import Dict, List
from urllib import request as urllib_request

logger = logging.getLogger("ingestion.summarizer")


SYSTEM_PROMPT = """你是一个知识提炼助手。给定一段学习资料文本，提取关键知识点，输出结构化 JSON。

必须输出纯 JSON，不要包含 ```json 标记或其他说明文字。

输出格式：
{
  "title": "提炼后的标题（10字以内）",
  "summary": "核心摘要（100字以内）",
  "knowledge_points": [
    {
      "concept": "概念/知识点名称",
      "definition": "一句话定义",
      "tags": ["标签1", "标签2"]
    }
  ],
  "domains": ["所属领域，如 Python/运维/AI/小说/交易"]
}"""


def summarize(
    text: str,
    source: str = "",
    api_url: str = "",
    api_key: str = "",
    model: str = "",
    temperature: float = 0.3,
    max_tokens: int = 2048,
) -> Dict | None:
    """
    对文本做 LLM 摘要 + 知识点提取。
    返回结构化知识单元 dict。
    """
    if not text or len(text.strip()) < 50:
        logger.warning("text too short to summarize: %s (%d chars)", source, len(text or ""))
        return None

    # 截断过长文本（token 超限保护）
    if len(text) > 8000:
        text = text[:8000] + "\n\n[...truncated]"

    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": f"资料来源: {source}\n\n{text}"},
        ],
        "temperature": temperature,
        "max_tokens": max_tokens,
    }

    try:
        data = json.dumps(payload).encode("utf-8")
        req = urllib_request.Request(
            api_url,
            data=data,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {api_key}",
            },
            method="POST",
        )

        with urllib_request.urlopen(req, timeout=600) as resp:
            body = json.loads(resp.read().decode("utf-8"))

        content = body.get("choices", [{}])[0].get("message", {}).get("content", "")
        if not content:
            logger.warning("LLM returned empty content for %s", source)
            return _fallback(text, source)

        # 清理可能的 ```json 包裹
        content = content.strip()
        if content.startswith("```"):
            content = content[content.index("\n") + 1:]
        if content.endswith("```"):
            content = content[:-3].strip()

        result = json.loads(content)
        result["_raw_source"] = source
        logger.info("summarized: %s → %d knowledge points", source, len(result.get("knowledge_points", [])))
        return result

    except Exception as e:
        logger.error("LLM summarize failed [%s]: %s", source, e)
        return _fallback(text, source)


def _fallback(text: str, source: str) -> Dict:
    """LLM 调用失败时的兜底摘要"""
    return {
        "title": source,
        "summary": text[:200] + "..." if len(text) > 200 else text,
        "knowledge_points": [],
        "domains": [],
        "_raw_source": source,
        "_fallback": True,
    }


def summarize_batch(
    chunks: List[Dict],
    source: str = "",
    api_url: str = "",
    api_key: str = "",
    model: str = "",
    temperature: float = 0.3,
    max_tokens: int = 2048,
) -> List[Dict]:
    """
    对多个切片分别做摘要。每片独立调用 LLM。
    """
    results = []
    for i, chunk in enumerate(chunks):
        res = summarize(
            chunk["text"],
            source=f"{source}[{i}]",
            api_url=api_url,
            api_key=api_key,
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
        )
        if res:
            res["_chunk_index"] = chunk["index"]
            results.append(res)
    return results