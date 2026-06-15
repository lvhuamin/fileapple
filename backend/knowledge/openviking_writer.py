"""
OpenViking 写入器 — L0/L1/L2 三层知识结构写入

目录结构:
  viking://resources/knowledge-base/{domain}/{filename}/
      L0.md              # 一句话摘要 (~100字)
      L1.md              # 概览 (title + domains + knowledge_points列表)
      L2/                # 完整内容
          chunk_000.md   # 原文切片
          chunk_001.md
          kp_000.md      # 知识点完整定义
          kp_001.md
"""
import json
import logging
from typing import Dict, List
from urllib import request as urllib_request

logger = logging.getLogger("ingestion.openviking_writer")

KNOWLEDGE_ROOT = "viking://resources/knowledge-base/"


def write_knowledge_unit(
    unit: Dict,
    chunks: List[Dict],
    base_url: str,
    api_key: str,
) -> bool:
    """
    写入一条知识单元到 OpenViking（L0/L1/L2 三层）。

    Args:
        unit: LLM 提炼出的知识单元，结构如下：
            {
                "title": "...",
                "summary": "100字以内摘要",
                "knowledge_points": [{"concept": "...", "definition": "...", "tags": [...]}],
                "domains": ["Python", "AI"],
                "_raw_source": "chapter八_dubbed.mp3"
            }
        chunks: chunker 产生的切片列表，每个元素:
            {"index": 0, "text": "...", "approx_tokens": 120, ...}
        base_url: OpenViking API 地址
        api_key: OpenViking API key
    """
    try:
        domains = unit.get("domains", ["general"])
        domain = domains[0] if domains else "general"
        filename = _sanitize_filename(unit.get("_raw_source", "unknown"))
        base = f"{KNOWLEDGE_ROOT}{domain}/{filename}"

        # 0. 创建基础目录
        _mkdir(base, base_url, api_key)
        # 创建 L2 目录
        l2_dir = f"{base}/L2"
        _mkdir(l2_dir, base_url, api_key)

        # ── L0: 一句话摘要 ──────────────────────────────────────
        l0_content = f"""{unit.get("summary", unit.get("title", filename))}
---
来源: {unit.get("_raw_source", "unknown")}
"""
        _write_file(f"{base}/L0.md", l0_content, base_url, api_key)

        # ── L1: 概览（title + domains + 知识点列表） ──────────
        kp_lines = []
        for i, kp in enumerate(unit.get("knowledge_points", [])):
            kp_lines.append(f"- **{kp.get('concept', f'概念{i}')}**: {kp.get('definition', '')}")
        kp_text = "\n".join(kp_lines) if kp_lines else "（无知识点）"

        l1_content = f"""# {unit.get("title", filename)}

**来源:** {unit.get("_raw_source", "unknown")}
**领域:** {', '.join(domains)}

## 核心知识点

{kp_text}

## 切片数: {len(chunks)}
"""
        _write_file(f"{base}/L1.md", l1_content, base_url, api_key)

        # ── L2: 原文切片 ───────────────────────────────────────
        for chunk in chunks:
            chunk_path = f"{l2_dir}/chunk_{chunk['index']:03d}.md"
            chunk_content = f"""# 切片 {chunk['index']}

**来源:** {unit.get("_raw_source", "unknown")} (char {chunk['char_start']}-{chunk['char_end']})
**token数:** ~{chunk.get('approx_tokens', 0)}

---

{chunk['text']}
"""
            _write_file(chunk_path, chunk_content, base_url, api_key)

        # ── L2: 知识点完整定义 ──────────────────────────────────
        for i, kp in enumerate(unit.get("knowledge_points", [])):
            kp_path = f"{l2_dir}/kp_{i:03d}.md"
            kp_tags = ", ".join(kp.get("tags", []))
            kp_content = f"""# {kp.get('concept', f'知识点{i}')}

**定义:** {kp.get('definition', '（无定义）')}
**标签:** {kp_tags}
**来源:** {unit.get("_raw_source", "unknown")}

---

## 相关切片

"""
            # 找相关切片（简单：按顺序关联）
            # 实际场景中可用 embedding 做语义关联，此处做线性映射
            related = chunks[i % len(chunks)] if chunks else None
            if related:
                kp_content += f"> {related['text'][:300]}..."

            _write_file(kp_path, kp_content, base_url, api_key)

        logger.info(
            "OpenViking write OK: %s (%s) | chunks=%d kps=%d",
            base, domain, len(chunks), len(unit.get("knowledge_points", []))
        )
        return True

    except Exception as e:
        logger.error("OpenViking write failed: %s", e)
        return False


def _mkdir(uri: str, base_url: str, api_key: str):
    """创建目录（忽略已存在错误）"""
    url = f"{base_url}/api/v1/fs/mkdir"
    payload = {"uri": uri}
    data = json.dumps(payload).encode("utf-8")
    req = urllib_request.Request(
        url, data=data,
        headers={
            "Content-Type": "application/json",
            "X-OpenViking-Account": "default",
            "X-OpenViking-User": "shared",
            "x-api-key": api_key,
        },
        method="POST",
    )
    with urllib_request.urlopen(req, timeout=15) as resp:
        resp_body = json.loads(resp.read().decode("utf-8"))
        if resp_body.get("status") != "ok":
            raise RuntimeError(f"OpenViking mkdir error: {resp_body}")


def _write_file(uri: str, content: str, base_url: str, api_key: str):
    """调 OpenViking API 写入文件"""
    url = f"{base_url}/api/v1/content/write"
    payload = {
        "uri": uri,
        "content": content,
        "mode": "create",
    }
    data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = urllib_request.Request(
        url,
        data=data,
        headers={
            "Content-Type": "application/json",
            "X-OpenViking-Account": "default",
            "X-OpenViking-User": "shared",
            "x-api-key": api_key,
        },
        method="POST",
    )
    with urllib_request.urlopen(req, timeout=30) as resp:
        resp_body = json.loads(resp.read().decode("utf-8"))
        if resp_body.get("status") != "ok":
            raise RuntimeError(f"OpenViking write error: {resp_body}")


def _sanitize_filename(name: str) -> str:
    """清理文件名（去掉路径、后缀）"""
    import os
    import re
    name = os.path.basename(name)
    name = os.path.splitext(name)[0]
    name = re.sub(r'[\\/:*?"<>|]', '_', name)
    name = name.strip("_ ") or "unknown"
    return name
