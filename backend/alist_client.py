#!/usr/bin/env python3
"""
Alist API 客户端
用于连接外部 Alist 存储服务
"""

import os
import json
import httpx
import logging
from typing import Optional, List, Dict, Any
from pathlib import Path

logger = logging.getLogger(__name__)


class AlistClient:
    """Alist API 客户端"""
    
    def __init__(self, host: str = None, token: str = None):
        self.host = host or os.getenv("ALIST_HOST", "http://localhost:5244")
        self.token = token or os.getenv("ALIST_TOKEN", "")
        self.client = httpx.AsyncClient(timeout=30.0)
        self.is_connected = False
    
    async def login(self, username: str, password: str) -> bool:
        """登录 Alist"""
        try:
            logger.info(f"[AlistClient] 登录 {self.host} 用户={username}")
            resp = await self.client.post(
                f"{self.host}/api/auth/login",
                json={"username": username, "password": password}
            )
            data = resp.json()
            if data.get("code") == 200:
                self.token = data["data"]["token"]
                self.is_connected = True
                logger.info(f"[AlistClient] 登录成功")
                return True
            logger.warning(f"[AlistClient] 登录失败: code={data.get('code')}")
            return False
        except Exception as e:
            logger.error(f"[AlistClient] 登录异常: {e}", exc_info=True)
            return False
    
    def set_token(self, token: str):
        """设置 token"""
        self.token = token
        self.is_connected = True
    
    async def close(self):
        """关闭连接"""
        await self.client.aclose()
    
    async def list(self, path: str = "/", password: str = "", page: int = 1, per_page: int = 100) -> Dict[str, Any]:
        """列出目录文件"""
        if not self.token:
            logger.warning("[AlistClient] list 无token")
            return {"code": 401, "message": "未登录"}
        
        try:
            resp = await self.client.get(
                f"{self.host}/api/fs/list",
                params={"path": path, "password": password, "page": page, "per_page": per_page},
                headers={"Authorization": self.token}
            )
            data = resp.json()
            logger.info(f"[AlistClient] list path={path} code={data.get('code')}")
            return data
        except Exception as e:
            logger.error(f"[AlistClient] list 异常: {e}", exc_info=True)
            return {"code": 500, "message": str(e)}
    
    async def get(self, path: str, password: str = "") -> Dict[str, Any]:
        """获取文件/目录信息"""
        if not self.token:
            return {"code": 401, "message": "未登录"}
        
        try:
            resp = await self.client.post(
                f"{self.host}/api/fs/get",
                json={"path": path, "password": password},
                headers={"Authorization": self.token}
            )
            return resp.json()
        except Exception as e:
            return {"code": 500, "message": str(e)}
    
    async def mkdir(self, path: str) -> Dict[str, Any]:
        """创建目录"""
        if not self.token:
            return {"code": 401, "message": "未登录"}
        
        try:
            resp = await self.client.post(
                f"{self.host}/api/fs/mkdir",
                json={"path": path},
                headers={"Authorization": self.token}
            )
            return resp.json()
        except Exception as e:
            return {"code": 500, "message": str(e)}
    
    async def move(self, src_dir: str, dst_dir: str, names: List[str]) -> Dict[str, Any]:
        """移动文件"""
        if not self.token:
            return {"code": 401, "message": "未登录"}
        
        try:
            resp = await self.client.post(
                f"{self.host}/api/fs/move",
                json={
                    "src_dir": src_dir,
                    "dst_dir": dst_dir,
                    "names": names
                },
                headers={"Authorization": self.token}
            )
            return resp.json()
        except Exception as e:
            return {"code": 500, "message": str(e)}
    
    async def rename(self, path: str, name: str) -> Dict[str, Any]:
        """重命名"""
        if not self.token:
            return {"code": 401, "message": "未登录"}
        
        try:
            resp = await self.client.post(
                f"{self.host}/api/fs/rename",
                json={"path": path, "name": name},
                headers={"Authorization": self.token}
            )
            return resp.json()
        except Exception as e:
            return {"code": 500, "message": str(e)}
    
    async def delete(self, path: str) -> Dict[str, Any]:
        """删除文件"""
        if not self.token:
            return {"code": 401, "message": "未登录"}
        
        try:
            resp = await self.client.post(
                f"{self.host}/api/fs/delete",
                json={"path": path},
                headers={"Authorization": self.token}
            )
            return resp.json()
        except Exception as e:
            return {"code": 500, "message": str(e)}
    
    async def upload(self, path: str, file_path: str, password: str = "") -> Dict[str, Any]:
        """上传文件到 Alist"""
        if not self.token:
            logger.warning("[AlistClient] upload 无token")
            return {"code": 401, "message": "未登录"}
        
        try:
            logger.info(f"[AlistClient] upload {file_path} -> {path}")
            with open(file_path, 'rb') as f:
                files = {'file': (Path(file_path).name, f, 'application/octet-stream')}
                data = {'path': path, 'password': password}
                resp = await self.client.post(
                    f"{self.host}/api/fs/put",
                    data=data,
                    files=files,
                    headers={"Authorization": self.token}
                )
            result = resp.json()
            logger.info(f"[AlistClient] upload 结果: code={result.get('code')}")
            return result
        except Exception as e:
            logger.error(f"[AlistClient] upload 异常: {e}", exc_info=True)
            return {"code": 500, "message": str(e)}
    
    async def search(self, path: str, keyword: str, page: int = 1, per_page: int = 100) -> Dict[str, Any]:
        """搜索文件"""
        if not self.token:
            logger.warning("[AlistClient] search 无token")
            return {"code": 401, "message": "未登录"}
        
        try:
            logger.info(f"[AlistClient] search keyword={keyword} path={path}")
            resp = await self.client.post(
                f"{self.host}/api/fs/search",
                json={
                    "path": path,
                    "keyword": keyword,
                    "page": page,
                    "per_page": per_page,
                    "scope": 2  # 0=当前路径, 1=文件夹, 2=全部
                },
                headers={"Authorization": self.token}
            )
            data = resp.json()
            logger.info(f"[AlistClient] search 结果: code={data.get('code')}")
            return data
        except Exception as e:
            logger.error(f"[AlistClient] search 异常: {e}", exc_info=True)
            return {"code": 500, "message": str(e)}
    
    async def get_download_url(self, path: str) -> str:
        """获取下载链接"""
        if not self.token:
            logger.warning(f"[AlistClient] get_download_url 无token: {path}")
            return ""
        
        try:
            resp = await self.client.post(
                f"{self.host}/api/fs/link",
                json={"path": path},
                headers={"Authorization": self.token}
            )
            data = resp.json()
            if data.get("code") == 200:
                url = data["data"]["raw_url"]
                logger.info(f"[AlistClient] get_download_url: {path} -> {url[:60]}...")
                return url
            logger.warning(f"[AlistClient] get_download_url 失败: code={data.get('code')}")
            return ""
        except Exception as e:
            logger.error(f"[AlistClient] get_download_url 异常: {e}", exc_info=True)
            return ""


# 全局客户端实例
_alist_client: Optional[AlistClient] = None


def get_alist_client() -> AlistClient:
    """获取 Alist 客户端单例"""
    global _alist_client
    if _alist_client is None:
        _alist_client = AlistClient()
    return _alist_client


async def init_alist():
    """初始化 Alist 连接"""
    client = get_alist_client()
    # 从环境变量或配置文件读取
    token = os.getenv("ALIST_TOKEN", "")
    if token:
        client.set_token(token)
    return client
