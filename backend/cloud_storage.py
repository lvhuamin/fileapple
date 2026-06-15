#!/usr/bin/env python3
"""
云盘管理器
支持多种网盘：阿里云盘、百度网盘、夸克网盘、天翼云、115等
"""
import os
import json
import asyncio
import hashlib
from pathlib import Path
from typing import Optional, List, Dict, Any
from dataclasses import dataclass, field
from datetime import datetime

import httpx
import logging

logger = logging.getLogger(__name__)

# ========== 网盘类型定义 ==========

@dataclass
class CloudDisk:
    """云盘配置"""
    id: str
    name: str
    type: str  # aliyun/baidu/quark/tianyi/115/local
    enabled: bool = True
    host: str = ""  # Alist地址
    token: str = ""
    mount_path: str = "/"  # 挂载到本地哪个路径
    username: str = ""  # 网盘账号
    password: str = ""  # 网盘密码
    refresh_token: str = ""  # OAuth刷新令牌
    last_sync: str = ""  # 上次同步时间
    status: str = "idle"  # idle/syncing/error
    file_count: int = 0
    total_size: int = 0


class CloudDiskManager:
    """云盘管理器"""

    def __init__(self, config_path: str = "/root/lvhuamin/fileapple/data/cloud_disks.json"):
        self.config_path = Path(config_path)
        self.config_path.parent.mkdir(parents=True, exist_ok=True)
        self.disks: Dict[str, CloudDisk] = {}
        self._load()

    def _load(self):
        """加载配置"""
        if self.config_path.exists():
            with open(self.config_path) as f:
                data = json.load(f)
                for d in data.get("disks", []):
                    self.disks[d["id"]] = CloudDisk(**d)
            logger.info(f"[CloudDisk] 加载 {len(self.disks)} 个网盘配置: {list(self.disks.keys())}")
        else:
            logger.info("[CloudDisk] 配置文件不存在，使用空配置")

    def _save(self):
        """保存配置"""
        with open(self.config_path, "w") as f:
            json.dump({"disks": [vars(d) for d in self.disks.values()]}, f, indent=2, ensure_ascii=False)
        logger.debug(f"[CloudDisk] 配置已保存，共 {len(self.disks)} 个网盘")

    def add_disk(self, disk: CloudDisk) -> bool:
        """添加网盘"""
        self.disks[disk.id] = disk
        self._save()
        return True

    def remove_disk(self, disk_id: str) -> bool:
        """移除网盘"""
        if disk_id in self.disks:
            del self.disks[disk_id]
            self._save()
            return True
        return False

    def get_disk(self, disk_id: str) -> Optional[CloudDisk]:
        return self.disks.get(disk_id)

    def list_disks(self) -> List[CloudDisk]:
        return list(self.disks.values())

    def update_disk_status(self, disk_id: str, status: str):
        """更新网盘状态"""
        if disk_id in self.disks:
            self.disks[disk_id].status = status
            self.disks[disk_id].last_sync = datetime.now().isoformat()
            self._save()


# ========== Alist 网盘适配器 ==========

class AlistAdapter:
    """Alist 网盘适配器"""

    def __init__(self, disk: CloudDisk):
        self.disk = disk
        self.client = httpx.AsyncClient(timeout=60.0)

    async def login(self, username: str, password: str) -> bool:
        """登录"""
        try:
            logger.info(f"[Alist] 登录 {self.disk.host} 用户={username}")
            resp = await self.client.post(
                f"{self.disk.host}/api/auth/login",
                json={"username": username, "password": password}
            )
            data = resp.json()
            if data.get("code") == 200:
                self.disk.token = data["data"]["token"]
                logger.info(f"[Alist] 登录成功: {self.disk.host}")
                return True
            logger.warning(f"[Alist] 登录失败: code={data.get('code')}")
            return False
        except Exception as e:
            logger.error(f"[Alist] 登录异常: {e}", exc_info=True)
            return False

    async def list_files(self, path: str = "/") -> List[Dict]:
        """列出文件"""
        if not self.disk.token:
            logger.warning(f"[Alist] list_files 无token，跳过: {path}")
            return []
        try:
            resp = await self.client.get(
                f"{self.disk.host}/api/fs/list",
                params={"path": path, "page": 1, "per_page": 100},
                headers={"Authorization": self.disk.token}
            )
            data = resp.json()
            if data.get("code") == 200:
                files = data.get("data", {}).get("content", [])
                logger.info(f"[Alist] list_files path={path} 返回 {len(files)} 个文件")
                return files
            logger.warning(f"[Alist] list_files 失败: code={data.get('code')}")
            return []
        except Exception as e:
            logger.error(f"[Alist] list_files 异常: {e}", exc_info=True)
            return []

    async def get_file_url(self, path: str) -> str:
        """获取文件直链"""
        if not self.disk.token:
            return ""
        try:
            resp = await self.client.post(
                f"{self.disk.host}/api/fs/link",
                json={"path": path},
                headers={"Authorization": self.disk.token}
            )
            data = resp.json()
            if data.get("code") == 200:
                return data["data"].get("raw_url", "")
            return ""
        except Exception as e:
            return ""

    async def download_file(self, remote_path: str, local_path: str) -> bool:
        """下载文件到本地"""
        url = await self.get_file_url(remote_path)
        if not url:
            logger.warning(f"[Alist] 无法获取下载链接: {remote_path}")
            return False
        try:
            logger.info(f"[Alist] 下载 {remote_path} -> {local_path}")
            resp = await self.client.get(url, follow_redirects=True)
            if resp.status_code == 200:
                Path(local_path).parent.mkdir(parents=True, exist_ok=True)
                with open(local_path, 'wb') as f:
                    f.write(resp.content)
                logger.info(f"[Alist] 下载完成: {local_path} ({len(resp.content)} bytes)")
                return True
            logger.warning(f"[Alist] 下载失败 status={resp.status_code}: {remote_path}")
        except Exception as e:
            logger.error(f"[Alist] 下载异常: {e}", exc_info=True)
        return False

    async def close(self):
        await self.client.aclose()


# ========== 同步管理器 ==========

class SyncManager:
    """文件同步管理器"""

    def __init__(self, manager: CloudDiskManager):
        self.manager = manager
        self.sync_queue: asyncio.Queue = asyncio.Queue()
        self.download_dir = Path("/root/.openclaw/workspace/learning/downloads")
        self.active_syncs: Dict[str, Dict] = {}  # 记录活跃的同步任务

    async def sync_disk(self, disk_id: str, remote_path: str = "/", local_category: str = "其他",
                       broadcast_func=None) -> Dict[str, Any]:
        """同步网盘文件到本地

        Args:
            disk_id: 云盘ID
            remote_path: 远程路径
            local_category: 本地分类目录
            broadcast_func: WebSocket广播函数
        """
        disk = self.manager.get_disk(disk_id)
        if not disk:
            logger.warning(f"[Sync] 网盘不存在: {disk_id}")
            return {"error": "网盘不存在"}

        import uuid
        task_id = str(uuid.uuid4())[:16]
        logger.info(f"[Sync] 开始同步 disk={disk_id} path={remote_path} task={task_id}")

        self.manager.update_disk_status(disk_id, "syncing")

        # 记录同步任务
        self.active_syncs[task_id] = {
            "task_id": task_id,
            "disk_id": disk_id,
            "status": "running",
            "total": 0,
            "synced": 0,
            "failed": 0,
            "start_time": datetime.now().isoformat()
        }

        async def _do_sync():
            try:
                if disk.type == "alist":
                    adapter = AlistAdapter(disk)
                    if disk.token:
                        adapter.disk.token = disk.token
                    else:
                        await adapter.login(disk.username, disk.password)

                    files = await adapter.list_files(remote_path)

                    # 统计
                    self.download_dir.mkdir(parents=True, exist_ok=True)
                    target_dir = self.download_dir / local_category
                    target_dir.mkdir(exist_ok=True)

                    total = len([f for f in files if not f.get("is_dir")])
                    synced = 0
                    failed = 0

                    self.active_syncs[task_id]["total"] = total

                    for f in files:
                        if f.get("is_dir"):
                            continue

                        # 发送进度更新
                        if broadcast_func:
                            await broadcast_func({
                                "type": "sync_progress",
                                "task_id": task_id,
                                "disk_id": disk_id,
                                "file": f["name"],
                                "synced": synced + 1,
                                "total": total,
                                "progress": (synced + 1) / total * 100 if total > 0 else 0
                            })

                        local_path = target_dir / f["name"]
                        if await adapter.download_file(f"/{f['sign']}", str(local_path)):
                            synced += 1
                        else:
                            failed += 1

                        self.active_syncs[task_id]["synced"] = synced
                        self.active_syncs[task_id]["failed"] = failed

                    await adapter.close()

                    self.manager.update_disk_status(disk_id, "idle")
                    disk.file_count = synced

                    # 发送完成消息
                    if broadcast_func:
                        await broadcast_func({
                            "type": "sync_complete",
                            "task_id": task_id,
                            "disk_id": disk_id,
                            "synced": synced,
                            "failed": failed,
                            "target": str(target_dir)
                        })

                    self.active_syncs[task_id]["status"] = "completed"

                    return {
                        "task_id": task_id,
                        "synced": synced,
                        "failed": failed,
                        "target": str(target_dir)
                    }
            except Exception as e:
                logger.error(f"[Sync] 同步失败 disk={disk_id} task={task_id}: {e}", exc_info=True)
                self.manager.update_disk_status(disk_id, "error")
                self.active_syncs[task_id]["status"] = "error"
                self.active_syncs[task_id]["error"] = str(e)

                if broadcast_func:
                    await broadcast_func({
                        "type": "sync_error",
                        "task_id": task_id,
                        "disk_id": disk_id,
                        "error": str(e)
                    })

                return {"error": str(e)}

        # 启动后台同步
        asyncio.create_task(_do_sync())

        return {
            "task_id": task_id,
            "status": "started",
            "message": "同步任务已启动"
        }

    def get_sync_status(self, task_id: str = None) -> Dict:
        """获取同步状态"""
        if task_id:
            return self.active_syncs.get(task_id, {})
        return {"active_syncs": list(self.active_syncs.values())}

    def cancel_sync(self, task_id: str) -> bool:
        """取消同步任务"""
        if task_id in self.active_syncs:
            self.active_syncs[task_id]["status"] = "cancelled"
            return True
        return False


# ========== 工厂函数 ==========

def get_cloud_disk_manager() -> CloudDiskManager:
    """获取云盘管理器单例"""
    global _cloud_disk_manager
    if _cloud_disk_manager is None:
        _cloud_disk_manager = CloudDiskManager()
    return _cloud_disk_manager


def get_sync_manager() -> SyncManager:
    """获取同步管理器"""
    global _sync_manager
    if _sync_manager is None:
        _sync_manager = SyncManager(get_cloud_disk_manager())
    return _sync_manager


_cloud_disk_manager: Optional[CloudDiskManager] = None
_sync_manager: Optional[SyncManager] = None
