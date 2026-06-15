#!/usr/bin/env python3
"""
8866 学习目录 - 知识导入流水线
独立运行：python3 ingest.py

流程：
  1. 扫描上传目录 + 打分
  2. 逐文件：提取/切片/摘要 → OpenViking + Hindsight → 同步到下载目录
  3. 完成后移动文件到 .processed
"""
import os
import sys
import json
import logging
import time
import yaml
import shutil
from datetime import datetime
from pathlib import Path

# 导入模块
from scanner import scan
from extractor import extract, SUPPORTED_EXTS as TEXT_EXTS
from transcriber import transcribe, is_supported as MEDIA_SUPPORTED
from chunker import chunk
from embedder import get_embedder, get_dedup_cache
from summarizer import summarize
from openviking_writer import write_knowledge_unit
from hindsight_writer import write_knowledge_to_hindsight
from sync_to_8866 import sync_result

# 路径
BASE_DIR = Path(__file__).parent.parent.parent.parent
DATA_DIR = Path("/root/lvhuamin/fileapple/data")
DATA_DIR.mkdir(parents=True, exist_ok=True)

# Registry
def _registry_path(cfg):
    return cfg.get("registry_path", str(DATA_DIR / "processed_registry.jsonl"))

def _load_registry(cfg):
    path = _registry_path(cfg)
    if not os.path.exists(path):
        return {}
    registry = {}
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                entry = json.loads(line)
                registry[entry["filename"]] = entry
            except json.JSONDecodeError:
                continue
    return registry

def _save_registry_entry(entry, cfg):
    path = _registry_path(cfg)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")

def _remove_from_registry(filename, cfg):
    path = _registry_path(cfg)
    if not os.path.exists(path):
        return
    entries = []
    with open(path, "r") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                e = json.loads(line)
                if e.get("filename") != filename:
                    entries.append(e)
            except json.JSONDecodeError:
                continue
    with open(path, "w") as f:
        for e in entries:
            f.write(json.dumps(e, ensure_ascii=False) + "\n")

# 日志
def setup_logging(log_dir, level="INFO"):
    os.makedirs(log_dir, exist_ok=True)
    log_file = os.path.join(log_dir, f"ingest_{time.strftime('%Y%m%d_%H%M%S')}.log")
    root = logging.getLogger()
    root.setLevel(getattr(logging, level.upper(), logging.INFO))
    fh = logging.FileHandler(log_file, encoding="utf-8")
    fh.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s"))
    root.addHandler(fh)
    ch = logging.StreamHandler(sys.stdout)
    ch.setFormatter(logging.Formatter("[%(levelname)s] %(message)s"))
    root.addHandler(ch)
    return log_file

# OOM保护
def _memory_ok(min_gb=3.0):
    try:
        with open("/proc/meminfo") as f:
            for line in f:
                parts = line.split()
                if parts[0].rstrip(":") == "MemAvailable":
                    return int(parts[1]) // (1024 * 1024) >= min_gb
    except:
        pass
    return True

# 归档
def _archive_file(filepath, archive_dir):
    try:
        os.makedirs(archive_dir, exist_ok=True)
        dest = os.path.join(archive_dir, os.path.basename(filepath))
        if os.path.exists(dest):
            base, ext = os.path.splitext(os.path.basename(filepath))
            dest = os.path.join(archive_dir, f"{base}_{int(time.time())}{ext}")
        shutil.move(filepath, dest)
        return True
    except Exception as e:
        logging.getLogger("ingestion.archive").warning("archive failed: %s", e)
        return False

# 处理单文件
def process_file(filepath, cfg):
    fname = os.path.basename(filepath)
    ext = os.path.splitext(filepath)[1].lower()
    logger = logging.getLogger("ingestion.process")

    if not _memory_ok(3.0):
        logger.critical("内存不足，跳过 %s", fname)
        return False

    logger.info("=" * 50)
    logger.info("处理: %s", fname)

    # Step 1: 提取文本
    text = None
    file_type = "unknown"
    if ext in TEXT_EXTS:
        text = extract(filepath)
        file_type = "text"
    elif MEDIA_SUPPORTED(filepath):
        text = transcribe(filepath)
        file_type = "media"
    else:
        logger.warning("不支持的文件类型: %s", ext)
        return False

    if not text or len(text.strip()) < 20:
        logger.warning("无法提取有效文本: %s", fname)
        write_knowledge_to_hindsight(
            filename=fname, file_type=file_type,
            knowledge={"summary": "", "knowledge_points": []},
            chunks=[], status="skip", error="no usable text",
            **cfg["memory"]["hindsight"],
        )
        return False

    # Step 2: 切片
    chunks = chunk(text, source=fname, max_tokens=cfg["chunking"]["max_tokens"], overlap_tokens=cfg["chunking"]["overlap_tokens"])
    logger.info("切片: %d 块", len(chunks))

    # Step 3: LLM摘要
    llm_cfg = cfg["llm"]
    knowledge = summarize(text, source=fname, api_url=llm_cfg["api_url"], api_key=llm_cfg["api_key"], model=llm_cfg["model"], temperature=llm_cfg["temperature"], max_tokens=llm_cfg["max_tokens"])
    if knowledge is None:
        knowledge = {"title": fname, "summary": text[:300], "knowledge_points": [], "domains": [], "_raw_source": fname}

    # Step 4: Embedding
    embedder = get_embedder(api_url=cfg["embedding"]["api_url"], model_name=cfg["embedding"]["model"], device=cfg["embedding"]["device"], batch_size=cfg["embedding"]["batch_size"])
    summary_text = knowledge.get("summary", text[:300])
    emb = embedder.encode([summary_text])
    embedding_vec = emb[0] if emb else None

    # Step 5: 去重
    dedup_cfg = cfg.get("dedup", {"threshold": 0.92, "cache_path": str(DATA_DIR / "processed_embeddings.jsonl")})
    dedup_cache = get_dedup_cache(cache_path=dedup_cfg.get("cache_path", str(DATA_DIR / "processed_embeddings.jsonl")))
    if embedding_vec and dedup_cache.is_duplicate(embedding_vec, threshold=dedup_cfg.get("threshold", 0.92)):
        logger.info("去重跳过: %s", fname)
        write_knowledge_to_hindsight(filename=fname, file_type=file_type, knowledge=knowledge, chunks=chunks, status="dedup_skip", **cfg["memory"]["hindsight"])
        return True

    # Step 6: 写入 OpenViking
    ov_cfg = cfg["memory"]["openviking"]
    ov_ok = write_knowledge_unit(unit=knowledge, chunks=chunks, base_url=ov_cfg["base_url"], api_key=ov_cfg["api_key"])

    if ov_ok and embedding_vec:
        dedup_cache.add(fname, summary_text, embedding_vec)

    # Step 7: 写入 Hindsight
    hi_cfg = cfg["memory"]["hindsight"]
    hindsight_ok = write_knowledge_to_hindsight(filename=fname, file_type=file_type, knowledge=knowledge, chunks=chunks, status="ok" if ov_ok else "write_failed", **hi_cfg)

    # Step 8: 同步到 8866 下载目录
    sync_base_dir = cfg.get("download_dir", "/root/.openclaw/workspace/learning/downloads")
    sync_result(filename=fname, file_type=file_type, knowledge=knowledge, chunks=chunks, base_dir=sync_base_dir, domains=knowledge.get("domains", []))

    # Step 9: 写入 registry + 归档
    if ov_ok:
        entry = {
            "filename": fname, "filepath": filepath, "status": "ok",
            "processed_at": datetime.now().isoformat(), "file_type": file_type,
            "chunk_count": len(chunks), "kp_count": len(knowledge.get("knowledge_points", [])),
            "domains": knowledge.get("domains", []), "summary": summary_text[:200],
        }
        _save_registry_entry(entry, cfg)
        archive_dir = cfg.get("archive_dir", "/root/.openclaw/workspace/learning/uploads/.processed")
        if _archive_file(filepath, archive_dir):
            logger.info("已归档: %s", fname)

    logger.info("完成: %s → OV=%s HI=%s", fname, "OK" if ov_ok else "FAIL", "OK" if hindsight_ok else "FAIL")
    return ov_ok

# 批量处理
def process_batch(files, cfg, max_files=20):
    ok = fail = skip = 0
    for i, f in enumerate(files[:max_files]):
        logger = logging.getLogger("ingestion.batch")
        logger.info("[%d/%d] priority=%.0f %s", i+1, min(max_files, len(files)), f.get("priority", 0), f["name"])
        try:
            if process_file(f["path"], cfg):
                ok += 1
            else:
                fail += 1
        except Exception as e:
            logger.error("处理失败 %s: %s", f["name"], e, exc_info=True)
            fail += 1
        if i < min(max_files, len(files)) - 1:
            time.sleep(3)
    return ok, fail, skip

# CLI
def main():
    import argparse
    parser = argparse.ArgumentParser(description="8866 知识导入流水线")
    parser.add_argument("--config", default="config.yaml", help="配置文件")
    parser.add_argument("--max-files", type=int, default=None, help="处理数量")
    parser.add_argument("--scan-only", action="store_true", help="仅扫描")
    parser.add_argument("--force", type=str, help="强制处理单文件")
    parser.add_argument("--reset", type=str, help="从registry移除")
    args = parser.parse_args()

    config_path = Path(__file__).parent / args.config
    with open(config_path, "r", encoding="utf-8") as f:
        cfg = yaml.safe_load(f)

    log_file = setup_logging(cfg["log"]["dir"], cfg["log"]["level"])
    logger = logging.getLogger("ingestion.main")
    logger.info("8866 知识导入流水线启动 | log=%s", log_file)

    # reset 模式
    if args.reset:
        _remove_from_registry(args.reset, cfg)
        logger.info("已移除: %s", args.reset)
        sys.exit(0)

    max_files = args.max_files or cfg["priority"]["max_files_per_run"]

    # 强制处理
    if args.force:
        filepath = args.force
        if not os.path.isfile(filepath):
            logger.error("文件不存在: %s", filepath)
            sys.exit(1)
        success = process_file(filepath, cfg)
        logger.info("结果: %s", "OK" if success else "FAIL")
        sys.exit(0 if success else 1)

    # 扫描
    input_dir = cfg["input_dir"]
    logger.info("扫描: %s", input_dir)
    registry = _load_registry(cfg)
    all_files = scan(input_dir)
    pending_files = [f for f in all_files if f["name"] not in registry]
    skipped = len(all_files) - len(pending_files)
    if skipped > 0:
        logger.info("已跳过 %d 个", skipped)
    if not pending_files:
        logger.warning("没有待处理文件")
        sys.exit(0)

    logger.info("扫描: 共 %d 个，待处理 %d 个", len(all_files), len(pending_files))

    if args.scan_only:
        print(json.dumps(pending_files[:50], ensure_ascii=False, indent=2, default=str))
        sys.exit(0)

    ok, fail, skip = process_batch(pending_files, cfg, max_files)

    logger.info("=" * 50)
    logger.info("完成: ✅ %d | ❌ %d | ⏭️ %d", ok, fail, skip)
    logger.info("日志: %s", log_file)
    print(f"\n结果: ✅ {ok} | ❌ {fail} | ⏭️ {skip}")
    print(f"待处理剩余: {len(pending_files) - ok - fail - skip} 个")

if __name__ == "__main__":
    main()
