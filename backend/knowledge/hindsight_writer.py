"""
Hindsight 写入器 — 知识导入工作记忆
写入内容：L0摘要 + knowledge_points（用于会话召回）
"""
import json
import logging
from datetime import datetime
from typing import Dict, List
from urllib import request as urllib_request

logger = logging.getLogger("ingestion.hindsight_writer")


def write_processing_log(
    filename: str,
    file_type: str,
    status: str,
    summary: str = "",
    chunk_count: int = 0,
    knowledge_points: int = 0,
    error: str = "",
    base_url: str = "http://localhost:8888",
    bank_id: str = "shared",
) -> bool:
    """兼容旧接口（处理日志）"""
    return write_knowledge_to_hindsight(
        filename=filename,
        file_type=file_type,
        knowledge={"summary": summary, "knowledge_points": []},
        chunks=[],
        status=status,
        error=error,
        base_url=base_url,
        bank_id=bank_id,
    )


def write_knowledge_to_hindsight(
    filename: str,
    file_type: str,
    knowledge: Dict,
    chunks: List[Dict],
    status: str = "ok",
    error: str = "",
    base_url: str = "http://localhost:8888",
    bank_id: str = "shared",
) -> bool:
    """
    将知识写入 Hindsight 工作记忆。

    写入内容：
    - L0 摘要（一句话）
    - 所有 knowledge_points（概念 + 定义）
    - 领域标签
    - 处理状态和时间戳

    用于：会话中语义召回"之前学过什么"
    """
    try:
        summary = knowledge.get("summary", "")
        kp_list = knowledge.get("knowledge_points", [])
        domains = knowledge.get("domains", [])

        # ── 组装记忆内容 ──────────────────────────────────────
        lines = [f"【知识导入】{filename}"]

        if status == "ok":
            lines.append(f"✓ 处理成功 | 类型: {file_type} | 切片: {len(chunks)}")

            if summary:
                lines.append(f"\n📌 摘要: {summary}")

            if kp_list:
                lines.append("\n📚 知识点:")
                for kp in kp_list:
                    concept = kp.get("concept", "未知概念")
                    definition = kp.get("definition", "（无定义）")
                    lines.append(f"  • {concept}: {definition}")

            if domains:
                lines.append(f"\n🏷️ 领域: {', '.join(domains)}")

        elif status == "dedup_skip":
            lines.append(f"⏭️ 去重跳过（与已有知识重复） | 摘要: {summary[:100]}")

        elif status == "error":
            lines.append(f"✗ 处理失败 | 错误: {error[:200]}")

        else:
            lines.append(f"状态: {status}")

        lines.append(f"\n⏰ 处理时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

        content = "\n".join(lines)

        # ── 构造 tags ────────────────────────────────────────
        tags = [
            "source:ingestion-pipeline",
            f"filetype:{file_type}",
            f"status:{status}",
        ]
        if domains:
            for d in domains[:3]:
                tags.append(f"domain:{d}")

        payload = {
            "bank_id": bank_id,
            "items": [
                {
                    "content": content,
                    "fact_type": "experience",
                    "tags": tags,
                }
            ],
        }

        url = f"{base_url}/v1/default/banks/{bank_id}/memories"
        data = json.dumps(payload).encode("utf-8")
        req = urllib_request.Request(
            url,
            data=data,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib_request.urlopen(req, timeout=30) as resp:
            result = json.loads(resp.read().decode("utf-8"))
            if result.get("success") is not True:
                logger.warning("Hindsight write returned non-success: %s", result)
            else:
                logger.debug("Hindsight knowledge written: %s (%d kps)", filename, len(kp_list))
            return True

    except Exception as e:
        logger.warning("Hindsight write failed (non-fatal): %s", e)
        return False
