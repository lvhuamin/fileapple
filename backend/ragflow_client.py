#!/usr/bin/env python3
"""
RAGFlow API 客户端
FileApple + RAGFlow 整合项目
"""

import os
import json
import httpx
import logging
from typing import Optional, List, Dict, Any
from pathlib import Path
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class RAGFlowConfig:
    """RAGFlow 配置"""
    base_url: str = "http://localhost:9380"
    api_key: str = ""
    timeout: float = 300.0

    @classmethod
    def from_env(cls):
        """从环境变量加载配置"""
        return cls(
            base_url=os.getenv("RAGFLOW_BASE_URL", "http://localhost:9380"),
            api_key=os.getenv("RAGFLOW_API_KEY", ""),
        )

    @classmethod
    def from_config_file(cls, path: str = "/root/lvhuamin/fileapple/data/ragflow-config.json"):
        """从配置文件加载"""
        config_path = Path(path)
        if config_path.exists():
            with open(config_path) as f:
                data = json.load(f)
                return cls(
                    base_url=data.get("ragflow_url", "http://localhost:9380"),
                    api_key=data.get("api_token", ""),
                )
        return cls.from_env()


class RAGFlowClient:
    """RAGFlow API 客户端"""

    # 知识库映射
    DATASET_MAPPING = {
        "技术运维": "tech-ops",
        "心理学": "psychology",
        "恋爱心理": "relationship",
        "文档": "documents",
        "有声剧": "audio-books",
        "其他": "general",
    }

    def __init__(self, config: Optional[RAGFlowConfig] = None):
        self.config = config or RAGFlowConfig.from_env()
        self.base_url = self.config.base_url.rstrip("/")
        self.api_version = "v1"  # RAGFlow API版本
        self.api_key = self.config.api_key
        self.client = httpx.AsyncClient(
            timeout=self.config.timeout,
            headers=self._get_headers()
        )
        self._dataset_ids: Dict[str, str] = {}

    def _get_headers(self) -> Dict[str, str]:
        """获取请求头"""
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        return headers

    def _get_dataset_id(self, name_or_id: str) -> str:
        """获取知识库ID（支持名称或ID）"""
        if name_or_id in self._dataset_ids:
            return self._dataset_ids[name_or_id]

        # 尝试通过API获取
        if name_or_id in self.DATASET_MAPPING:
            mapped = self.DATASET_MAPPING[name_or_id]
            return mapped

        return name_or_id

    # ========== 认证相关 ==========

    async def login(self, email: str, password: str) -> Dict[str, Any]:
        """用户登录"""
        try:
            logger.info(f"[RAGFlow] 登录 {self.base_url} email={email}")
            response = await self.client.post(
                f"{self.base_url}/api/v1/auth/login",
                json={"email": email, "password": password}
            )
            data = response.json()
            if data.get("code") == 0:
                token = data.get("data", {}).get("access_token")
                if token:
                    self.api_key = token
                    self.client.headers.update({"Authorization": f"Bearer {token}"})
                    logger.info("[RAGFlow] 登录成功")
            else:
                logger.warning(f"[RAGFlow] 登录失败: code={data.get('code')}")
            return data
        except Exception as e:
            logger.error(f"[RAGFlow] 登录异常: {e}", exc_info=True)
            return {"code": 1, "error": str(e)}

    async def get_token(self) -> Optional[str]:
        """获取当前 Token"""
        return self.api_key

    # ========== 知识库管理 ==========

    async def list_datasets(self) -> List[Dict[str, Any]]:
        """列出所有知识库"""
        try:
            response = await self.client.get(
                f"{self.base_url}/api/v1/datasets",
                headers=self._get_headers()
            )
            data = response.json()
            if data.get("code") == 0:
                datasets = data.get("data", [])
                logger.info(f"[RAGFlow] 列出 {len(datasets)} 个知识库")
                return datasets
            logger.warning(f"[RAGFlow] list_datasets 失败: code={data.get('code')}")
            return []
        except Exception as e:
            logger.error(f"[RAGFlow] list_datasets 异常: {e}", exc_info=True)
            return []

    async def create_dataset(
        self,
        name: str,
        description: str = "",
        language: str = "Chinese",
        permission: str = "me"
    ) -> Optional[str]:
        """创建知识库，返回知识库ID"""
        try:
            response = await self.client.post(
                f"{self.base_url}/api/v1/datasets",
                headers=self._get_headers(),
                json={
                    "name": name,
                    "description": description,
                    "permission": permission
                }
            )
            data = response.json()
            if data.get("code") == 0:
                dataset_id = data.get("data", {}).get("dataset_id")
                self._dataset_ids[name] = dataset_id
                return dataset_id
            return None
        except Exception as e:
            print(f"创建知识库失败: {e}")
            return None

    async def get_dataset(self, dataset_id: str) -> Optional[Dict[str, Any]]:
        """获取知识库详情"""
        try:
            response = await self.client.get(
                f"{self.base_url}/api/v1/datasets/{dataset_id}",
                headers=self._get_headers()
            )
            data = response.json()
            if data.get("code") == 0:
                return data.get("data")
            return None
        except Exception as e:
            print(f"获取知识库失败: {e}")
            return None

    async def delete_dataset(self, dataset_id: str) -> bool:
        """删除知识库"""
        try:
            response = await self.client.delete(
                f"{self.base_url}/api/v1/datasets",
                headers=self._get_headers(),
                json={"dataset_ids": [dataset_id]}
            )
            data = response.json()
            return data.get("code") == 0
        except Exception as e:
            print(f"删除知识库失败: {e}")
            return False

    # ========== 文档管理 ==========

    async def upload_document(
        self,
        dataset_id: str,
        file_path: str,
        chunk_size: int = 512,
        layout_recognize: bool = True
    ) -> Optional[str]:
        """上传文档到知识库，返回文档ID"""
        try:
            file_path = Path(file_path)
            if not file_path.exists():
                logger.warning(f"[RAGFlow] 文件不存在: {file_path}")
                return None
            logger.info(f"[RAGFlow] 上传文档 {file_path.name} -> dataset={dataset_id}")

            # 解析 dataset_id（可能是名称或别名，需要转为真实ID）
            real_id = self._get_dataset_id(dataset_id)

            # 构建 multipart form
            with open(file_path, 'rb') as f:
                files = {'file': (file_path.name, f.read(), 'application/octet-stream')}
                data = {
                    'chunk_size': str(chunk_size),
                    'layout_recognize': 'true' if layout_recognize else 'false'
                }

                # 使用非JSON请求
                headers = {"Authorization": f"Bearer {self.api_key}"} if self.api_key else {}
                response = await self.client.post(
                    f"{self.base_url}/api/v1/datasets/{real_id}/documents",
                    headers=headers,
                    files=files,
                    data=data
                )

            result = response.json()
            if result.get("code") == 0:
                doc_id = result.get("data", {}).get("document", {}).get("id")
                logger.info(f"[RAGFlow] 上传成功 doc_id={doc_id}")
                return doc_id
            logger.warning(f"[RAGFlow] 上传失败: code={result.get('code')}")
            return None
        except Exception as e:
            logger.error(f"[RAGFlow] 上传文档异常: {e}", exc_info=True)
            return None

    async def list_documents(self, dataset_id: str, page: int = 1, size: int = 50) -> List[Dict]:
        """列出知识库中的文档"""
        try:
            response = await self.client.get(
                f"{self.base_url}/api/v1/datasets/{dataset_id}/documents",
                params={"page": page, "size": size},
                headers=self._get_headers()
            )
            data = response.json()
            if data.get("code") == 0:
                return data.get("data", {}).get("docs", [])
            return []
        except Exception as e:
            print(f"列出文档失败: {e}")
            return []

    async def delete_documents(self, dataset_id: str, doc_ids: List[str]) -> bool:
        """删除文档"""
        try:
            response = await self.client.delete(
                f"{self.base_url}/api/v1/datasets/{dataset_id}/documents",
                headers=self._get_headers(),
                json={"document_ids": doc_ids}
            )
            data = response.json()
            return data.get("code") == 0
        except Exception as e:
            print(f"删除文档失败: {e}")
            return False

    # ========== 文档解析 ==========

    async def parse_document(self, dataset_id: str, doc_id: str) -> Dict:
        """触发文档解析"""
        try:
            response = await self.client.post(
                f"{self.base_url}/api/v1/datasets/{dataset_id}/documents/{doc_id}/parse",
                headers=self._get_headers()
            )
            return response.json()
        except Exception as e:
            print(f"解析文档失败: {e}")
            return {"code": 1, "error": str(e)}

    async def get_document_status(self, dataset_id: str, doc_id: str) -> Dict:
        """获取文档解析状态"""
        try:
            response = await self.client.get(
                f"{self.base_url}/api/v1/datasets/{dataset_id}/documents/{doc_id}",
                headers=self._get_headers()
            )
            data = response.json()
            if data.get("code") == 0:
                return data.get("data", {})
            return {}
        except Exception as e:
            print(f"获取状态失败: {e}")
            return {}

    async def wait_for_parsing(
        self,
        dataset_id: str,
        doc_id: str,
        max_wait: int = 600,
        interval: int = 5
    ) -> Dict:
        """等待文档解析完成"""
        import asyncio
        elapsed = 0

        while elapsed < max_wait:
            status = await self.get_document_status(dataset_id, doc_id)
            progress = status.get("progress", 0)
            doc_status = status.get("status", "")

            if doc_status == "completed":
                return {"success": True, "status": status}
            elif doc_status == "failed":
                return {"success": False, "error": "解析失败", "status": status}

            await asyncio.sleep(interval)
            elapsed += interval

        return {"success": False, "error": "解析超时"}

    # ========== 向量索引 ==========

    async def start_indexing(self, dataset_id: str) -> Dict:
        """启动向量索引构建"""
        try:
            response = await self.client.post(
                f"{self.base_url}/api/v1/datasets/{dataset_id}/index",
                headers=self._get_headers()
            )
            return response.json()
        except Exception as e:
            print(f"启动索引失败: {e}")
            return {"code": 1, "error": str(e)}

    async def get_index_status(self, dataset_id: str) -> Dict:
        """获取索引状态"""
        try:
            response = await self.client.get(
                f"{self.base_url}/api/v1/datasets/{dataset_id}/index",
                headers=self._get_headers()
            )
            return response.json()
        except Exception as e:
            print(f"获取索引状态失败: {e}")
            return {"code": 1, "error": str(e)}

    # ========== 检索和搜索 ==========

    async def search(
        self,
        query: str,
        dataset_ids: List[str] = None,
        top_k: int = 10,
        similarity_threshold: float = 0.5,
        vector_similarity_weight: float = 0.5
    ) -> List[Dict[str, Any]]:
        """语义搜索"""
        try:
            # 如果没有指定知识库，搜索所有
            if not dataset_ids:
                datasets = await self.list_datasets()
                dataset_ids = [d["id"] for d in datasets[:5]]  # 限制前5个

            logger.info(f"[RAGFlow] search query={query[:50]} datasets={len(dataset_ids)}")
            response = await self.client.post(
                f"{self.base_url}/api/v1/datasets/{dataset_ids[0]}/search",
                headers=self._get_headers(),
                json={
                    "query": query,
                    "top_k": top_k,
                    "similarity_threshold": similarity_threshold,
                    "vector_similarity_weight": vector_similarity_weight,
                    "rerank_model_disabled": True
                }
            )
            data = response.json()
            if data.get("code") == 0:
                results = data.get("data", [])
                logger.info(f"[RAGFlow] search 返回 {len(results)} 条结果")
                return results
            logger.warning(f"[RAGFlow] search 失败: code={data.get('code')}")
            return []
        except Exception as e:
            logger.error(f"[RAGFlow] search 异常: {e}", exc_info=True)
            return []

    async def retrieval(
        self,
        query: str,
        dataset_id: str,
        top_k: int = 10
    ) -> List[Dict[str, Any]]:
        """在指定知识库中检索"""
        try:
            response = await self.client.post(
                f"{self.base_url}/api/v1/datasets/{dataset_id}/retrieval",
                headers=self._get_headers(),
                json={
                    "query": query,
                    "top_k": top_k
                }
            )
            data = response.json()
            if data.get("code") == 0:
                return data.get("data", [])
            return []
        except Exception as e:
            print(f"检索失败: {e}")
            return []

    # ========== RAG 对话 ==========

    async def create_chat(
        self,
        dataset_id: str,
        name: str = "FileApple Chat",
        top_n: int = 3
    ) -> Optional[str]:
        """创建聊天助手"""
        try:
            response = await self.client.post(
                f"{self.base_url}/api/v1/chats",
                headers=self._get_headers(),
                json={
                    "dataset_ids": [dataset_id] if isinstance(dataset_id, str) else dataset_id,
                    "name": name,
                    "top_n": top_n
                }
            )
            data = response.json()
            if data.get("code") == 0:
                return data.get("data", {}).get("id")
            return None
        except Exception as e:
            print(f"创建聊天失败: {e}")
            return None

    async def chat_completion(
        self,
        question: str,
        dataset_id: str = None,
        chat_id: str = None,
        history: List[Dict[str, str]] = None
    ) -> Dict[str, Any]:
        """RAG 对话完成"""
        try:
            payload = {
                "question": question,
                "stream": False
            }

            # 支持传入对话历史（RAGFlow API 支持 param_type=context 或作为 messages）
            if history:
                # 转换为 RAGFlow 期望的格式
                payload["history"] = [{"role": h["role"], "content": h["content"]} for h in history]

            if dataset_id and not chat_id:
                payload["dataset_ids"] = [dataset_id]

            endpoint = f"{self.base_url}/api/v1/chat/completions"
            if chat_id:
                endpoint = f"{self.base_url}/api/v1/chats/{chat_id}/chat/completions"

            response = await self.client.post(
                endpoint,
                headers=self._get_headers(),
                json=payload
            )
            return response.json()
        except Exception as e:
            print(f"对话失败: {e}")
            return {"error": str(e)}

    # ========== 工具方法 ==========

    async def health_check(self) -> bool:
        """健康检查"""
        try:
            response = await self.client.get(f"{self.base_url}/api/v1/system/ping")
            ok = response.text.strip() == "pong"
            logger.info(f"[RAGFlow] health_check {'OK' if ok else 'FAIL'}: {self.base_url}")
            return ok
        except Exception as e:
            logger.warning(f"[RAGFlow] health_check 异常: {e}")
            return False

    async def get_version(self) -> str:
        """获取版本"""
        try:
            response = await self.client.get(f"{self.base_url}/api/v1/system/version")
            data = response.json()
            # 版本 API 返回 {"code": 0, "data": "v0.25.6"}
            if isinstance(data.get("data"), str):
                return data.get("data", "unknown")
            return data.get("data", {}).get("version", "unknown")
        except Exception:
            return "unknown"

    async def close(self):
        """关闭客户端"""
        await self.client.aclose()

    # ========== 批量导入 ==========

    async def import_file(
        self,
        file_path: str,
        dataset_name: str,
        wait_completed: bool = True,
        max_wait: int = 600
    ) -> Dict[str, Any]:
        """导入文件到知识库（完整流程）

        Args:
            file_path: 文件路径
            dataset_name: 知识库名称或ID
            wait_completed: 是否等待解析完成
            max_wait: 最大等待秒数

        Returns:
            包含 doc_id, status 等信息
        """
        dataset_id = self._get_dataset_id(dataset_name)
        logger.info(f"[RAGFlow] import_file {file_path} -> dataset={dataset_name}(id={dataset_id})")

        # 1. 上传文档
        doc_id = await self.upload_document(dataset_id, file_path)
        if not doc_id:
            return {"success": False, "error": "上传失败"}

        # 2. 触发解析
        await self.parse_document(dataset_id, doc_id)

        # 3. 等待解析完成
        if wait_completed:
            result = await self.wait_for_parsing(dataset_id, doc_id, max_wait)
            result["doc_id"] = doc_id
            result["dataset_id"] = dataset_id
            return result

        return {
            "success": True,
            "doc_id": doc_id,
            "dataset_id": dataset_id,
            "status": "parsing"
        }

    async def batch_import(
        self,
        files: List[str],
        dataset_name: str,
        callback=None
    ) -> List[Dict[str, Any]]:
        """批量导入文件"""
        results = []
        for i, file_path in enumerate(files):
            result = await self.import_file(file_path, dataset_name, wait_completed=False)
            result["index"] = i
            results.append(result)

            if callback:
                callback(i, len(files), file_path)

        return results


# ========== 单例模式 ==========

_client: Optional[RAGFlowClient] = None


def get_ragflow_client() -> RAGFlowClient:
    """获取 RAGFlow 客户端单例"""
    global _client
    if _client is None:
        _client = RAGFlowClient()
    return _client


# ========== 主函数（测试用） ==========

if __name__ == "__main__":
    import asyncio

    async def test():
        client = RAGFlowClient()

        # 健康检查
        print(f"RAGFlow 健康检查: {await client.health_check()}")

        # 列出知识库
        datasets = await client.list_datasets()
        print(f"知识库列表: {len(datasets)} 个")

        for ds in datasets[:5]:
            print(f"  - {ds.get('name')}: {ds.get('id')}")

        await client.close()

    asyncio.run(test())
