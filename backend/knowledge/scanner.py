#!/usr/bin/env python3
"""
文件扫描器 — 扫描输入目录，分类 + 打分 + 排优先级
独立可运行：python3 scanner.py --dir /data/8866-uploads

输出：按优先级排序的文件列表（JSON）
"""
import os
import sys
import json
import time
import logging
from typing import List, Dict
from pathlib import Path

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("scanner")

# 文件类型分类
CATEGORIES = {
    "ebook": {".pdf", ".epub", ".mobi", ".azw3", ".djvu"},
    "document": {".docx", ".doc", ".txt", ".md", ".csv", ".xlsx", ".pptx"},
    "video": {".mp4", ".avi", ".mov", ".mkv", ".flv", ".wmv", ".webm"},
    "audio": {".mp3", ".wav", ".flac", ".aac", ".ogg", ".m4a", ".wma"},
    "code": {".py", ".js", ".ts", ".go", ".rs", ".java", ".cpp", ".yaml", ".json", ".sh"},
    "image": {".jpg", ".jpeg", ".png", ".gif", ".bmp", ".svg", ".webp"},
}

# 优先级加分域（文件名或路径包含以下关键词）
DOMAIN_BONUS = {
    "python": 20, "py": 20,
    "运维": 20, "ops": 20, "devops": 20, "deploy": 20,
    "ai": 18, "agent": 18, "llm": 18, "rag": 18,
    "小说": 15, "novel": 15, "story": 15, "写作": 15,
    "交易": 15, "trade": 15, "quant": 15, "stock": 15,
    "测试": 12, "test": 12,
    "安全": 12, "security": 12, "pentest": 12,
}


def scan(directory: str) -> List[Dict]:
    """扫描目录，返回带优先级的文件列表"""
    if not os.path.isdir(directory):
        logger.error("directory not found: %s", directory)
        return []

    files = []
    for root, dirs, fnames in os.walk(directory):
        # 跳过 .processed 目录
        if ".processed" in root:
            continue
        for fname in fnames:
            filepath = os.path.join(root, fname)
            try:
                stat = os.stat(filepath)
            except OSError:
                continue

            if stat.st_size == 0:
                continue

            entry = {
                "path": filepath,
                "name": fname,
                "ext": os.path.splitext(fname)[1].lower(),
                "size": stat.st_size,
                "size_str": _fmt_size(stat.st_size),
                "mtime": stat.st_mtime,
                "mtime_str": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(stat.st_mtime)),
                "category": _classify(fname),
                "priority": 0,
            }

            entry["priority"] = _score(entry)
            files.append(entry)

    # 按优先级降序
    files.sort(key=lambda f: f["priority"], reverse=True)
    logger.info("scanned %s: %d files, top priority=%.0f", directory, len(files), files[0]["priority"] if files else 0)
    return files


def _classify(filename: str) -> str:
    ext = os.path.splitext(filename)[1].lower()
    for cat, exts in CATEGORIES.items():
        if ext in exts:
            return cat
    return "other"


def _score(entry: Dict) -> float:
    """综合优先级打分（0-100）"""
    score = 0

    # 类型加分
    cat = entry["category"]
    if cat == "ebook":
        score += 25
    elif cat == "document":
        score += 20
    elif cat in ("video", "audio"):
        score += 15
    elif cat == "code":
        score += 10
    elif cat == "image":
        score += 5

    # 大小减分（>500MB 降权）
    size_mb = entry["size"] / (1024 * 1024)
    if size_mb > 500:
        score -= 20
    elif size_mb > 100:
        score -= 10
    elif size_mb > 50:
        score -= 5
    elif size_mb < 1:
        score += 5  # 小文件优先

    # 新文件加分（7天内）
    age_hours = (time.time() - entry["mtime"]) / 3600
    if age_hours < 24:
        score += 10
    elif age_hours < 168:
        score += 5

    # 域名匹配加分
    name_lower = entry["name"].lower()
    for keyword, bonus in DOMAIN_BONUS.items():
        if keyword in name_lower:
            score += bonus
            break  # 只加一次

    return max(0, min(100, score))


def _fmt_size(size: int) -> str:
    for unit in ("B", "KB", "MB", "GB"):
        if size < 1024:
            return f"{size:.1f}{unit}"
        size /= 1024
    return f"{size:.1f}TB"


# ── CLI ─────────────────────────────────────────────────
if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="知识导入文件扫描器")
    parser.add_argument("--dir", default="/data/8866-uploads", help="扫描目录")
    parser.add_argument("--top", type=int, default=20, help="显示前 N 条")
    parser.add_argument("--json", action="store_true", help="输出 JSON")
    args = parser.parse_args()

    files = scan(args.dir)
    if args.json:
        print(json.dumps(files[:args.top], ensure_ascii=False, indent=2))
    else:
        print(f"\n{'优先级':>6} {'大小':>10} {'分类':>10} {'修改时间':>19}  文件名")
        print("-" * 80)
        for f in files[:args.top]:
            print(f"{f['priority']:>6.0f} {f['size_str']:>10} {f['category']:>10} {f['mtime_str']:>19}  {f['name']}")
        print(f"\n共 {len(files)} 个文件，显示前 {args.top} 个")