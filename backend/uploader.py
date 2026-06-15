"""
分片上传模块
支持大文件、分片、断点续传
"""
import os
import uuid
import aiofiles
import asyncio
import logging
from datetime import datetime
from typing import Dict

logger = logging.getLogger(__name__)


class ChunkUploader:
    """分片上传处理器"""

    def __init__(self, upload_dir: str):
        self.upload_dir = upload_dir
        os.makedirs(upload_dir, exist_ok=True)
        self.tasks: Dict[str, dict] = {}

    async def init_upload(self, filename: str, total_chunks: int, file_size: int):
        """初始化上传任务"""
        task_id = str(uuid.uuid4())[:8]
        logger.info(f"[Uploader] 初始化上传: {filename} 分片={total_chunks} 大小={file_size} task={task_id}")

        # 检查已上传的分片
        chunk_dir = os.path.join(self.upload_dir, task_id)
        os.makedirs(chunk_dir, exist_ok=True)

        existing_chunks = set()
        if os.path.exists(chunk_dir):
            for f in os.listdir(chunk_dir):
                if f.endswith('.chunk'):
                    existing_chunks.add(int(f.split('.')[0]))

        self.tasks[task_id] = {
            "filename": filename,
            "total_chunks": total_chunks,
            "file_size": file_size,
            "uploaded_chunks": existing_chunks,
            "chunk_dir": chunk_dir,
            "created_at": datetime.now().isoformat()
        }

        return {
            "task_id": task_id,
            "uploaded_chunks": list(existing_chunks),
            "total_chunks": total_chunks
        }

    async def upload_chunk(self, task_id: str, chunk_index: int, data: bytes):
        """上传单个分片"""
        if task_id not in self.tasks:
            logger.warning(f"[Uploader] 上传分片失败: task_id={task_id} 不存在")
            raise Exception("上传任务不存在")

        task = self.tasks[task_id]

        # 保存分片
        chunk_path = os.path.join(task["chunk_dir"], f"{chunk_index}.chunk")
        async with aiofiles.open(chunk_path, 'wb') as f:
            await f.write(data)

        task["uploaded_chunks"].add(chunk_index)

        # 返回进度
        progress = len(task["uploaded_chunks"]) / task["total_chunks"] * 100
        logger.debug(f"[Uploader] 分片 {chunk_index} 上传完成 进度={progress:.1f}%")
        return {
            "chunk_index": chunk_index,
            "uploaded": len(task["uploaded_chunks"]),
            "total": task["total_chunks"],
            "progress": round(progress, 1)
        }

    async def finish_upload(self, task_id: str):
        """完成上传，合并分片"""
        if task_id not in self.tasks:
            logger.warning(f"[Uploader] 完成上传失败: task_id={task_id} 不存在")
            raise Exception("上传任务不存在")

        task = self.tasks[task_id]
        logger.info(f"[Uploader] 合并分片: {task['filename']} 共 {task['total_chunks']} 片")

        # 检查是否所有分片都上传完成
        if len(task["uploaded_chunks"]) != task["total_chunks"]:
            missing = set(range(task["total_chunks"])) - task["uploaded_chunks"]
            logger.warning(f"[Uploader] 分片不完整: 缺少 {len(missing)} 片")
            raise Exception(f"还有 {len(missing)} 个分片未上传: {sorted(missing)}")

        # 合并文件
        filename = task["filename"]
        output_path = os.path.join(self.upload_dir, filename)

        # 如果文件已存在，加时间戳
        if os.path.exists(output_path):
            name, ext = os.path.splitext(filename)
            output_path = os.path.join(self.upload_dir, f"{name}_{datetime.now().strftime('%H%M%S')}{ext}")

        with open(output_path, 'wb') as out:
            for i in range(task["total_chunks"]):
                chunk_path = os.path.join(task["chunk_dir"], f"{i}.chunk")
                with open(chunk_path, 'rb') as inp:
                    out.write(inp.read())

        # 清理分片目录
        for i in range(task["total_chunks"]):
            chunk_path = os.path.join(task["chunk_dir"], f"{i}.chunk")
            if os.path.exists(chunk_path):
                os.remove(chunk_path)
        os.rmdir(task["chunk_dir"])

        # 删除任务记录
        del self.tasks[task_id]
        logger.info(f"[Uploader] 上传完成: {output_path}")

        return {
            "path": output_path,
            "filename": os.path.basename(output_path),
            "size": task["file_size"]
        }

    def get_status(self, task_id: str):
        """获取上传状态"""
        if task_id not in self.tasks:
            return None

        task = self.tasks[task_id]
        progress = len(task["uploaded_chunks"]) / task["total_chunks"] * 100

        return {
            "filename": task["filename"],
            "uploaded_chunks": len(task["uploaded_chunks"]),
            "total_chunks": task["total_chunks"],
            "progress": round(progress, 1),
            "file_size": task["file_size"]
        }

    def cancel_upload(self, task_id: str):
        """取消上传"""
        if task_id not in self.tasks:
            logger.warning(f"[Uploader] 取消上传失败: task_id={task_id} 不存在")
            return
        logger.info(f"[Uploader] 取消上传: task_id={task_id}")

        task = self.tasks[task_id]
        chunk_dir = task["chunk_dir"]

        # 清理分片
        if os.path.exists(chunk_dir):
            for f in os.listdir(chunk_dir):
                if f.endswith('.chunk'):
                    os.remove(os.path.join(chunk_dir, f))
            os.rmdir(chunk_dir)

        del self.tasks[task_id]
