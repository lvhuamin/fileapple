#!/usr/bin/env python3
"""
学习目录后端 - FastAPI
分片上传 + 断点续传 + 音频转文字 + 文件管理（浏览/搜索/预览/分享）
"""

import os
import sys
import json
import uuid
import hashlib
import asyncio
import aiofiles
import logging
import traceback
from pathlib import Path as PathLib
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any

from fastapi import FastAPI, UploadFile, File, HTTPException, Form, WebSocket, WebSocketDisconnect, Query, Path, Body, Request
from fastapi.responses import RedirectResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, StreamingResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
import uvicorn

# ========== 日志配置 ==========
LOG_DIR = PathLib("/root/.openclaw/workspace/learning/logs")
LOG_DIR.mkdir(parents=True, exist_ok=True)

LOG_FILE = PathLib("/tmp/fileapple.log")
LOG_ERROR_FILE = PathLib("/tmp/fileapple_error.log")  # 错误日志单独一份

# 日志轮转：每天一个文件，最多保留30天
from logging.handlers import TimedRotatingFileHandler

_log_formatter = logging.Formatter(
    '%(asctime)s [%(levelname)-5s] [%(process)d:%(thread)d] %(name)s: %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)

# 实时日志（stdout + 当日文件 + /tmp/fileapple.log）
_stdout_handler = logging.StreamHandler(sys.stdout)
_stdout_handler.setFormatter(_log_formatter)

_daily_handler = TimedRotatingFileHandler(
    LOG_DIR / "fileapple.log", when='midnight', interval=1, backupCount=30, encoding='utf-8'
)
_daily_handler.setFormatter(_log_formatter)

_main_log_handler = logging.FileHandler(LOG_FILE, encoding='utf-8')
_main_log_handler.setFormatter(_log_formatter)

# 错误日志（单独文件，方便排查崩溃原因）
_error_handler = TimedRotatingFileHandler(
    LOG_ERROR_FILE, when='midnight', interval=1, backupCount=30, encoding='utf-8'
)
_error_handler.setFormatter(_log_formatter)
_error_handler.setLevel(logging.WARNING)

logging.basicConfig(
    level=logging.INFO,
    handlers=[_stdout_handler, _daily_handler, _main_log_handler, _error_handler]
)

logger = logging.getLogger("fileapple")
logger.info("=" * 60)
logger.info("FileApple 8866 服务启动 — 日志系统初始化完成")
logger.info("日志文件: %s (主日志), %s (错误日志)", LOG_FILE, LOG_ERROR_FILE)
logger.info("按日轮转日志: %s/fileapple.log", LOG_DIR)

# ========== 配置 ==========
BASE_DIR = PathLib("/root/.openclaw/workspace/learning")
UPLOADS_DIR = BASE_DIR / "uploads"
DOWNLOADS_DIR = BASE_DIR / "downloads"
CHUNKS_DIR = BASE_DIR / "chunks"
TRANSCRIPTS_DIR = BASE_DIR / "transcripts"
CHECKPOINTS_DIR = BASE_DIR / "checkpoints"
DB_FILE = BASE_DIR / "learning.db"

# 允许访问的目录
ALLOWED_DIRS = [UPLOADS_DIR, DOWNLOADS_DIR]

CHUNK_SIZE = 5 * 1024 * 1024  # 5MB
API_PORT = 8866

# 确保目录存在
for d in [UPLOADS_DIR, CHUNKS_DIR, TRANSCRIPTS_DIR, CHECKPOINTS_DIR]:
    d.mkdir(parents=True, exist_ok=True)

# ========== 数据库 ==========
import sqlite3

def init_db():
    """初始化数据库"""
    logger.info("[DB] 初始化数据库: %s", DB_FILE)
    try:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
    except Exception as e:
        logger.critical("[DB] 数据库连接失败! error=%s", e, exc_info=True)
        raise

    # 上传任务表
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS upload_tasks (
            task_id TEXT PRIMARY KEY,
            file_name TEXT NOT NULL,
            file_path TEXT,
            file_size INTEGER,
            total_chunks INTEGER,
            uploaded_chunks INTEGER DEFAULT 0,
            file_hash TEXT,
            status TEXT DEFAULT 'pending',
            created_at TEXT,
            completed_at TEXT
        )
    """)
    
    # 分片记录表
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS chunks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            task_id TEXT,
            chunk_index INTEGER,
            chunk_hash TEXT,
            size INTEGER,
            FOREIGN KEY (task_id) REFERENCES upload_tasks
        )
    """)
    
    # 转写任务表
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS transcribe_tasks (
            task_id TEXT PRIMARY KEY,
            source_file TEXT,
            output_text TEXT,
            output_json TEXT,
            output_srt TEXT,
            status TEXT DEFAULT 'pending',
            language TEXT DEFAULT 'zh',
            model_size TEXT DEFAULT 'small',
            created_at TEXT,
            completed_at TEXT
        )
    """)
    
    # 文件夹上传表
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS folder_uploads (
            folder_id TEXT PRIMARY KEY,
            folder_name TEXT,
            total_files INTEGER,
            uploaded_files INTEGER DEFAULT 0,
            total_size INTEGER,
            uploaded_size INTEGER DEFAULT 0,
            status TEXT DEFAULT 'pending',
            created_at TEXT
        )
    """)
    
    # 分享链接表
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS share_links (
            share_id TEXT PRIMARY KEY,
            file_path TEXT NOT NULL,
            file_name TEXT NOT NULL,
            password TEXT,
            expires_at TEXT,
            view_count INTEGER DEFAULT 0,
            max_views INTEGER,
            created_at TEXT
        )
    """)

    conn.commit()
    conn.close()
    logger.info("[DB] 数据库初始化完成 — 5张表就绪")

# ========== 工具函数 ==========
def calc_hash(data: bytes) -> str:
    return hashlib.md5(data).hexdigest()

def get_task_checkpoint(task_id: str) -> Optional[Dict]:
    """获取断点信息"""
    checkpoint_file = CHECKPOINTS_DIR / f"{task_id}.json"
    if checkpoint_file.exists():
        with open(checkpoint_file) as f:
            return json.load(f)
    return None

def save_task_checkpoint(task_id: str, data: Dict):
    """保存断点"""
    checkpoint_file = CHECKPOINTS_DIR / f"{task_id}.json"
    with open(checkpoint_file, 'w') as f:
        json.dump(data, f, indent=2)

def clear_task_checkpoint(task_id: str):
    """清除断点"""
    checkpoint_file = CHECKPOINTS_DIR / f"{task_id}.json"
    if checkpoint_file.exists():
        checkpoint_file.unlink()

# ========== FastAPI 应用 ==========
app = FastAPI(title="学习目录 API", version="1.0.0")

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 请求日志中间件
@app.middleware("http")
async def log_requests(request: Request, call_next):
    """记录所有 HTTP 请求"""
    start_time = datetime.now()
    request_id = str(uuid.uuid4())[:8]

    logger.info(f"[{request_id}] {request.method} {request.url.path}")

    try:
        response = await call_next(request)
        duration = (datetime.now() - start_time).total_seconds()
        logger.info(f"[{request_id}] {request.method} {request.url.path} -> {response.status_code} ({duration:.3f}s)")
        response.headers["X-Request-ID"] = request_id
        return response
    except Exception as e:
        duration = (datetime.now() - start_time).total_seconds()
        logger.error(f"[{request_id}] {request.method} {request.url.path} -> ERROR: {e}")
        logger.error(f"[{request_id}] Traceback: {traceback.format_exc()}")
        raise

# WebSocket 连接管理
class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []
    
    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)
    
    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
    
    async def broadcast(self, message: dict):
        for connection in self.active_connections:
            await connection.send_json(message)

manager = ConnectionManager()

# ========== 路由 ==========

# --- 首页 ---
@app.get("/")
async def root():
    return RedirectResponse(url="/index.html")

# --- 前端日志接收 ---
@app.post("/api/client/log")
async def receive_client_log(request: Request):
    """接收前端日志并写入后端日志文件"""
    try:
        data = await request.json()
        level = data.get('level', 'INFO')
        message = data.get('message', '')
        timestamp = data.get('timestamp', datetime.now().isoformat())
        log_data = data.get('data', {})
        user_agent = data.get('userAgent', '')[:50]

        log_msg = f"[CLIENT:{level}] {timestamp} [{user_agent}] {message}"
        if log_data:
            log_msg += f" | {json.dumps(log_data, ensure_ascii=False)}"

        if level == 'error':
            logger.error(log_msg)
        elif level == 'warning':
            logger.warning(log_msg)
        else:
            logger.info(log_msg)

        return {"status": "ok"}
    except Exception as e:
        logger.error(f"[CLIENT:LOG] 接收日志失败: {e}")
        return {"status": "error"}

# --- 上传初始化 ---
@app.post("/api/upload/init")
async def upload_init(file_name: str = Form(...), file_size: int = Form(...)):
    """初始化上传任务"""
    task_id = str(uuid.uuid4())[:16]
    total_chunks = (file_size + CHUNK_SIZE - 1) // CHUNK_SIZE
    
    logger.info("[UPLOAD] 初始化: name=%s size=%s(%s) chunks=%s task_id=%s",
                file_name, file_size, f"{file_size/1024/1024:.1f}MB", total_chunks, task_id)

    # 保存到数据库
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO upload_tasks (task_id, file_name, file_size, total_chunks, status, created_at)
        VALUES (?, ?, ?, ?, 'uploading', ?)
    """, (task_id, file_name, file_size, total_chunks, datetime.now().isoformat()))
    conn.commit()
    conn.close()
    
    # 检查断点
    checkpoint = get_task_checkpoint(task_id)
    uploaded_chunks = checkpoint.get('uploaded_chunks', []) if checkpoint else []
    
    # 保存 file_name 到断点（merge 时需要）
    checkpoint_data = {'task_id': task_id, 'file_name': file_name, 'uploaded_chunks': uploaded_chunks}
    save_task_checkpoint(task_id, checkpoint_data)
    
    return {
        "task_id": task_id,
        "total_chunks": total_chunks,
        "chunk_size": CHUNK_SIZE,
        "uploaded_chunks": uploaded_chunks
    }

# --- 上传分片 ---
@app.post("/api/upload/chunk")
async def upload_chunk(task_id: str = Form(...), chunk_index: int = Form(...), chunk: UploadFile = File(...)):
    """上传分片"""
    # 读取分片数据
    chunk_data = await chunk.read()
    chunk_hash = calc_hash(chunk_data)
    
    logger.debug("[UPLOAD] 分片: task=%s chunk=%s size=%s hash=%s", task_id, chunk_index, len(chunk_data), chunk_hash[:8])

    # 保存分片
    chunk_file = CHUNKS_DIR / f"{task_id}_{chunk_index:04d}.chunk"
    async with aiofiles.open(chunk_file, 'wb') as f:
        await f.write(chunk_data)
    
    # 更新断点
    checkpoint = get_task_checkpoint(task_id) or {'task_id': task_id, 'uploaded_chunks': []}
    if chunk_index not in checkpoint['uploaded_chunks']:
        checkpoint['uploaded_chunks'].append(chunk_index)
        checkpoint['uploaded_chunks'].sort()
    checkpoint['chunk_hashes'] = checkpoint.get('chunk_hashes', {})
    checkpoint['chunk_hashes'][str(chunk_index)] = chunk_hash
    save_task_checkpoint(task_id, checkpoint)
    
    # 更新数据库
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("""
        INSERT OR REPLACE INTO chunks (task_id, chunk_index, chunk_hash, size)
        VALUES (?, ?, ?, ?)
    """, (task_id, chunk_index, chunk_hash, len(chunk_data)))
    cursor.execute("""
        UPDATE upload_tasks SET uploaded_chunks = ? WHERE task_id = ?
    """, (len(checkpoint['uploaded_chunks']), task_id))
    conn.commit()
    conn.close()
    
    # 广播进度
    total_chunks = len(checkpoint['uploaded_chunks']) + (len(checkpoint.get('remaining', [])) if checkpoint.get('remaining') else 0)
    await manager.broadcast({
        "type": "upload_progress",
        "task_id": task_id,
        "chunk": chunk_index,
        "uploaded": len(checkpoint['uploaded_chunks']),
        "total": total_chunks,
        "progress": len(checkpoint['uploaded_chunks']) / total_chunks * 100 if total_chunks else 0
    })
    
    return {
        "chunk": chunk_index,
        "hash": chunk_hash,
        "uploaded": len(checkpoint['uploaded_chunks'])
    }

# --- 合并文件 ---
@app.post("/api/upload/merge")
async def merge_file(task_id: str = Form(...)):
    """合并分片"""
    logger.info("[UPLOAD] 开始合并: task_id=%s", task_id)
    checkpoint = get_task_checkpoint(task_id)
    if not checkpoint:
        logger.warning("[UPLOAD] 合并失败: 任务不存在 task_id=%s", task_id)
        raise HTTPException(status_code=404, detail="任务不存在")
    
    file_name = checkpoint.get('file_name', 'unknown')
    output_path = UPLOADS_DIR / file_name
    
    # 合并（用 uploaded_chunks 列表而非 total_chunks，后者可能未保存在 checkpoint）
    uploaded_chunks = sorted(checkpoint.get('uploaded_chunks', []))
    logger.info("[UPLOAD] 合并参数: file=%s chunks=%s output=%s", file_name, uploaded_chunks, output_path)

    merged_size = 0
    with open(output_path, 'wb') as out:
        for i in uploaded_chunks:
            chunk_file = CHUNKS_DIR / f"{task_id}_{i:04d}.chunk"
            if chunk_file.exists():
                with open(chunk_file, 'rb') as f:
                    data = f.read()
                    out.write(data)
                    merged_size += len(data)
                chunk_file.unlink()  # 删除分片
            else:
                logger.warning("[UPLOAD] 合并时分片丢失: task=%s chunk=%s", task_id, i)
    
    logger.info("[UPLOAD] 合并完成: file=%s size=%s", file_name, f"{merged_size/1024/1024:.1f}MB")

    # 更新数据库
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("""
        UPDATE upload_tasks SET status = 'completed', file_path = ?, completed_at = ?
        WHERE task_id = ?
    """, (str(output_path), datetime.now().isoformat(), task_id))
    conn.commit()
    conn.close()
    
    # 清除断点
    clear_task_checkpoint(task_id)
    
    # 广播完成
    await manager.broadcast({
        "type": "upload_complete",
        "task_id": task_id,
        "path": str(output_path)
    })
    
    return {"path": str(output_path), "size": output_path.stat().st_size}

# --- 上传状态 ---
@app.get("/api/upload/status/{task_id}")
async def upload_status(task_id: str):
    """获取上传状态"""
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM upload_tasks WHERE task_id = ?", (task_id,))
    row = cursor.fetchone()
    conn.close()
    
    if not row:
        raise HTTPException(status_code=404, detail="任务不存在")
    
    return dict(row)

# --- 列出上传任务 ---
@app.get("/api/uploads")
async def list_uploads():
    """列出所有上传任务"""
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM upload_tasks ORDER BY created_at DESC")
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]

# --- 删除上传任务 ---
@app.delete("/api/upload/{task_id}")
async def delete_upload(task_id: str):
    """删除上传任务"""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    
    # 获取文件路径
    cursor.execute("SELECT file_path FROM upload_tasks WHERE task_id = ?", (task_id,))
    row = cursor.fetchone()
    
    if row and row[0]:
        file_path = PathLib(row[0])
        if file_path.exists():
            file_path.unlink()
    
    # 删除分片
    for chunk_file in CHUNKS_DIR.glob(f"{task_id}_*.chunk"):
        chunk_file.unlink()
    
    # 删除记录
    cursor.execute("DELETE FROM chunks WHERE task_id = ?", (task_id,))
    cursor.execute("DELETE FROM upload_tasks WHERE task_id = ?", (task_id,))
    conn.commit()
    conn.close()
    
    clear_task_checkpoint(task_id)
    
    return {"success": True}

# ========== 文件夹上传 ==========

# --- 初始化文件夹上传 ---
@app.post("/api/folder/init")
async def folder_init(folder_name: str = Form(...), total_files: int = Form(...), total_size: int = Form(...)):
    """初始化文件夹上传"""
    folder_id = str(uuid.uuid4())[:16]
    
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO folder_uploads (folder_id, folder_name, total_files, total_size, created_at)
        VALUES (?, ?, ?, ?, ?)
    """, (folder_id, folder_name, total_files, total_size, datetime.now().isoformat()))
    conn.commit()
    conn.close()
    
    return {"folder_id": folder_id}

# --- 更新文件夹上传进度 ---
@app.post("/api/folder/progress")
async def folder_progress(folder_id: str = Form(...), uploaded_files: int = Form(...), uploaded_size: int = Form(...)):
    """更新文件夹上传进度"""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("""
        UPDATE folder_uploads SET uploaded_files = ?, uploaded_size = ?
        WHERE folder_id = ?
    """, (uploaded_files, uploaded_size, folder_id))
    conn.commit()
    conn.close()
    
    # 获取总文件数
    conn2 = sqlite3.connect(DB_FILE)
    conn2.row_factory = sqlite3.Row
    cursor2 = conn2.cursor()
    cursor2.execute("SELECT total_files, total_size FROM folder_uploads WHERE folder_id = ?", (folder_id,))
    row = cursor2.fetchone()
    total_files = row['total_files'] if row else 0
    total_size = row['total_size'] if row else 0
    conn2.close()

    await manager.broadcast({
        "type": "folder_progress",
        "folder_id": folder_id,
        "total_files": total_files,
        "total_size": total_size,
        "uploaded_files": uploaded_files,
        "uploaded_size": uploaded_size
    })
    
    return {"success": True}

# --- 列出文件夹上传 ---
@app.get("/api/folders")
async def list_folders():
    """列出所有文件夹上传"""
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM folder_uploads ORDER BY created_at DESC")
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]

# ========== 音频转写 ==========

# --- 转写文件上传 ---
@app.post("/api/transcribe/upload")
async def transcribe_upload(file: UploadFile = File(...)):
    """上传音频文件用于转写"""
    import hashlib
    import time

    # 创建转写目录
    transcribe_dir = BASE_DIR / "transcripts" / "upload"
    transcribe_dir.mkdir(parents=True, exist_ok=True)

    # 生成唯一文件名
    ext = PathLib(file.filename).suffix if file.filename else ".tmp"
    timestamp = int(time.time())
    hash_name = hashlib.md5(f"{file.filename}{timestamp}".encode()).hexdigest()[:12]
    filename = f"{hash_name}{ext}"
    filepath = transcribe_dir / filename

    # 保存文件
    content = await file.read()
    with open(filepath, 'wb') as f:
        f.write(content)

    return {
        "path": str(filepath),
        "filename": filename,
        "size": len(content)
    }

# --- 转写初始化 ---
@app.post("/api/transcribe/init")
async def transcribe_init(source_file: str = Form(...), language: str = Form("zh"), model_size: str = Form("small")):
    """初始化转写任务"""
    # Auto-migrate: add columns if missing (BEFORE insert)
    try:
        conn_m = sqlite3.connect(DB_FILE)
        c_m = conn_m.cursor()
        cols = [r[1] for r in c_m.execute("PRAGMA table_info(transcribe_tasks)").fetchall()]
        if 'model_size' not in cols:
            c_m.execute("ALTER TABLE transcribe_tasks ADD COLUMN model_size TEXT DEFAULT 'small'")
        if 'output_srt' not in cols:
            c_m.execute("ALTER TABLE transcribe_tasks ADD COLUMN output_srt TEXT")
        conn_m.commit()
        conn_m.close()
    except:
        pass
    
    task_id = str(uuid.uuid4())[:16]
    
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO transcribe_tasks (task_id, source_file, language, model_size, created_at)
        VALUES (?, ?, ?, ?, ?)
    """, (task_id, source_file, language, model_size, datetime.now().isoformat()))
    conn.commit()
    conn.close()
    
    return {"task_id": task_id}

# --- 执行转写 ---
@app.post("/api/transcribe/execute/{task_id}")
async def execute_transcribe(task_id: str):
    """执行转写（异步）"""
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM transcribe_tasks WHERE task_id = ?", (task_id,))
    row = cursor.fetchone()
    conn.close()
    
    if not row:
        raise HTTPException(status_code=404, detail="任务不存在")
    
    # 异步执行转写
    asyncio.create_task(do_transcribe(task_id, dict(row)))
    
    return {"status": "processing"}

async def do_transcribe(task_id: str, task: dict):
    """执行转写 — faster-whisper (CPU int8, 支持音频+视频)"""
    logger.info("[TRANSCRIBE] 开始转写: task_id=%s source=%s model=%s", 
                task_id, task.get('source_file', 'unknown'), task.get('model_size', 'small'))
    try:
        import tempfile
        import subprocess
        
        # HuggingFace 镜像（国内必需）
        if "HF_ENDPOINT" not in os.environ:
            os.environ["HF_ENDPOINT"] = "https://hf-mirror.com"
        
        # 更新状态
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        cursor.execute("UPDATE transcribe_tasks SET status = 'processing' WHERE task_id = ?", (task_id,))
        conn.commit()
        conn.close()
        
        await manager.broadcast({"type": "transcribe_start", "task_id": task_id})
        
        source_file = task['source_file']
        ext = PathLib(source_file).suffix.lower()
        
        # 视频文件需要先提取音频
        VIDEO_EXTS = {'.mp4', '.avi', '.mov', '.mkv', '.flv', '.wmv'}
        tmp_audio = None
        audio_path = source_file
        
        if ext in VIDEO_EXTS:
            logger.info("[TRANSCRIBE] 检测到视频文件，提取音频轨道...")
            tmp_audio = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
            audio_path = tmp_audio.name
            subprocess.run([
                "ffmpeg", "-y", "-i", source_file,
                "-vn", "-acodec", "pcm_s16le", "-ar", "16000", "-ac", "1",
                audio_path
            ], capture_output=True, check=True)
            logger.info("[TRANSCRIBE] 音频提取完成")
        
        # 加载 faster-whisper 模型
        model_size = task.get('model_size', 'small')
        model_start = datetime.now()
        logger.info("[TRANSCRIBE] 加载 faster-whisper %s 模型...", model_size)
        
        from faster_whisper import WhisperModel
        model = WhisperModel(model_size, device="cpu", compute_type="int8")
        model_time = (datetime.now() - model_start).total_seconds()
        logger.info("[TRANSCRIBE] 模型加载完成 (%.1fs)", model_time)
        
        # 转写
        transcribe_start = datetime.now()
        language = task.get('language', 'zh')
        if language == 'auto':
            language = None  # faster-whisper auto-detect
        
        segments, info = model.transcribe(audio_path, beam_size=5, language=language)
        
        lines = []
        srt_lines = []
        seg_idx = 1
        for seg in segments:
            ts = f"[{_fmt_time(seg.start)} -> {_fmt_time(seg.end)}]"
            lines.append(f"{ts} {seg.text.strip()}")
            
            # SRT 格式
            srt_lines.append(str(seg_idx))
            srt_lines.append(f"{_srt_time(seg.start)} --> {_srt_time(seg.end)}")
            srt_lines.append(seg.text.strip())
            srt_lines.append("")
            seg_idx += 1
        
        transcribe_time = (datetime.now() - transcribe_start).total_seconds()
        text = "\n".join(lines)
        srt = "\n".join(srt_lines)
        
        logger.info("[TRANSCRIBE] 转写完成: %d segments, %d chars, language=%s, duration=%.1fs", 
                    seg_idx-1, len(text), info.language, transcribe_time)
        
        # 清理临时音频
        if tmp_audio and os.path.exists(audio_path):
            os.unlink(audio_path)
        
        # 保存结果
        source_path = PathLib(task['source_file'])
        stem = source_path.stem
        
        txt_path = TRANSCRIPTS_DIR / f"{stem}.txt"
        json_path = TRANSCRIPTS_DIR / f"{stem}.json"
        srt_path = TRANSCRIPTS_DIR / f"{stem}.srt"
        
        with open(txt_path, 'w', encoding='utf-8') as f:
            f.write(text)
        
        with open(json_path, 'w', encoding='utf-8') as f:
            json.dump({
                "text": text,
                "language": info.language,
                "language_probability": info.language_probability,
                "duration": info.duration,
                "model_size": model_size,
                "segments": [{"start": s.start, "end": s.end, "text": s.text.strip()} 
                             for s in []]  # segments already consumed
            }, f, ensure_ascii=False, indent=2)
        
        with open(srt_path, 'w', encoding='utf-8') as f:
            f.write(srt)
        
        # 更新数据库
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE transcribe_tasks 
            SET status = 'completed', output_text = ?, output_json = ?, output_srt = ?, completed_at = ?
            WHERE task_id = ?
        """, (str(txt_path), str(json_path), str(srt_path), datetime.now().isoformat(), task_id))
        conn.commit()
        conn.close()
        
        await manager.broadcast({
            "type": "transcribe_complete",
            "task_id": task_id,
            "text_path": str(txt_path),
            "srt_path": str(srt_path)
        })
        
    except Exception as e:
        logger.error("[TRANSCRIBE] 转写失败: task_id=%s error=%s", task_id, e, exc_info=True)
        # 清理临时文件
        if tmp_audio and os.path.exists(audio_path):
            try: os.unlink(audio_path)
            except: pass
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        cursor.execute("UPDATE transcribe_tasks SET status = 'error' WHERE task_id = ?", (task_id,))
        conn.commit()
        conn.close()
        
        await manager.broadcast({
            "type": "transcribe_error",
            "task_id": task_id,
            "error": str(e)
        })

# --- 转写状态 ---
@app.get("/api/transcribe/status/{task_id}")
async def transcribe_status(task_id: str):
    """获取转写状态"""
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM transcribe_tasks WHERE task_id = ?", (task_id,))
    row = cursor.fetchone()
    conn.close()
    
    if not row:
        raise HTTPException(status_code=404, detail="任务不存在")
    
    return dict(row)

# --- 列出转写任务 ---
@app.get("/api/transcribes")
async def list_transcribes():
    """列出所有转写任务"""
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM transcribe_tasks ORDER BY created_at DESC")
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]

def _srt_time(seconds: float) -> str:
    """SRT 时间格式 HH:MM:SS,mmm"""
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    ms = int((seconds - int(seconds)) * 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"

# ========== 总状态 ==========

@app.get("/api/status")
async def status():
    """获取总状态"""
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    cursor.execute("SELECT COUNT(*) as count FROM upload_tasks WHERE status = 'completed'")
    completed_uploads = cursor.fetchone()['count']
    
    cursor.execute("SELECT COUNT(*) as count FROM upload_tasks WHERE status = 'uploading'")
    active_uploads = cursor.fetchone()['count']
    
    cursor.execute("SELECT COUNT(*) as count FROM transcribe_tasks WHERE status = 'completed'")
    completed_transcribes = cursor.fetchone()['count']
    
    cursor.execute("SELECT SUM(file_size) as total FROM upload_tasks WHERE status = 'completed'")
    total_size = cursor.fetchone()['total'] or 0
    
    conn.close()
    
    return {
        "completed_uploads": completed_uploads,
        "active_uploads": active_uploads,
        "completed_transcribes": completed_transcribes,
        "total_size": total_size,
        "ws_connections": len(manager.active_connections)
    }

# ========== WebSocket ==========

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        # 发送欢迎消息
        await websocket.send_json({"type": "connected", "message": "已连接"})
        
        # 保活 ping
        while True:
            try:
                # 每 25 秒发送 ping
                await asyncio.wait_for(websocket.send_json({"type": "ping"}), timeout=25)
                
                # 等待客户端响应（带超时）
                try:
                    msg = await asyncio.wait_for(websocket.receive_text(), timeout=30)
                    # 收到 pong 或心跳响应
                    if msg == "pong" or msg == "heartbeat":
                        pass
                except asyncio.TimeoutError:
                    # 超时后继续，下次循环会发送 ping
                    pass
                    
            except asyncio.CancelledError:
                break
            except Exception:
                break
                
    except WebSocketDisconnect:
        pass
    except Exception:
        pass
    finally:
        manager.disconnect(websocket)

# ========== 文件管理 ==========

# --- 浏览文件列表 ---
@app.get("/api/files")
async def list_files(
    path: str = Query("", description="子目录路径"),
    source: str = Query("uploads", description="来源: uploads/downloads"),
    sort_by: str = Query("name", description="排序字段: name/size/time"),
    order: str = Query("asc", description="排序方向: asc/desc"),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200)
):
    """浏览文件列表，支持分页和排序"""
    base_dir = DOWNLOADS_DIR if source == "downloads" else UPLOADS_DIR
    target_dir = base_dir / path if path else base_dir
    if not target_dir.exists():
        raise HTTPException(status_code=404, detail="目录不存在")
    if not any(str(target_dir.resolve()).startswith(str(d.resolve())) for d in ALLOWED_DIRS):
        raise HTTPException(status_code=403, detail="禁止访问")
    # 如果路径指向文件而非目录，返回文件信息而非报错
    if target_dir.is_file():
        stat = target_dir.stat()
        return {
            "items": [{
                "name": target_dir.name,
                "path": str(target_dir.relative_to(base_dir)),
                "is_file": True,
                "is_dir": False,
                "size": stat.st_size,
                "modified": datetime.fromtimestamp(stat.st_mtime).isoformat(),
                "source": source
            }],
            "total": 1, "page": 1, "page_size": 1, "total_pages": 1,
            "is_file_response": True
        }
    items = []
    for item in target_dir.iterdir():
        stat = item.stat()
        items.append({
            "name": item.name,
            "path": str(item.relative_to(base_dir)),
            "is_file": item.is_file(),
            "is_dir": item.is_dir(),
            "size": stat.st_size,
            "modified": datetime.fromtimestamp(stat.st_mtime).isoformat(),
            "source": source
        })
    reverse = order == "desc"
    if sort_by == "size":
        items.sort(key=lambda x: x["size"], reverse=reverse)
    elif sort_by == "time":
        items.sort(key=lambda x: x["modified"], reverse=reverse)
    else:
        items.sort(key=lambda x: x["name"].lower(), reverse=reverse)
    total = len(items)
    start = (page - 1) * page_size
    end = start + page_size
    paginated = items[start:end]
    return {
        "items": paginated, "total": total, "page": page,
        "page_size": page_size, "total_pages": (total + page_size - 1) // page_size
    }

# --- 搜索文件 ---
@app.get("/api/files/search")
async def search_files(
    q: str = Query(..., min_length=1),
    source: str = Query("all", description="搜索范围: uploads/downloads/all"),
    type: str = Query(None)
):
    """搜索文件 — 支持 uploads/downloads/all"""
    results = []
    q_lower = q.lower()
    search_dirs = []
    if source == "downloads":
        search_dirs = [(DOWNLOADS_DIR, "downloads")]
    elif source == "uploads":
        search_dirs = [(UPLOADS_DIR, "uploads")]
    else:
        search_dirs = [(UPLOADS_DIR, "uploads"), (DOWNLOADS_DIR, "downloads")]
    for base, src in search_dirs:
        for item in base.rglob("*"):
            if q_lower in item.name.lower():
                if type == "file" and not item.is_file(): continue
                if type == "dir" and not item.is_dir(): continue
                stat = item.stat()
                results.append({
                    "name": item.name,
                    "path": str(item.relative_to(base)),
                    "is_file": item.is_file(),
                    "size": stat.st_size if item.is_file() else 0,
                    "modified": datetime.fromtimestamp(stat.st_mtime).isoformat(),
                    "source": src
                })
    results.sort(key=lambda x: x["name"].lower())
    return {"results": results, "count": len(results)}

def get_mime_type(ext: str) -> str:
    mime_map = {
        ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png",
        ".gif": "image/gif", ".webp": "image/webp", ".bmp": "image/bmp",
        ".pdf": "application/pdf",
        ".mp4": "video/mp4", ".avi": "video/x-msvideo", ".mov": "video/quicktime",
        ".mp3": "audio/mpeg", ".wav": "audio/wav", ".flac": "audio/flac",
        ".txt": "text/plain", ".md": "text/markdown", ".json": "application/json",
        ".html": "text/html", ".css": "text/css", ".js": "application/javascript",
        ".zip": "application/zip", ".tar": "application/x-tar", ".gz": "application/gzip",
        ".doc": "application/msword", ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        ".xls": "application/vnd.ms-excel", ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        ".ppt": "application/vnd.ms-powerpoint", ".pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    }
    return mime_map.get(ext.lower(), "application/octet-stream")

async def stream_file(path, chunk_size=1024*1024):
    with open(path, 'rb') as f:
        while True:
            chunk = f.read(chunk_size)
            if not chunk: break
            yield chunk

# --- 获取文件详情 ---
@app.get("/api/files/info")
async def file_info(path: str = Query(...), source: str = Query("uploads")):
    base_dir = DOWNLOADS_DIR if source == "downloads" else UPLOADS_DIR
    target = base_dir / path
    if not target.exists():
        raise HTTPException(status_code=404, detail="文件不存在")
    if not any(str(target.resolve()).startswith(str(d.resolve())) for d in ALLOWED_DIRS):
        raise HTTPException(status_code=403, detail="禁止访问")
    stat = target.stat()
    info = {
        "name": target.name, "path": path,
        "is_file": target.is_file(), "is_dir": target.is_dir(),
        "size": stat.st_size,
        "modified": datetime.fromtimestamp(stat.st_mtime).isoformat(),
        "created": datetime.fromtimestamp(stat.st_ctime).isoformat()
    }
    if target.is_file():
        info["extension"] = target.suffix.lower()
        info["mime_type"] = get_mime_type(target.suffix)
    return info

# --- 预览文件 ---
@app.get("/s/{share_id}")
async def access_share(share_id: str, password: str = Query(None)):
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM share_links WHERE share_id = ?", (share_id,))
    row = cursor.fetchone()
    conn.close()
    if not row:
        raise HTTPException(status_code=404, detail="分享不存在或已过期")
    row = dict(row)
    if row["expires_at"] and datetime.fromisoformat(row["expires_at"]) < datetime.now():
        raise HTTPException(status_code=410, detail="分享已过期")
    if row["max_views"] and row["view_count"] >= row["max_views"]:
        raise HTTPException(status_code=410, detail="分享已达到最大查看次数")
    if row["password"] and row["password"] != password:
        return JSONResponse(status_code=401, content={"error": "密码错误", "password_required": True})
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("UPDATE share_links SET view_count = view_count + 1 WHERE share_id = ?", (share_id,))
    conn.commit()
    conn.close()
    target = UPLOADS_DIR / row["file_path"]
    if not target.exists():
        raise HTTPException(status_code=404, detail="文件已被删除")
    try:
        return FileResponse(path=str(target), filename=row["file_name"], media_type="application/octet-stream")
    except Exception as e:
        import traceback
        return JSONResponse(status_code=500, content={"error": str(e), "trace": traceback.format_exc()})

@app.get("/api/files/preview/{full_path:path}")
async def preview_file(full_path: str, source: str = Query("uploads")):
    base_dir = DOWNLOADS_DIR if source == "downloads" else UPLOADS_DIR
    target = base_dir / full_path
    if not target.exists() or not target.is_file():
        raise HTTPException(status_code=404, detail="文件不存在")
    if not any(str(target.resolve()).startswith(str(d.resolve())) for d in ALLOWED_DIRS):
        raise HTTPException(status_code=403, detail="禁止访问")
    ext = target.suffix.lower()
    mime_type = get_mime_type(ext)
    if ext in [".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp"]:
        return FileResponse(path=str(target), media_type=mime_type, filename=target.name)
    if ext in [".mp4", ".avi", ".mov", ".mp3", ".wav", ".flac"]:
        return StreamingResponse(stream_file(target), media_type=mime_type, headers={"Accept-Ranges": "bytes"})
    text_exts = [".txt", ".md", ".json", ".html", ".css", ".js", ".py", ".java", ".c", ".cpp", ".h", ".sh", ".xml", ".yaml", ".yml", ".toml", ".ini", ".cfg", ".log"]
    if ext in text_exts and target.stat().st_size < 1024*1024:
        with open(target, 'r', encoding='utf-8', errors='ignore') as f:
            return JSONResponse({"content": f.read(), "size": target.stat().st_size})
    return FileResponse(path=str(target), media_type=mime_type, filename=target.name)

# --- 下载文件 ---
@app.get("/api/files/download/{full_path:path}")
async def download_file(full_path: str, source: str = Query("uploads")):
    base_dir = DOWNLOADS_DIR if source == "downloads" else UPLOADS_DIR
    target = base_dir / full_path
    if not target.exists() or not target.is_file():
        raise HTTPException(status_code=404, detail="文件不存在")
    if not any(str(target.resolve()).startswith(str(d.resolve())) for d in ALLOWED_DIRS):
        raise HTTPException(status_code=403, detail="禁止访问")
    return FileResponse(path=str(target), filename=target.name, media_type="application/octet-stream")

# --- 删除文件（仅限uploads） ---
@app.delete("/api/files")
async def delete_file(path: str = Query(...), source: str = Query("uploads")):
    if source != "uploads":
        raise HTTPException(status_code=403, detail="下载目录文件不可删除")
    target = UPLOADS_DIR / path
    if not target.exists():
        raise HTTPException(status_code=404, detail="文件不存在")
    if not str(target.resolve()).startswith(str(UPLOADS_DIR.resolve())):
        raise HTTPException(status_code=403, detail="禁止访问")
    if target.is_file():
        target.unlink()
    else:
        import shutil; shutil.rmtree(target)
    return {"success": True, "path": path}


@app.post("/api/files/folder")
async def create_folder(body: dict):
    """创建文件夹"""
    name = body.get("name", "").strip()
    parent_path = body.get("path", "")

    if not name:
        raise HTTPException(status_code=400, detail="文件夹名称不能为空")

    if "/" in name or "\\" in name:
        raise HTTPException(status_code=400, detail="文件夹名称不能包含斜杠")

    # 处理根路径
    if parent_path in ("", "/"):
        target = UPLOADS_DIR / name
    else:
        target = UPLOADS_DIR / parent_path / name

    if target.exists():
        raise HTTPException(status_code=409, detail="文件夹已存在")

    if not str(target.resolve()).startswith(str(UPLOADS_DIR.resolve())):
        raise HTTPException(status_code=403, detail="禁止访问")

    target.mkdir(parents=True, exist_ok=True)
    result_path = f"{parent_path}/{name}".replace("//", "/").strip("/")
    return {"success": True, "path": result_path}


# ========== 分享功能 ==========

@app.post("/api/share")
async def create_share(
    file_path: str = Form(...),
    source: str = Form("uploads"),
    password: str = Form(None),
    expires_days: int = Form(7, ge=1, le=90),
    max_views: int = Form(None)
):
    share_id = uuid.uuid4().hex[:12]
    expires_at = (datetime.now() + timedelta(days=expires_days)).isoformat()
    base_dir = DOWNLOADS_DIR if source == "downloads" else UPLOADS_DIR
    target = base_dir / file_path
    if not target.exists():
        raise HTTPException(status_code=404, detail="文件不存在")
    if not any(str(target.resolve()).startswith(str(d.resolve())) for d in ALLOWED_DIRS):
        raise HTTPException(status_code=403, detail="禁止访问")
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO share_links (share_id, file_path, file_name, password, expires_at, max_views, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (share_id, file_path, target.name, password, expires_at, max_views, datetime.now().isoformat()))
    conn.commit()
    conn.close()
    return {"share_id": share_id, "url": f"/s/{share_id}", "expires_at": expires_at, "password_required": password is not None}


@app.get("/api/share/{share_id}")
async def share_info(share_id: str):
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("SELECT share_id, file_name, expires_at, view_count, max_views, created_at, password FROM share_links WHERE share_id = ?", (share_id,))
    row = cursor.fetchone()
    conn.close()
    if not row:
        raise HTTPException(status_code=404, detail="分享不存在")
    return {
        "share_id": row["share_id"], "file_name": row["file_name"],
        "expires_at": row["expires_at"], "view_count": row["view_count"],
        "max_views": row["max_views"], "created_at": row["created_at"],
        "password_required": row["password"] is not None
    }

@app.get("/api/shares")
async def list_shares():
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("SELECT share_id, file_name, expires_at, view_count, max_views, created_at, password FROM share_links ORDER BY created_at DESC")
    rows = cursor.fetchall()
    conn.close()
    return [{
        "share_id": r["share_id"], "file_name": r["file_name"],
        "expires_at": r["expires_at"], "view_count": r["view_count"],
        "max_views": r["max_views"], "created_at": r["created_at"],
        "password_required": r["password"] is not None
    } for r in rows]

@app.delete("/api/share/{share_id}")
async def delete_share(share_id: str):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM share_links WHERE share_id = ?", (share_id,))
    conn.commit()
    conn.close()
    return {"success": True}

# ========== 网盘管理 ==========

from cloud_storage import get_cloud_disk_manager, get_sync_manager, CloudDisk

# 附加上传目录列表
ADDITIONAL_UPLOAD_DIRS = []

@app.get("/api/disks")
async def list_disks():
    """列出已配置的网盘"""
    manager = get_cloud_disk_manager()
    disks = []
    for d in manager.list_disks():
        disks.append({
            "id": d.id,
            "name": d.name,
            "type": d.type,
            "enabled": d.enabled,
            "mount_path": d.mount_path,
            "status": d.status,
            "file_count": d.file_count,
            "last_sync": d.last_sync,
        })
    return {"disks": disks}

@app.post("/api/disks")
async def add_disk(
    name: str = Form(...),
    disk_type: str = Form(...),
    host: str = Form(""),
    username: str = Form(""),
    password: str = Form(""),
    mount_path: str = Form("/其他")
):
    """添加网盘"""
    import uuid
    disk_id = str(uuid.uuid4())[:8]
    disk = CloudDisk(
        id=disk_id, name=name, type=disk_type,
        host=host, username=username, password=password,
        mount_path=mount_path,
    )
    manager = get_cloud_disk_manager()
    manager.add_disk(disk)
    return {"id": disk_id, "name": name, "type": disk_type}

@app.delete("/api/disks/{disk_id}")
async def remove_disk(disk_id: str):
    """移除网盘"""
    manager = get_cloud_disk_manager()
    if manager.remove_disk(disk_id):
        return {"success": True}
    raise HTTPException(status_code=404, detail="网盘不存在")

@app.post("/api/disks/{disk_id}/sync")
async def sync_disk(disk_id: str, remote_path: str = Form("/"), local_category: str = Form("其他")):
    """同步网盘到本地"""
    sync_mgr = get_sync_manager()

    # 创建广播函数
    async def broadcast(msg: dict):
        await manager.broadcast(msg)

    result = await sync_mgr.sync_disk(disk_id, remote_path, local_category, broadcast_func=broadcast)
    return result

@app.get("/api/disks/{disk_id}/files")
async def list_disk_files(disk_id: str, path: str = Query("/")):
    """列出网盘文件"""
    manager = get_cloud_disk_manager()
    disk = manager.get_disk(disk_id)
    if not disk:
        raise HTTPException(status_code=404, detail="网盘不存在")
    if disk.type == "alist":
        from cloud_storage import AlistAdapter
        adapter = AlistAdapter(disk)
        if disk.token:
            adapter.disk.token = disk.token
        elif disk.username and disk.password:
            await adapter.login(disk.username, disk.password)
        files = await adapter.list_files(path)
        await adapter.close()
        return {"path": path, "files": files}
    return {"path": path, "files": []}

# ========== 上传目录管理 ==========

@app.get("/api/dirs/uploads")
async def list_upload_dirs():
    """列出所有上传目录"""
    dirs = [{"path": str(UPLOADS_DIR), "name": "主上传目录", "default": True}]
    for d in ADDITIONAL_UPLOAD_DIRS:
        p = PathLib(d)
        if p.exists():
            dirs.append({"path": d, "name": PathLib(d).name, "default": False})
    return {"dirs": dirs}

@app.post("/api/dirs/uploads")
async def add_upload_dir(path: str = Form(...)):
    """添加上传目录"""
    p = PathLib(path)
    if not p.exists():
        p.mkdir(parents=True, exist_ok=True)
    if path not in ADDITIONAL_UPLOAD_DIRS:
        ADDITIONAL_UPLOAD_DIRS.append(path)
    return {"success": True, "path": path}

@app.delete("/api/dirs/uploads")
async def remove_upload_dir(path: str = Query(...)):
    """移除上传目录"""
    if path in ADDITIONAL_UPLOAD_DIRS:
        ADDITIONAL_UPLOAD_DIRS.remove(path)
        return {"success": True}
    raise HTTPException(status_code=403, detail="不能移除默认上传目录")

# ========== 启动 ==========

# ========== 知识导入流水线 ==========

# 添加knowledge模块路径
import sys
sys.path.insert(0, str(PathLib(__file__).parent / "knowledge"))

from knowledge.ingest import scan as ki_scan, process_file as ki_process_file

@app.get("/api/knowledge/scan")
async def knowledge_scan():
    """扫描待导入文件"""
    try:
        files = ki_scan(str(UPLOADS_DIR))
        return {
            "total": len(files),
            "files": [{"name": f["name"], "path": f["path"], "size": f["size"], "priority": f["priority"], "category": f["category"]} for f in files[:50]]
        }
    except Exception as e:
        logger.error(f"知识扫描失败: {e}")
        return {"error": str(e), "trace": traceback.format_exc()}

@app.post("/api/knowledge/import/batch")
async def knowledge_import_batch(
    files: List[str] = Body(...),
    category: str = Body("其他"),
    sync_ragflow: bool = Body(True)
):
    """批量导入文件到知识库"""
    import_id = str(uuid.uuid4())[:16]
    logger.info(f"[{import_id}] 批量导入开始: {len(files)} 个文件, category={category}")

    # 创建导入记录
    from database import get_db
    db = get_db()
    db.create_knowledge_import(import_id, ",".join(files), category, len(files))

    # 异步执行批量导入（包含RAGFlow同步）
    asyncio.create_task(_do_batch_import(import_id, files, category, sync_ragflow))

    return {"import_id": import_id, "total": len(files), "status": "processing"}

@app.post("/api/knowledge/import/{filename}")
async def knowledge_import(filename: str):
    """触发单个文件的知识导入"""
    logger.info(f"知识导入请求: filename={filename}")

    # 排除 batch 路径，避免与批量导入路由冲突
    if filename == "batch":
        logger.warning("收到 batch 请求但使用了单文件接口")
        raise HTTPException(status_code=400, detail="请使用 /api/knowledge/import/batch 进行批量导入")

    # 支持子目录路径 (filename 可能包含路径如 "docs/test.txt")
    filepath = UPLOADS_DIR / filename
    logger.info(f"知识导入路径解析: {filepath}")

    if not filepath.exists():
        logger.warning(f"文件不存在: {filepath}")
        raise HTTPException(status_code=404, detail=f"文件不存在: {filepath}")
    if not filepath.is_file():
        logger.warning(f"不是有效文件: {filepath}")
        raise HTTPException(status_code=400, detail="不是有效文件")

    # 异步执行导入
    logger.info(f"开始异步处理: {filepath}")
    asyncio.create_task(_do_knowledge_import(str(filepath)))

    return {"status": "processing", "file": filename, "path": str(filepath)}

async def _do_knowledge_import(filepath: str):
    """异步执行知识导入"""
    logger.info(f"[_do_knowledge_import] 开始导入: {filepath}")
    try:
        import yaml
        config_path = PathLib(__file__).parent / "knowledge" / "config.yaml"
        with open(config_path) as f:
            cfg = yaml.safe_load(f)

        logger.info(f"[_do_knowledge_import] 处理文件: {filepath}")
        await asyncio.to_thread(ki_process_file, filepath, cfg)
        logger.info(f"[_do_knowledge_import] 处理完成: {filepath}")

        await manager.broadcast({
            "type": "knowledge_import_complete",
            "file": os.path.basename(filepath)
        })
    except Exception as e:
        logger.error(f"[_do_knowledge_import] 处理失败: {filepath}, error={e}")
        await manager.broadcast({
            "type": "knowledge_import_error",
            "file": os.path.basename(filepath),
            "error": str(e)
        })

@app.get("/api/knowledge/status")
async def knowledge_status():
    """查看导入状态"""
    # 使用数据库统计
    from database import get_db
    db = get_db()
    stats = db.get_knowledge_stats()
    return stats

async def _do_batch_import(import_id: str, files: List[str], category: str, sync_ragflow: bool = True):
    """异步执行批量导入"""
    from database import get_db
    db = get_db()

    success = 0
    failed = 0
    ragflow_synced = 0

    # 转换文件路径为完整路径
    full_paths = []
    for f in files:
        if f.startswith('/'):
            full_paths.append(f)  # 已经是绝对路径
        else:
            full_paths.append(str(UPLOADS_DIR / f))  # 相对路径拼接

    # 初始化 RAGFlow 客户端
    rag_client = None
    if sync_ragflow:
        try:
            from ragflow_client import RAGFlowClient, RAGFlowConfig
            rag_client = RAGFlowClient(RAGFlowConfig.from_config_file())
        except Exception as e:
            print(f"RAGFlow 客户端初始化失败: {e}")

    # 分类到知识库映射
    dataset_mapping = {
        "技术运维": "tech-ops",
        "心理学": "psychology",
        "恋爱心理": "relationship",
        "文档": "documents",
        "有声剧": "audio-books",
        "其他": "general"
    }
    dataset_id = dataset_mapping.get(category, "general")

    try:
        import yaml
        config_path = PathLib(__file__).parent / "knowledge" / "config.yaml"
        with open(config_path) as f:
            cfg = yaml.safe_load(f)

        for i, filename in enumerate(files):
            try:
                filepath = UPLOADS_DIR / filename
                if filepath.exists():
                    # 处理文件（提取/转写/摘要/Embedding）
                    await asyncio.to_thread(ki_process_file, str(filepath), cfg)
                    success += 1

                    # 同步到 RAGFlow
                    if rag_client:
                        try:
                            doc_id = await rag_client.upload_document(dataset_id, str(filepath))
                            if doc_id:
                                await rag_client.parse_document(dataset_id, doc_id)
                                ragflow_synced += 1
                                await manager.broadcast({
                                    "type": "ragflow_sync_progress",
                                    "file": filename,
                                    "doc_id": doc_id,
                                    "synced": ragflow_synced
                                })
                        except Exception as rag_err:
                            print(f"RAGFlow 同步失败: {filename} - {rag_err}")
                else:
                    failed += 1

                # 更新进度
                db.update_knowledge_import(import_id, success_count=success, fail_count=failed)
                await manager.broadcast({
                    "type": "knowledge_batch_progress",
                    "import_id": import_id,
                    "current": i + 1,
                    "total": len(files),
                    "success": success,
                    "failed": failed,
                    "ragflow_synced": ragflow_synced
                })
            except Exception as e:
                failed += 1
                db.update_knowledge_import(import_id, success_count=success, fail_count=failed)

        # 完成
        db.complete_knowledge_import(import_id, target_path=str(UPLOADS_DIR / category))
        await manager.broadcast({
            "type": "knowledge_batch_complete",
            "import_id": import_id,
            "success": success,
            "failed": failed,
            "ragflow_synced": ragflow_synced
        })
    except Exception as e:
        db.update_knowledge_import(import_id, status='error', error=str(e))
        await manager.broadcast({
            "type": "knowledge_batch_error",
            "import_id": import_id,
            "error": str(e)
        })
    finally:
        if rag_client:
            await rag_client.close()

@app.get("/api/knowledge/imports")
async def list_knowledge_imports(limit: int = Query(50)):
    """列出知识导入记录"""
    from database import get_db
    db = get_db()
    return {"imports": db.list_knowledge_imports(limit=limit)}

@app.get("/api/knowledge/stats")
async def knowledge_stats():
    """获取知识导入统计"""
    from database import get_db
    db = get_db()
    stats = db.get_knowledge_stats()

    # 扫描待处理文件
    all_files = list(UPLOADS_DIR.rglob("*"))
    pending = len([f for f in all_files if f.is_file()])

    return {**stats, "pending_files": pending}

# ========== 标签管理 ==========

@app.post("/api/files/tags")
async def add_file_tag(path: str = Body(...), tag: str = Body(...)):
    """为文件添加标签"""
    from database import get_db
    db = get_db()
    db.add_file_tag(path, tag)
    return {"success": True, "path": path, "tag": tag}

@app.delete("/api/files/tags")
async def remove_file_tag(path: str = Query(...), tag: str = Query(...)):
    """移除文件标签"""
    from database import get_db
    db = get_db()
    db.remove_file_tag(path, tag)
    return {"success": True}

@app.get("/api/files/tags")
async def get_file_tags(path: str = Query(...)):
    """获取文件标签"""
    from database import get_db
    db = get_db()
    tags = db.get_file_tags(path)
    return {"path": path, "tags": tags}

@app.get("/api/tags")
async def list_all_tags():
    """列出所有标签"""
    from database import get_db
    db = get_db()
    tags = db.get_all_tags()
    return {"tags": tags}

@app.get("/api/tags/{tag}/files")
async def get_files_by_tag(tag: str):
    """按标签查询文件"""
    from database import get_db
    db = get_db()
    files = db.get_files_by_tag(tag)
    return {"tag": tag, "count": len(files), "files": files}

# ========== 批量操作 ==========

@app.post("/api/files/batch-delete")
async def batch_delete_files(paths: List[str] = Body(...)):
    """批量删除文件"""
    deleted = []
    failed = []
    for path in paths:
        try:
            target = UPLOADS_DIR / path
            if target.exists() and str(target.resolve()).startswith(str(UPLOADS_DIR.resolve())):
                if target.is_file():
                    target.unlink()
                else:
                    import shutil
                    shutil.rmtree(target)
                deleted.append(path)
            else:
                failed.append({"path": path, "error": "权限不足或不存在"})
        except Exception as e:
            failed.append({"path": path, "error": str(e)})
    return {"deleted": deleted, "failed": failed, "total": len(paths)}

@app.post("/api/files/batch-move")
async def batch_move_files(
    paths: List[str] = Body(...),
    target_dir: str = Body(...)
):
    """批量移动文件"""
    import shutil
    moved = []
    failed = []
    target_path = UPLOADS_DIR / target_dir
    target_path.mkdir(parents=True, exist_ok=True)

    for path in paths:
        try:
            source = UPLOADS_DIR / path
            dest = target_path / source.name
            if source.exists():
                shutil.move(str(source), str(dest))
                moved.append({"from": path, "to": str(dest.relative_to(UPLOADS_DIR))})
            else:
                failed.append({"path": path, "error": "源文件不存在"})
        except Exception as e:
            failed.append({"path": path, "error": str(e)})
    return {"moved": moved, "failed": failed}

# ========== 存储统计 ==========

@app.get("/api/storage/stats")
async def storage_stats():
    """获取存储统计"""
    from database import get_db
    db = get_db()
    stats = db.get_storage_stats()

    # 计算分类统计
    categories = {}
    for item in UPLOADS_DIR.iterdir():
        if item.is_dir():
            size = sum(f.stat().st_size for f in item.rglob("*") if f.is_file())
            categories[item.name] = {"count": len(list(item.rglob("*.*"))), "size": size}

    return {**stats, "categories": categories}

@app.get("/api/storage/duplicates")
async def find_duplicates():
    """查找重复文件（按大小+名称）"""
    import hashlib
    from collections import defaultdict

    size_name_map = defaultdict(list)

    # 按大小+名称分组
    for f in UPLOADS_DIR.rglob("*"):
        if f.is_file():
            key = f"{f.stat().st_size}_{f.name}"
            size_name_map[key].append(str(f.relative_to(UPLOADS_DIR)))

    # 返回有重复的
    duplicates = []
    for key, paths in size_name_map.items():
        if len(paths) > 1:
            size = int(key.split('_')[0])
            duplicates.append({
                "name": paths[0].split('/')[-1],
                "size": size,
                "count": len(paths),
                "paths": paths
            })

    return {"duplicates": duplicates[:50]}  # 最多返回50组

# ========== 批量操作 ==========

@app.post("/api/files/batch-copy")
async def batch_copy_files(
    paths: List[str] = Body(...),
    target_dir: str = Body(...)
):
    """批量复制文件"""
    import shutil
    copied = []
    failed = []
    target_path = UPLOADS_DIR / target_dir
    target_path.mkdir(parents=True, exist_ok=True)

    for path in paths:
        try:
            source = UPLOADS_DIR / path
            dest = target_path / source.name
            if source.exists():
                shutil.copy2(str(source), str(dest))
                copied.append({"from": path, "to": str(dest.relative_to(UPLOADS_DIR))})
            else:
                failed.append({"path": path, "error": "源文件不存在"})
        except Exception as e:
            failed.append({"path": path, "error": str(e)})
    return {"copied": copied, "failed": failed}

# ========== 云盘同步进度 WebSocket ==========

@app.get("/api/disks/sync/status")
async def sync_status():
    """获取同步任务状态"""
    from database import get_db
    db = get_db()
    tasks = db.list_sync_tasks(status='running')
    return {"running_tasks": tasks}

@app.post("/api/disks/sync/cancel/{task_id}")
async def cancel_sync(task_id: str):
    """取消同步任务"""
    from database import get_db
    db = get_db()
    db.complete_sync_task(task_id, status='cancelled')
    return {"success": True, "task_id": task_id}

# ========== 启动 ==========

# ========== RAGFlow 集成 ==========

# 延迟导入避免循环依赖 + 单例复用连接池
_rag_client_instance = None

def get_rag_client():
    global _rag_client_instance
    if _rag_client_instance is not None:
        return _rag_client_instance
    try:
        from ragflow_client import RAGFlowClient, RAGFlowConfig
        _rag_client_instance = RAGFlowClient(RAGFlowConfig.from_config_file())
        return _rag_client_instance
    except ImportError:
        return None

@app.get("/api/rag/health")
async def rag_health():
    """RAGFlow 健康检查"""
    client = get_rag_client()
    if not client:
        return {"status": "unavailable", "message": "RAGFlow 未配置"}
    healthy = await client.health_check()
    return {"status": "healthy" if healthy else "unhealthy", "version": await client.get_version()}

@app.get("/api/rag/datasets")
async def rag_list_datasets():
    """列出 RAGFlow 知识库"""
    client = get_rag_client()
    if not client:
        raise HTTPException(status_code=503, detail="RAGFlow 未配置")
    datasets = await client.list_datasets()
    return {"datasets": datasets}

@app.post("/api/rag/datasets")
async def rag_create_dataset(name: str = Body(...), description: str = Body(""), language: str = Body("Chinese")):
    """创建知识库"""
    client = get_rag_client()
    if not client:
        raise HTTPException(status_code=503, detail="RAGFlow 未配置")
    dataset_id = await client.create_dataset(name, description, language)
    if dataset_id:
        return {"dataset_id": dataset_id, "name": name}
    raise HTTPException(status_code=500, detail="创建失败")

@app.post("/api/rag/upload")
async def rag_upload_file(
    file: UploadFile = File(...),
    dataset: str = Form("general")
):
    """上传文件到 RAGFlow"""
    client = get_rag_client()
    if not client:
        raise HTTPException(status_code=503, detail="RAGFlow 未配置")

    # 保存临时文件
    import tempfile
    with tempfile.NamedTemporaryFile(delete=False, suffix=PathLib(file.filename).suffix) as tmp:
        content = await file.read()
        tmp.write(content)
        tmp_path = tmp.name

    try:
        # 上传到 RAGFlow
        doc_id = await client.upload_document(dataset, tmp_path)
        if doc_id:
            # 触发解析
            await client.parse_document(dataset, doc_id)
            return {"doc_id": doc_id, "dataset": dataset, "status": "parsing"}
        raise HTTPException(status_code=500, detail="上传失败")
    finally:
        PathLib(tmp_path).unlink(missing_ok=True)

@app.post("/api/rag/search")
async def rag_search(
    query: str = Body(...),
    dataset: str = Body("all"),
    top_k: int = Body(10)
):
    """语义搜索"""
    client = get_rag_client()
    if not client:
        raise HTTPException(status_code=503, detail="RAGFlow 未配置")

    results = await client.search(query, top_k=top_k)
    return {"query": query, "results": results, "count": len(results)}

@app.post("/api/rag/chat")
async def rag_chat(
    question: str = Body(...),
    dataset: str = Body(None)
):
    """RAG 对话"""
    client = get_rag_client()
    if not client:
        raise HTTPException(status_code=503, detail="RAGFlow 未配置")

    result = await client.chat_completion(question, dataset_id=dataset)
    return result

@app.get("/api/rag/status/{dataset_id}/{doc_id}")
async def rag_document_status(dataset_id: str, doc_id: str):
    """获取文档解析状态"""
    client = get_rag_client()
    if not client:
        raise HTTPException(status_code=503, detail="RAGFlow 未配置")

    status = await client.get_document_status(dataset_id, doc_id)
    return status

@app.post("/api/rag/import/{category}")
async def rag_import_category(
    category: str,
    files: List[str] = Body(...)
):
    """批量导入文件到指定分类知识库"""
    client = get_rag_client()
    if not client:
        raise HTTPException(status_code=503, detail="RAGFlow 未配置")

    # 映射分类到知识库
    dataset_mapping = {
        "技术运维": "tech-ops",
        "心理学": "psychology",
        "恋爱心理": "relationship",
        "文档": "documents",
        "有声剧": "audio-books",
        "其他": "general"
    }
    dataset_id = dataset_mapping.get(category, "general")

    results = []
    for file_path in files:
        try:
            result = await client.import_file(file_path, dataset_id, wait_completed=False)
            results.append({"file": file_path, "result": result})
        except Exception as e:
            results.append({"file": file_path, "error": str(e)})

    return {"category": category, "dataset": dataset_id, "results": results}


# ========== 启动 ==========

if __name__ == "__main__":
    logger.info("=" * 60)
    logger.info("FileApple 8866 服务初始化")
    logger.info("BASE_DIR: %s", BASE_DIR)
    logger.info("UPLOADS_DIR: %s", UPLOADS_DIR)
    logger.info("DB_FILE: %s", DB_FILE)
    logger.info("CHUNK_SIZE: %s bytes", CHUNK_SIZE)
    
    try:
        init_db()
        logger.info("[DB] 初始化完成")
    except Exception as e:
        logger.critical("[DB] 初始化失败! error=%s", e, exc_info=True)
        sys.exit(1)

    # 检查上传目录
    if not UPLOADS_DIR.exists():
        logger.warning("上传目录不存在，创建: %s", UPLOADS_DIR)
        UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
    
    # 挂载前端静态文件
    FRONTEND_DIR = PathLib(__file__).parent.parent / "frontend"
    if FRONTEND_DIR.exists():
        app.mount("", StaticFiles(directory=str(FRONTEND_DIR), html=True), name="static")
        logger.info("前端静态目录: %s", FRONTEND_DIR)
    else:
        logger.warning("前端静态目录不存在: %s", FRONTEND_DIR)

    logger.info("服务监听: http://0.0.0.0:%s", API_PORT)
    logger.info("=" * 60)
    print(f"""
╔══════════════════════════════════════════════════╗
║  学习目录 API 服务                               ║
║  分片上传 + 断点续传 + 音频转文字 + 知识导入       ║
║  RAGFlow 集成 + 语义搜索                          ║
╠══════════════════════════════════════════════════╣
║  Web UI:   http://localhost:{API_PORT}            ║
║  HTTP API: http://localhost:{API_PORT}/api        ║
║  WebSocket: ws://localhost:{API_PORT}/ws          ║
║  文档:      http://localhost:{API_PORT}/docs      ║
╠══════════════════════════════════════════════════╣
║  知识导入:                                      ║
║    GET  /api/knowledge/scan     # 扫描待导入文件  ║
║    POST /api/knowledge/import/  # 触发导入       ║
║  RAG 搜索:                                      ║
║    GET  /api/rag/health         # 健康检查       ║
║    GET  /api/rag/datasets      # 知识库列表      ║
║    POST /api/rag/search        # 语义搜索        ║
║    POST /api/rag/chat          # RAG 对话        ║
╚══════════════════════════════════════════════════╝
    """)
    uvicorn.run(app, host="0.0.0.0", port=API_PORT, log_level="info")
