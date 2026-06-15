#!/usr/bin/env python3
"""
知识导入结果同步到8866下载目录

功能：
1. 处理完成后，将摘要/知识点同步到8866下载目录
2. 按分类目录存放：技术运维/心理学/恋爱心理/文档/测试报告/其他
3. 生成 Markdown 格式的知识卡片便于下载阅读

用法：
  from lib.sync_to_8866 import sync_result
  sync_result(filename, file_type, knowledge, chunks, base_dir)
"""
import os
import json
import logging
from datetime import datetime
from typing import Dict, List, Optional

logger = logging.getLogger("sync_to_8866")

# 域分类映射
DOMAIN_CATEGORY_MAP = {
    "python": "技术运维",
    "py": "技术运维",
    "运维": "技术运维",
    "ops": "技术运维",
    "devops": "技术运维",
    "deploy": "技术运维",
    "ai": "技术运维",
    "agent": "技术运维",
    "llm": "技术运维",
    "rag": "技术运维",
    "code": "技术运维",
    "交易": "其他",
    "trade": "其他",
    "quant": "其他",
    "stock": "其他",
    "测试": "测试报告",
    "test": "测试报告",
    "安全": "测试报告",
    "security": "测试报告",
    "pentest": "测试报告",
    "心理学": "心理学",
    "psychology": "心理学",
    "恋爱": "恋爱心理",
    "love": "恋爱心理",
    "relationship": "恋爱心理",
    "novel": "其他",
    "小说": "其他",
    "ebook": "文档",
    "pdf": "文档",
    "epub": "文档",
}

DEFAULT_CATEGORY = "文档"


def _get_category(filename: str, domains: List[str]) -> str:
    """根据文件名和领域确定分类目录"""
    # 先用领域匹配
    for domain in domains:
        domain_lower = domain.lower()
        for key, cat in DOMAIN_CATEGORY_MAP.items():
            if key in domain_lower:
                return cat

    # 用文件名匹配
    filename_lower = filename.lower()
    for key, cat in DOMAIN_CATEGORY_MAP.items():
        if key in filename_lower:
            return cat

    return DEFAULT_CATEGORY


def _sanitize_filename(name: str) -> str:
    """清理文件名，去除特殊字符"""
    # 去除扩展名
    name = os.path.splitext(name)[0]
    # 替换特殊字符
    for char in ['/', '\\', ':', '*', '?', '"', '<', '>', '|', '\n', '\r']:
        name = name.replace(char, '_')
    # 限制长度
    if len(name) > 100:
        name = name[:100]
    return name


def _generate_markdown(filename: str, file_type: str, knowledge: Dict, chunks: List[Dict], domains: List[str]) -> str:
    """生成 Markdown 格式的知识卡片"""
    title = knowledge.get("title", _sanitize_filename(filename))
    summary = knowledge.get("summary", "")
    kps = knowledge.get("knowledge_points", [])

    md = f"""# {title}

> **文件来源**: {filename}
> **处理时间**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
> **类型**: {file_type}
> **领域**: {', '.join(domains) if domains else '未分类'}

---

## 摘要

{summary}

"""

    # 添加知识点
    if kps:
        md += "## 核心知识点\n\n"
        for i, kp in enumerate(kps, 1):
            if isinstance(kp, dict):
                point = kp.get("point", str(kp))
                explanation = kp.get("explanation", "")
                md += f"{i}. **{point}**"
                if explanation:
                    md += f"\n   - {explanation}"
                md += "\n"
            else:
                md += f"{i}. {kp}\n"
        md += "\n"

    # 添加领域标签
    if domains:
        md += "---\n\n**领域标签**: "
        md += " | ".join([f"`{d}`" for d in domains])
        md += "\n"

    # 元信息
    md += f"""
---

*本文件由知识导入流水线自动生成 | {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}*
"""

    return md


def _generate_json_summary(filename: str, file_type: str, knowledge: Dict, chunks: List[Dict], domains: List[str]) -> str:
    """生成 JSON 格式的摘要"""
    data = {
        "filename": filename,
        "file_type": file_type,
        "processed_at": datetime.now().isoformat(),
        "title": knowledge.get("title", filename),
        "summary": knowledge.get("summary", ""),
        "knowledge_points": knowledge.get("knowledge_points", []),
        "domains": domains,
        "chunk_count": len(chunks) if chunks else 0,
    }
    return json.dumps(data, ensure_ascii=False, indent=2)


def sync_result(
    filename: str,
    file_type: str,
    knowledge: Dict,
    chunks: List[Dict],
    base_dir: str = "/root/.openclaw/workspace/learning/downloads",
    domains: Optional[List[str]] = None
) -> bool:
    """
    将处理结果同步到8866下载目录

    Args:
        filename: 原始文件名
        file_type: 文件类型 (text/media)
        knowledge: LLM摘要结果 (title/summary/knowledge_points/domains)
        chunks: 切片列表
        base_dir: 下载目录根路径
        domains: 领域标签列表

    Returns:
        bool: 是否成功
    """
    if domains is None:
        domains = knowledge.get("domains", [])

    logger = logging.getLogger("sync_to_8866")

    # 确定分类目录
    category = _get_category(filename, domains)
    target_dir = os.path.join(base_dir, category)

    try:
        os.makedirs(target_dir, exist_ok=True)
    except Exception as e:
        logger.error("无法创建目录 %s: %s", target_dir, e)
        return False

    # 生成干净的文件名
    clean_name = _sanitize_filename(filename)
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')

    # 1. 写入 Markdown 知识卡片
    md_filename = f"{clean_name}_{timestamp}.md"
    md_path = os.path.join(target_dir, md_filename)

    try:
        md_content = _generate_markdown(filename, file_type, knowledge, chunks, domains)
        with open(md_path, "w", encoding="utf-8") as f:
            f.write(md_content)
        logger.info("已同步 Markdown: %s", md_path)
    except Exception as e:
        logger.error("写入 Markdown 失败 %s: %s", md_path, e)
        return False

    # 2. 写入 JSON 摘要（可选，用于程序读取）
    json_filename = f"{clean_name}_{timestamp}.json"
    json_path = os.path.join(target_dir, json_filename)

    try:
        json_content = _generate_json_summary(filename, file_type, knowledge, chunks, domains)
        with open(json_path, "w", encoding="utf-8") as f:
            f.write(json_content)
        logger.info("已同步 JSON: %s", json_path)
    except Exception as e:
        logger.warning("写入 JSON 失败 %s: %s (非致命)", json_path, e)

    return True


# ── CLI ──────────────────────────────────────────────────────

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="同步知识导入结果到8866下载目录")
    parser.add_argument("--file", required=True, help="原始文件名")
    parser.add_argument("--type", default="text", help="文件类型")
    parser.add_argument("--summary", required=True, help="摘要文本")
    parser.add_argument("--domains", help="领域标签，逗号分隔")
    parser.add_argument("--base-dir", default="/root/.openclaw/workspace/learning/downloads", help="下载目录")
    args = parser.parse_args()

    domains = args.domains.split(",") if args.domains else []

    knowledge = {
        "title": os.path.splitext(args.file)[0],
        "summary": args.summary,
        "knowledge_points": [],
        "domains": domains,
    }

    success = sync_result(
        filename=args.file,
        file_type=args.type,
        knowledge=knowledge,
        chunks=[],
        base_dir=args.base_dir,
        domains=domains,
    )

    print(f"同步结果: {'✅ 成功' if success else '❌ 失败'}")
