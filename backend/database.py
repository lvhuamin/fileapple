#!/usr/bin/env python3
"""
学习目录数据库模块
SQLite 数据库操作封装
"""

import sqlite3
import json
import os
import logging
from pathlib import Path
from datetime import datetime
from typing import Optional, List, Dict, Any
from contextlib import contextmanager

logger = logging.getLogger("fileapple.database")


class LearningDB:
    """学习目录数据库"""

    def __init__(self, db_path: str):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        logger.info("[DB] 初始化数据库: %s", db_path)
        self.init_tables()
        logger.info("[DB] 核心表初始化完成")
        self.init_cloud_tables()  # 初始化云盘相关表
        logger.info("[DB] 云盘表初始化完成")
    
    @contextmanager
    def get_conn(self):
        """获取数据库连接（上下文管理器）"""
        conn = None
        try:
            conn = sqlite3.connect(self.db_path, timeout=10)
            conn.row_factory = sqlite3.Row
            yield conn
            conn.commit()
        except Exception as e:
            logger.error("[DB] 操作失败: %s", e, exc_info=True)
            if conn:
                try:
                    conn.rollback()
                except Exception:
                    pass
            raise
        finally:
            if conn:
                conn.close()
    
    def init_tables(self):
        """初始化数据库表"""
        with self.get_conn() as conn:
            cursor = conn.cursor()
            
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
                    completed_at TEXT,
                    metadata TEXT
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
                    created_at TEXT,
                    FOREIGN KEY (task_id) REFERENCES upload_tasks(task_id) ON DELETE CASCADE,
                    UNIQUE(task_id, chunk_index)
                )
            """)
            
            # 转写任务表
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS transcribe_tasks (
                    task_id TEXT PRIMARY KEY,
                    source_file TEXT,
                    source_type TEXT,
                    output_text TEXT,
                    output_json TEXT,
                    output_srt TEXT,
                    status TEXT DEFAULT 'pending',
                    language TEXT DEFAULT 'zh',
                    model_size TEXT DEFAULT 'small',
                    duration REAL,
                    error_message TEXT,
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
                    created_at TEXT,
                    completed_at TEXT
                )
            """)

            # 文本提取任务表
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS extract_tasks (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    file_path TEXT NOT NULL,
                    file_name TEXT NOT NULL,
                    file_type TEXT,
                    file_ext TEXT,
                    status TEXT DEFAULT 'pending',
                    text_content TEXT,
                    char_count INTEGER,
                    error_message TEXT,
                    auto_processed INTEGER DEFAULT 0,
                    folder_batch_id INTEGER,
                    sort_order INTEGER,
                    created_at TEXT,
                    completed_at TEXT
                )
            """)
            
            # 文件夹批量转写表
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS folder_batch (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    folder_path TEXT NOT NULL,
                    folder_name TEXT NOT NULL,
                    total_files INTEGER DEFAULT 0,
                    completed_files INTEGER DEFAULT 0,
                    failed_files INTEGER DEFAULT 0,
                    status TEXT DEFAULT 'pending',
                    merged_text TEXT,
                    merged_char_count INTEGER,
                    error_message TEXT,
                    created_at TEXT,
                    completed_at TEXT
                )
            """)
            
            # 文件记录表（已完成的文件）
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS files (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    file_name TEXT NOT NULL,
                    file_path TEXT NOT NULL,
                    file_size INTEGER,
                    file_type TEXT,
                    mime_type TEXT,
                    md5_hash TEXT,
                    tags TEXT,
                    description TEXT,
                    created_at TEXT,
                    accessed_at TEXT,
                    FOREIGN KEY (file_path) REFERENCES upload_tasks(file_path) ON DELETE SET NULL
                )
            """)
            
            # 创建索引
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_upload_status ON upload_tasks(status)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_transcribe_status ON transcribe_tasks(status)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_files_name ON files(file_name)")
    
    # ========== 上传任务 ==========
    
    def create_upload_task(self, task_id: str, file_name: str, file_size: int, 
                          total_chunks: int, file_hash: str = None) -> bool:
        """创建上传任务"""
        try:
            with self.get_conn() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO upload_tasks 
                    (task_id, file_name, file_size, total_chunks, file_hash, status, created_at)
                    VALUES (?, ?, ?, ?, ?, 'uploading', ?)
                """, (task_id, file_name, file_size, total_chunks, file_hash, datetime.now().isoformat()))
                return True
        except Exception as e:
            logger.error("[DB] 创建上传任务失败: %s", e, exc_info=True)
            return False
    
    def update_upload_progress(self, task_id: str, uploaded_chunks: int) -> bool:
        """更新上传进度"""
        try:
            with self.get_conn() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    UPDATE upload_tasks SET uploaded_chunks = ? WHERE task_id = ?
                """, (uploaded_chunks, task_id))
                return True
        except Exception as e:
            logger.error("[DB] 更新上传进度失败: %s", e, exc_info=True)
            return False
    
    def complete_upload(self, task_id: str, file_path: str) -> bool:
        """完成上传"""
        try:
            with self.get_conn() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    UPDATE upload_tasks 
                    SET status = 'completed', file_path = ?, completed_at = ?
                    WHERE task_id = ?
                """, (file_path, datetime.now().isoformat(), task_id))
                return True
        except Exception as e:
            logger.error("[DB] 完成上传失败: %s", e, exc_info=True)
            return False
    
    def get_upload_task(self, task_id: str) -> Optional[Dict]:
        """获取上传任务"""
        with self.get_conn() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM upload_tasks WHERE task_id = ?", (task_id,))
            row = cursor.fetchone()
            return dict(row) if row else None
    
    def list_upload_tasks(self, status: str = None, limit: int = 100) -> List[Dict]:
        """列出上传任务"""
        with self.get_conn() as conn:
            cursor = conn.cursor()
            if status:
                cursor.execute("""
                    SELECT * FROM upload_tasks 
                    WHERE status = ? 
                    ORDER BY created_at DESC LIMIT ?
                """, (status, limit))
            else:
                cursor.execute("SELECT * FROM upload_tasks ORDER BY created_at DESC LIMIT ?", (limit,))
            return [dict(row) for row in cursor.fetchall()]
    
    def delete_upload_task(self, task_id: str) -> bool:
        """删除上传任务"""
        try:
            with self.get_conn() as conn:
                cursor = conn.cursor()
                cursor.execute("DELETE FROM chunks WHERE task_id = ?", (task_id,))
                cursor.execute("DELETE FROM upload_tasks WHERE task_id = ?", (task_id,))
                return True
        except Exception as e:
            logger.error("[DB] 删除上传任务失败: %s", e, exc_info=True)
            return False
    
    # ========== 分片记录 ==========
    
    def add_chunk(self, task_id: str, chunk_index: int, chunk_hash: str, size: int) -> bool:
        """添加分片记录"""
        try:
            with self.get_conn() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT OR REPLACE INTO chunks 
                    (task_id, chunk_index, chunk_hash, size, created_at)
                    VALUES (?, ?, ?, ?, ?)
                """, (task_id, chunk_index, chunk_hash, size, datetime.now().isoformat()))
                return True
        except Exception as e:
            logger.error("[DB] 添加分片记录失败: %s", e, exc_info=True)
            return False
    
    def get_chunks(self, task_id: str) -> List[Dict]:
        """获取任务的所有分片"""
        with self.get_conn() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM chunks WHERE task_id = ? ORDER BY chunk_index
            """, (task_id,))
            return [dict(row) for row in cursor.fetchall()]
    
    def get_uploaded_chunk_indices(self, task_id: str) -> List[int]:
        """获取已上传的分片索引"""
        with self.get_conn() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT chunk_index FROM chunks WHERE task_id = ? ORDER BY chunk_index", (task_id,))
            return [row['chunk_index'] for row in cursor.fetchall()]
    
    # ========== 转写任务 ==========
    
    def create_transcribe_task(self, task_id: str, source_file: str, 
                               source_type: str = "file", language: str = "zh") -> bool:
        """创建转写任务"""
        try:
            with self.get_conn() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO transcribe_tasks 
                    (task_id, source_file, source_type, language, status, created_at)
                    VALUES (?, ?, ?, ?, 'pending', ?)
                """, (task_id, source_file, source_type, language, datetime.now().isoformat()))
                return True
        except Exception as e:
            logger.error("[DB] 创建转写任务失败: %s", e, exc_info=True)
            return False
    
    def update_transcribe_progress(self, task_id: str, status: str, 
                                   output_text: str = None, output_json: str = None,
                                   duration: float = None, error: str = None) -> bool:
        """更新转写进度"""
        try:
            with self.get_conn() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    UPDATE transcribe_tasks 
                    SET status = ?, output_text = ?, output_json = ?, 
                        duration = ?, error_message = ?,
                        completed_at = CASE WHEN ? = 'completed' THEN ? ELSE completed_at END
                    WHERE task_id = ?
                """, (status, output_text, output_json, duration, error, 
                      status, datetime.now().isoformat(), task_id))
                return True
        except Exception as e:
            logger.error("[DB] 更新转写进度失败: %s", e, exc_info=True)
            return False
    
    def get_transcribe_task(self, task_id: str) -> Optional[Dict]:
        """获取转写任务"""
        with self.get_conn() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM transcribe_tasks WHERE task_id = ?", (task_id,))
            row = cursor.fetchone()
            return dict(row) if row else None
    
    def list_transcribe_tasks(self, status: str = None, limit: int = 100) -> List[Dict]:
        """列出转写任务"""
        with self.get_conn() as conn:
            cursor = conn.cursor()
            if status:
                cursor.execute("""
                    SELECT * FROM transcribe_tasks 
                    WHERE status = ? 
                    ORDER BY created_at DESC LIMIT ?
                """, (status, limit))
            else:
                cursor.execute("SELECT * FROM transcribe_tasks ORDER BY created_at DESC LIMIT ?", (limit,))
            return [dict(row) for row in cursor.fetchall()]
    

    # ========== 文本提取 ==========
    
    def create_extract_task(self, file_path: str, file_name: str, file_type: str, file_ext: str) -> int:
        """创建文本提取任务，返回任务ID"""
        try:
            with self.get_conn() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO extract_tasks (file_path, file_name, file_type, file_ext, status, created_at)
                    VALUES (?, ?, ?, ?, 'pending', ?)
                """, (file_path, file_name, file_type, file_ext, datetime.now().isoformat()))
                return cursor.lastrowid
        except Exception as e:
            logger.error("[DB] 创建提取任务失败: %s", e, exc_info=True)
            return None
    
    def update_extract_task(self, task_id: int, status: str = None, 
                           text_content: str = None, char_count: int = None,
                           error_message: str = None, auto_processed: bool = None) -> bool:
        """更新提取任务"""
        try:
            with self.get_conn() as conn:
                cursor = conn.cursor()
                updates = []
                params = []
                if status:
                    updates.append("status = ?")
                    params.append(status)
                if text_content:
                    updates.append("text_content = ?")
                    params.append(text_content)
                if char_count is not None:
                    updates.append("char_count = ?")
                    params.append(char_count)
                if error_message:
                    updates.append("error_message = ?")
                    params.append(error_message)
                if auto_processed is not None:
                    updates.append("auto_processed = ?")
                    params.append(1 if auto_processed else 0)
                if status == 'completed':
                    updates.append("completed_at = ?")
                    params.append(datetime.now().isoformat())
                if not updates:
                    return False
                params.append(task_id)
                cursor.execute(f"UPDATE extract_tasks SET {', '.join(updates)} WHERE id = ?", params)
                return True
        except Exception as e:
            logger.error("[DB] 更新提取任务失败: %s", e, exc_info=True)
            return False
    
    # ========== 文件夹批量转写 ==========
    
    def create_folder_batch(self, folder_path: str, folder_name: str, total_files: int) -> int:
        """创建文件夹批量转写任务"""
        try:
            with self.get_conn() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO folder_batch (folder_path, folder_name, total_files, status, created_at)
                    VALUES (?, ?, ?, 'pending', ?)
                """, (folder_path, folder_name, total_files, datetime.now().isoformat()))
                return cursor.lastrowid
        except Exception as e:
            logger.error("[DB] 创建文件夹批量任务失败: %s", e, exc_info=True)
            return None
    
    def update_folder_batch(self, batch_id: int, status: str = None,
                           completed_files: int = None, failed_files: int = None,
                           merged_text: str = None, merged_char_count: int = None,
                           error_message: str = None) -> bool:
        """更新文件夹批量任务"""
        try:
            with self.get_conn() as conn:
                cursor = conn.cursor()
                updates = []
                params = []
                if status:
                    updates.append("status = ?")
                    params.append(status)
                if completed_files is not None:
                    updates.append("completed_files = ?")
                    params.append(completed_files)
                if failed_files is not None:
                    updates.append("failed_files = ?")
                    params.append(failed_files)
                if merged_text:
                    updates.append("merged_text = ?")
                    params.append(merged_text)
                if merged_char_count is not None:
                    updates.append("merged_char_count = ?")
                    params.append(merged_char_count)
                if error_message:
                    updates.append("error_message = ?")
                    params.append(error_message)
                if status == 'completed':
                    updates.append("completed_at = ?")
                    params.append(datetime.now().isoformat())
                if not updates:
                    return False
                params.append(batch_id)
                cursor.execute(f"UPDATE folder_batch SET {', '.join(updates)} WHERE id = ?", params)
                return True
        except Exception as e:
            logger.error("[DB] 更新文件夹批量任务失败: %s", e, exc_info=True)
            return False
    
    def get_folder_batch(self, batch_id: int) -> dict:
        """获取文件夹批量任务"""
        try:
            with self.get_conn() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT * FROM folder_batch WHERE id = ?", (batch_id,))
                row = cursor.fetchone()
                if row:
                    return dict(row)
                return None
        except Exception as e:
            logger.error("[DB] 获取文件夹批量任务失败: %s", e, exc_info=True)
            return None
    
    def list_folder_batches(self, status: str = None, limit: int = 50) -> list:
        """列出文件夹批量任务"""
        try:
            with self.get_conn() as conn:
                cursor = conn.cursor()
                if status:
                    cursor.execute("SELECT * FROM folder_batch WHERE status = ? ORDER BY id DESC LIMIT ?", (status, limit))
                else:
                    cursor.execute("SELECT * FROM folder_batch ORDER BY id DESC LIMIT ?", (limit,))
                return [dict(row) for row in cursor.fetchall()]
        except Exception as e:
            logger.error("[DB] 列出文件夹批量任务失败: %s", e, exc_info=True)
            return []
    
    def add_extract_to_batch(self, batch_id: int, task_id: int) -> bool:
        """将提取任务关联到批量任务"""
        try:
            with self.get_conn() as conn:
                cursor = conn.cursor()
                cursor.execute("UPDATE extract_tasks SET folder_batch_id = ? WHERE id = ?", (batch_id, task_id))
                return True
        except Exception as e:
            logger.error("[DB] 关联提取任务到批量任务失败: %s", e, exc_info=True)
            return False
    
    def list_extract_tasks(self, status: str = None, limit: int = 100) -> List[Dict]:
        """列出提取任务"""
        with self.get_conn() as conn:
            cursor = conn.cursor()
            if status:
                cursor.execute("""
                    SELECT * FROM extract_tasks 
                    WHERE status = ? 
                    ORDER BY created_at DESC LIMIT ?
                """, (status, limit))
            else:
                cursor.execute("SELECT * FROM extract_tasks ORDER BY created_at DESC LIMIT ?", (limit,))
            return [dict(row) for row in cursor.fetchall()]
    
    def get_extract_stats(self) -> Dict[str, int]:
        """获取提取统计"""
        with self.get_conn() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT status, COUNT(*) as count FROM extract_tasks GROUP BY status
            """)
            rows = cursor.fetchall()
            stats = {"total": 0, "pending": 0, "processing": 0, "completed": 0, "error": 0}
            for row in rows:
                s = row[0] or "unknown"
                c = row[1]
                stats["total"] += c
                if s in stats:
                    stats[s] = c
            return stats
    
    def is_file_extracted(self, file_path: str) -> bool:
        """检查文件是否已提取"""
        with self.get_conn() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT id FROM extract_tasks 
                WHERE file_path = ? AND status = 'completed'
            """, (file_path,))
            return cursor.fetchone() is not None

    # ========== 文件夹上传 ==========
    
    def create_folder_upload(self, folder_id: str, folder_name: str, 
                            total_files: int, total_size: int) -> bool:
        """创建文件夹上传任务"""
        try:
            with self.get_conn() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO folder_uploads 
                    (folder_id, folder_name, total_files, total_size, status, created_at)
                    VALUES (?, ?, ?, ?, 'uploading', ?)
                """, (folder_id, folder_name, total_files, total_size, datetime.now().isoformat()))
                return True
        except Exception as e:
            logger.error("[DB] 创建文件夹上传任务失败: %s", e, exc_info=True)
            return False
    
    def update_folder_progress(self, folder_id: str, uploaded_files: int, uploaded_size: int) -> bool:
        """更新文件夹上传进度"""
        try:
            with self.get_conn() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    UPDATE folder_uploads 
                    SET uploaded_files = ?, uploaded_size = ?
                    WHERE folder_id = ?
                """, (uploaded_files, uploaded_size, folder_id))
                return True
        except Exception as e:
            logger.error("[DB] 更新文件夹进度失败: %s", e, exc_info=True)
            return False
    
    def complete_folder_upload(self, folder_id: str) -> bool:
        """完成文件夹上传"""
        try:
            with self.get_conn() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    UPDATE folder_uploads 
                    SET status = 'completed', completed_at = ?
                    WHERE folder_id = ?
                """, (datetime.now().isoformat(), folder_id))
                return True
        except Exception as e:
            logger.error("[DB] 完成文件夹上传失败: %s", e, exc_info=True)
            return False
    
    def list_folder_uploads(self) -> List[Dict]:
        """列出文件夹上传任务"""
        with self.get_conn() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM folder_uploads ORDER BY created_at DESC")
            return [dict(row) for row in cursor.fetchall()]
    
    # ========== 统计 ==========
    
    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        with self.get_conn() as conn:
            cursor = conn.cursor()

            stats = {}

            # 上传统计
            cursor.execute("SELECT COUNT(*) as count, SUM(file_size) as total_size FROM upload_tasks WHERE status = 'completed'")
            row = cursor.fetchone()
            stats['completed_uploads'] = row['count'] or 0
            stats['total_upload_size'] = row['total_size'] or 0

            # 进行中的上传
            cursor.execute("SELECT COUNT(*) as count FROM upload_tasks WHERE status = 'uploading'")
            stats['active_uploads'] = cursor.fetchone()['count']

            # 转写统计
            cursor.execute("SELECT COUNT(*) as count FROM transcribe_tasks WHERE status = 'completed'")
            stats['completed_transcribes'] = cursor.fetchone()['count']

            # 转写时长
            cursor.execute("SELECT SUM(duration) as total_duration FROM transcribe_tasks WHERE status = 'completed'")
            stats['total_transcribe_duration'] = cursor.fetchone()['total_duration'] or 0

            return stats

    # ========== 云盘管理 ==========

    def init_cloud_tables(self):
        """初始化云盘相关表"""
        with self.get_conn() as conn:
            cursor = conn.cursor()

            # 云盘配置表
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS cloud_disks (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    disk_id TEXT UNIQUE NOT NULL,
                    name TEXT NOT NULL,
                    disk_type TEXT NOT NULL,
                    host TEXT,
                    username TEXT,
                    password TEXT,
                    token TEXT,
                    mount_path TEXT NOT NULL,
                    is_active INTEGER DEFAULT 1,
                    last_sync_at TEXT,
                    created_at TEXT,
                    updated_at TEXT
                )
            """)

            # 同步任务表
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS sync_tasks (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    task_id TEXT UNIQUE NOT NULL,
                    disk_id TEXT NOT NULL,
                    direction TEXT NOT NULL,
                    status TEXT DEFAULT 'pending',
                    total_files INTEGER DEFAULT 0,
                    synced_files INTEGER DEFAULT 0,
                    total_size INTEGER DEFAULT 0,
                    synced_size INTEGER DEFAULT 0,
                    error_message TEXT,
                    started_at TEXT,
                    completed_at TEXT,
                    created_at TEXT,
                    FOREIGN KEY (disk_id) REFERENCES cloud_disks(disk_id) ON DELETE CASCADE
                )
            """)

            # 知识导入记录表
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS knowledge_imports (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    import_id TEXT UNIQUE NOT NULL,
                    source_path TEXT NOT NULL,
                    target_path TEXT,
                    category TEXT,
                    file_count INTEGER DEFAULT 0,
                    success_count INTEGER DEFAULT 0,
                    fail_count INTEGER DEFAULT 0,
                    status TEXT DEFAULT 'pending',
                    error_message TEXT,
                    created_at TEXT,
                    completed_at TEXT
                )
            """)

            # 文件标签表
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS file_tags (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    file_path TEXT NOT NULL,
                    tag TEXT NOT NULL,
                    created_at TEXT,
                    UNIQUE(file_path, tag)
                )
            """)

            # ============================================================
            # 知识导入-文件级状态表（v0.2.0 多目录版）
            # 区别于 knowledge_imports（按批次）：本表按"每个文件"记录状态
            # 状态机：pending → processing → processed / failed
            # 幂等键：file_hash (SHA256 of file content)
            # ============================================================
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS knowledge_files (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    file_path TEXT UNIQUE NOT NULL,
                    file_name TEXT NOT NULL,
                    file_size INTEGER,
                    file_hash TEXT,
                    file_ext TEXT,
                    category TEXT,
                    status TEXT DEFAULT 'pending',
                    error_message TEXT,
                    knowledge_id TEXT,
                    source_import_id TEXT,
                    retry_count INTEGER DEFAULT 0,
                    discovered_at TEXT,
                    processed_at TEXT,
                    FOREIGN KEY (source_import_id) REFERENCES knowledge_imports(import_id) ON DELETE SET NULL
                )
            """)

            # 状态机常量（避免拼写错）
            # pending: 已发现，待处理
            # processing: 正在转
            # processed: 转换完成，知识已写入 Hindsight/OpenViking
            # failed: 失败，error_message 有错

            # 创建索引
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_cloud_disks_active ON cloud_disks(is_active)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_sync_tasks_status ON sync_tasks(status)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_knowledge_status ON knowledge_imports(status)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_file_tags_path ON file_tags(file_path)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_knowledge_files_status ON knowledge_files(status)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_knowledge_files_hash ON knowledge_files(file_hash)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_knowledge_files_ext ON knowledge_files(file_ext)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_file_tags_tag ON file_tags(tag)")

    # ========== 云盘 CRUD ==========

    def create_cloud_disk(self, disk_id: str, name: str, disk_type: str, mount_path: str,
                         host: str = None, username: str = None, password: str = None,
                         token: str = None) -> bool:
        """创建云盘配置"""
        try:
            with self.get_conn() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO cloud_disks
                    (disk_id, name, disk_type, host, username, password, token, mount_path, is_active, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, 1, ?, ?)
                """, (disk_id, name, disk_type, host, username, password, token, mount_path,
                      datetime.now().isoformat(), datetime.now().isoformat()))
                return True
        except Exception as e:
            logger.error("[DB] 创建云盘配置失败: %s", e, exc_info=True)
            return False

    def list_cloud_disks(self, active_only: bool = True) -> List[Dict]:
        """列出云盘"""
        with self.get_conn() as conn:
            cursor = conn.cursor()
            if active_only:
                cursor.execute("SELECT * FROM cloud_disks WHERE is_active = 1 ORDER BY created_at DESC")
            else:
                cursor.execute("SELECT * FROM cloud_disks ORDER BY created_at DESC")
            return [dict(row) for row in cursor.fetchall()]

    def update_cloud_disk_sync(self, disk_id: str) -> bool:
        """更新云盘同步时间"""
        try:
            with self.get_conn() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    UPDATE cloud_disks SET last_sync_at = ?, updated_at = ? WHERE disk_id = ?
                """, (datetime.now().isoformat(), datetime.now().isoformat(), disk_id))
                return True
        except Exception as e:
            logger.error("[DB] 更新云盘同步时间失败: %s", e, exc_info=True)
            return False

    def delete_cloud_disk(self, disk_id: str) -> bool:
        """删除云盘"""
        try:
            with self.get_conn() as conn:
                cursor = conn.cursor()
                cursor.execute("DELETE FROM cloud_disks WHERE disk_id = ?", (disk_id,))
                return True
        except Exception as e:
            logger.error("[DB] 删除云盘失败: %s", e, exc_info=True)
            return False

    # ========== 同步任务 ==========

    def create_sync_task(self, task_id: str, disk_id: str, direction: str,
                        total_files: int = 0, total_size: int = 0) -> bool:
        """创建同步任务"""
        try:
            with self.get_conn() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO sync_tasks
                    (task_id, disk_id, direction, total_files, total_size, status, created_at)
                    VALUES (?, ?, ?, ?, ?, 'running', ?)
                """, (task_id, disk_id, direction, total_files, total_size, datetime.now().isoformat()))
                return True
        except Exception as e:
            logger.error("[DB] 创建同步任务失败: %s", e, exc_info=True)
            return False

    def update_sync_progress(self, task_id: str, synced_files: int, synced_size: int) -> bool:
        """更新同步进度"""
        try:
            with self.get_conn() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    UPDATE sync_tasks SET synced_files = ?, synced_size = ? WHERE task_id = ?
                """, (synced_files, synced_size, task_id))
                return True
        except Exception as e:
            logger.error("[DB] 更新同步进度失败: %s", e, exc_info=True)
            return False

    def complete_sync_task(self, task_id: str, status: str = 'completed', error: str = None) -> bool:
        """完成同步任务"""
        try:
            with self.get_conn() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    UPDATE sync_tasks
                    SET status = ?, error_message = ?, completed_at = ?
                    WHERE task_id = ?
                """, (status, error, datetime.now().isoformat(), task_id))
                return True
        except Exception as e:
            logger.error("[DB] 完成同步任务失败: %s", e, exc_info=True)
            return False

    def list_sync_tasks(self, disk_id: str = None, status: str = None, limit: int = 50) -> List[Dict]:
        """列出同步任务"""
        with self.get_conn() as conn:
            cursor = conn.cursor()
            query = "SELECT * FROM sync_tasks WHERE 1=1"
            params = []
            if disk_id:
                query += " AND disk_id = ?"
                params.append(disk_id)
            if status:
                query += " AND status = ?"
                params.append(status)
            query += " ORDER BY created_at DESC LIMIT ?"
            params.append(limit)
            cursor.execute(query, params)
            return [dict(row) for row in cursor.fetchall()]

    # ========== 知识导入 ==========

    def create_knowledge_import(self, import_id: str, source_path: str, category: str = None,
                               file_count: int = 0) -> bool:
        """创建知识导入记录"""
        try:
            with self.get_conn() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO knowledge_imports
                    (import_id, source_path, category, file_count, status, created_at)
                    VALUES (?, ?, ?, ?, 'processing', ?)
                """, (import_id, source_path, category, file_count, datetime.now().isoformat()))
                return True
        except Exception as e:
            logger.error("[DB] 创建知识导入记录失败: %s", e, exc_info=True)
            return False

    def update_knowledge_import(self, import_id: str, success_count: int = None,
                               fail_count: int = None, status: str = None, error: str = None) -> bool:
        """更新知识导入进度"""
        try:
            with self.get_conn() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    UPDATE knowledge_imports
                    SET success_count = COALESCE(?, success_count),
                        fail_count = COALESCE(?, fail_count),
                        status = COALESCE(?, status),
                        error_message = ?
                    WHERE import_id = ?
                """, (success_count, fail_count, status, error, import_id))
                return True
        except Exception as e:
            logger.error("[DB] 更新知识导入进度失败: %s", e, exc_info=True)
            return False

    def complete_knowledge_import(self, import_id: str, target_path: str = None) -> bool:
        """完成知识导入"""
        try:
            with self.get_conn() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    UPDATE knowledge_imports
                    SET status = 'completed', target_path = ?, completed_at = ?
                    WHERE import_id = ?
                """, (target_path, datetime.now().isoformat(), import_id))
                return True
        except Exception as e:
            logger.error("[DB] 完成知识导入失败: %s", e, exc_info=True)
            return False

    def list_knowledge_imports(self, status: str = None, limit: int = 100) -> List[Dict]:
        """列出知识导入记录"""
        with self.get_conn() as conn:
            cursor = conn.cursor()
            if status:
                cursor.execute("""
                    SELECT * FROM knowledge_imports WHERE status = ?
                    ORDER BY created_at DESC LIMIT ?
                """, (status, limit))
            else:
                cursor.execute("SELECT * FROM knowledge_imports ORDER BY created_at DESC LIMIT ?", (limit,))
            return [dict(row) for row in cursor.fetchall()]

    def get_knowledge_stats(self) -> Dict[str, Any]:
        """获取知识导入统计"""
        with self.get_conn() as conn:
            cursor = conn.cursor()
            stats = {}
            cursor.execute("SELECT COUNT(*) as count FROM knowledge_imports WHERE status = 'completed'")
            stats['completed_imports'] = cursor.fetchone()['count']
            cursor.execute("SELECT SUM(success_count) as total FROM knowledge_imports")
            stats['total_files_imported'] = cursor.fetchone()['total'] or 0
            cursor.execute("SELECT COUNT(*) as count FROM knowledge_imports WHERE status = 'processing'")
            stats['active_imports'] = cursor.fetchone()['count']
            return stats

    # ========== 文件标签 ==========

    def add_file_tag(self, file_path: str, tag: str) -> bool:
        """添加文件标签"""
        try:
            with self.get_conn() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT OR IGNORE INTO file_tags (file_path, tag, created_at)
                    VALUES (?, ?, ?)
                """, (file_path, tag, datetime.now().isoformat()))
                return True
        except Exception as e:
            logger.error("[DB] 添加文件标签失败: %s", e, exc_info=True)
            return False

    def remove_file_tag(self, file_path: str, tag: str) -> bool:
        """移除文件标签"""
        try:
            with self.get_conn() as conn:
                cursor = conn.cursor()
                cursor.execute("DELETE FROM file_tags WHERE file_path = ? AND tag = ?", (file_path, tag))
                return True
        except Exception as e:
            logger.error("[DB] 移除文件标签失败: %s", e, exc_info=True)
            return False

    def get_file_tags(self, file_path: str) -> List[str]:
        """获取文件标签"""
        with self.get_conn() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT tag FROM file_tags WHERE file_path = ?", (file_path,))
            return [row['tag'] for row in cursor.fetchall()]

    def get_all_tags(self) -> List[Dict]:
        """获取所有标签及其使用次数"""
        with self.get_conn() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT tag, COUNT(*) as count
                FROM file_tags
                GROUP BY tag
                ORDER BY count DESC
            """)
            return [dict(row) for row in cursor.fetchall()]

    def get_files_by_tag(self, tag: str) -> List[str]:
        """按标签查询文件"""
        with self.get_conn() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT file_path FROM file_tags WHERE tag = ?", (tag,))
            return [row['file_path'] for row in cursor.fetchall()]

    # ========== knowledge_files CRUD（v0.2.0 多目录版）==========
    def upsert_knowledge_file(
        self,
        file_path: str,
        file_name: str,
        file_size: int,
        file_hash: Optional[str],
        file_ext: str,
        category: str = "其他",
        status: str = "pending",
    ) -> int:
        """
        插入或更新知识文件记录（按 file_path 幂等）
        - 如果 hash 不同：更新 hash + status=pending（内容变了，重转）
        - 如果 hash 相同 + status=processed：不重置（保持 processed）
        """
        with self.get_conn() as conn:
            cursor = conn.cursor()
            now = datetime.now().isoformat()
            # 查现有
            cursor.execute("SELECT id, file_hash, status FROM knowledge_files WHERE file_path = ?", (file_path,))
            row = cursor.fetchone()
            if row is None:
                cursor.execute("""
                    INSERT INTO knowledge_files
                        (file_path, file_name, file_size, file_hash, file_ext, category, status, discovered_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (file_path, file_name, file_size, file_hash, file_ext, category, status, now))
                return cursor.lastrowid
            else:
                # 现有记录
                old_hash, old_status = row['file_hash'], row['status']
                new_status = old_status if (old_status == "processed" and old_hash == file_hash) else status
                cursor.execute("""
                    UPDATE knowledge_files
                    SET file_name=?, file_size=?, file_hash=?, file_ext=?, category=?, status=?
                    WHERE id=?
                """, (file_name, file_size, file_hash, file_ext, category, new_status, row['id']))
                return row['id']

    def mark_knowledge_processing(self, file_path: str) -> bool:
        """标记为处理中（避免重复处理）"""
        with self.get_conn() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE knowledge_files SET status='processing', retry_count=retry_count+1 WHERE file_path=?",
                (file_path,)
            )
            return cursor.rowcount > 0

    def mark_knowledge_processed(
        self,
        file_path: str,
        knowledge_id: Optional[str] = None,
        source_import_id: Optional[str] = None,
    ) -> bool:
        """标记为已处理完成"""
        with self.get_conn() as conn:
            cursor = conn.cursor()
            now = datetime.now().isoformat()
            cursor.execute("""
                UPDATE knowledge_files
                SET status='processed', knowledge_id=?, source_import_id=?, processed_at=?, error_message=NULL
                WHERE file_path=?
            """, (knowledge_id, source_import_id, now, file_path))
            return cursor.rowcount > 0

    def mark_knowledge_failed(self, file_path: str, error_message: str) -> bool:
        """标记为失败"""
        with self.get_conn() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE knowledge_files
                SET status='failed', error_message=?
                WHERE file_path=?
            """, (error_message[:1000], file_path))
            return cursor.rowcount > 0

    def get_knowledge_file(self, file_path: str) -> Optional[Dict]:
        """获取单条记录"""
        with self.get_conn() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM knowledge_files WHERE file_path=?", (file_path,))
            row = cursor.fetchone()
            return dict(row) if row else None

    def list_knowledge_files(
        self,
        status: Optional[str] = None,
        category: Optional[str] = None,
        limit: int = 200,
    ) -> List[Dict]:
        """列出知识文件（按状态/分类过滤）"""
        with self.get_conn() as conn:
            cursor = conn.cursor()
            query = "SELECT * FROM knowledge_files WHERE 1=1"
            params = []
            if status:
                query += " AND status=?"
                params.append(status)
            if category:
                query += " AND category=?"
                params.append(category)
            query += " ORDER BY discovered_at DESC LIMIT ?"
            params.append(limit)
            cursor.execute(query, params)
            return [dict(row) for row in cursor.fetchall()]

    def get_knowledge_stats(self) -> Dict[str, int]:
        """统计：pending/processing/processed/failed 数量"""
        with self.get_conn() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT status, COUNT(*) as cnt
                FROM knowledge_files
                GROUP BY status
            """)
            stats = {"pending": 0, "processing": 0, "processed": 0, "failed": 0, "total": 0}
            for row in cursor.fetchall():
                stats[row['status']] = row['cnt']
                stats['total'] += row['cnt']
            return stats

    def get_storage_stats(self) -> Dict[str, Any]:
        """获取存储统计"""
        with self.get_conn() as conn:
            cursor = conn.cursor()
            stats = {}

            # 上传目录大小
            uploads_path = "/root/.openclaw/workspace/learning/uploads"
            if os.path.exists(uploads_path):
                total_size = sum(f.stat().st_size for f in Path(uploads_path).rglob('*') if f.is_file())
                stats['uploads_size'] = total_size
                stats['uploads_count'] = len(list(Path(uploads_path).rglob('*.*')))
            else:
                stats['uploads_size'] = 0
                stats['uploads_count'] = 0

            # 数据库统计
            cursor.execute("SELECT SUM(file_size) as total FROM upload_tasks WHERE status = 'completed'")
            stats['db_total_size'] = cursor.fetchone()['total'] or 0

            cursor.execute("SELECT COUNT(*) as count FROM upload_tasks WHERE status = 'completed'")
            stats['db_total_files'] = cursor.fetchone()['count']

            return stats


# 全局数据库实例
_db: Optional[LearningDB] = None


def get_db(db_path: str = None) -> LearningDB:
    """获取数据库单例"""
    global _db
    if _db is None:
        if db_path is None:
            db_path = "/root/.openclaw/workspace/learning/learning.db"
        _db = LearningDB(db_path)
    return _db
