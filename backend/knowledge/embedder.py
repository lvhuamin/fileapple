"""
向量引擎 — 远程 bge-m3 embedding API
向 167 服务器上的 embed API 服务发送 HTTP 请求，而非本地加载模型。
"""
import json
import logging
import urllib.request
import urllib.error
from typing import List, Optional
from pathlib import Path

logger = logging.getLogger("ingestion.embedder")

DEFAULT_EMBED_API_URL = "http://192.168.0.100:11436/v1/embeddings"


class Embedder:
    """远程 bge-m3 Embedding 引擎 — HTTP 请求到 167 embed API 服务"""

    def __init__(self, api_url: str = DEFAULT_EMBED_API_URL, model_name: str = "BAAI/bge-m3",
                 device: str = "cpu", batch_size: int = 16):
        self.api_url = api_url
        self.model_name = model_name
        # device / batch_size 保留接口兼容但不由本地控制

    def encode(self, texts: List[str]) -> Optional[List[List[float]]]:
        """通过远程 API 生成 embedding 向量，返回 [[float], ...]"""
        if not texts:
            return None

        try:
            payload = json.dumps({
                "model": "bge-m3",
                "input": texts,
            }).encode("utf-8")

            req = urllib.request.Request(
                self.api_url,
                data=payload,
                headers={"Content-Type": "application/json"},
                method="POST",
            )

            with urllib.request.urlopen(req, timeout=120) as resp:
                result = json.loads(resp.read().decode("utf-8"))

            if "data" not in result:
                logger.error("embed API unexpected response: %s", result)
                return None

            # data 按 index 排序
            data = sorted(result["data"], key=lambda x: x["index"])
            embeddings = [d["embedding"] for d in data]
            logger.debug("embed remote: %d texts → %d-dim", len(texts), len(embeddings[0]) if embeddings else 0)
            return embeddings

        except urllib.error.HTTPError as e:
            logger.error("embed API HTTP error [%d]: %s", e.code, e.read().decode())
            return None
        except Exception as e:
            logger.error("embedding failed: %s", e)
            return None


class DedupCache:
    """基于 bge-m3 的本地去重缓存

    存储已处理文件的摘要 embedding，写入 OpenViking 前比对相似度。
    相似度 > threshold 视为重复，跳过写入。

    数据存于 JSONL 文件，每条:
      {"source": "xxx", "summary": "...", "embedding": [0.xx, ...]}
    """

    def __init__(self, cache_path: str = "/root/knowledge-ingestion/data/processed_embeddings.jsonl"):
        self.cache_path = Path(cache_path)
        self.cache_path.parent.mkdir(parents=True, exist_ok=True)
        self._records: List[dict] = []
        self._load()

    def _load(self):
        if self.cache_path.exists():
            with open(self.cache_path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line:
                        self._records.append(json.loads(line))
            logger.info("DedupCache loaded: %d records", len(self._records))

    def _save(self, record: dict):
        with open(self.cache_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
        self._records.append(record)

    def is_duplicate(self, embedding: List[float], threshold: float = 0.92) -> bool:
        """检查是否与已有记录相似（cosine similarity > threshold）"""
        import math
        for prev in self._records:
            prev_emb = prev.get("embedding")
            if not prev_emb:
                continue
            sim = self._cosine_similarity(embedding, prev_emb)
            if sim > threshold:
                logger.debug("Dedup match: sim=%.4f > %.2f, prev='%s'",
                             sim, threshold, prev.get("summary", "")[:60])
                return True
        return False

    def add(self, source: str, summary: str, embedding: List[float]):
        """添加一条处理记录"""
        record = {"source": source, "summary": summary, "embedding": embedding}
        self._save(record)
        logger.info("DedupCache add: %s", source)

    @staticmethod
    def _cosine_similarity(a: List[float], b: List[float]) -> float:
        import math
        dot = sum(x * y for x, y in zip(a, b))
        na = math.sqrt(sum(x * x for x in a))
        nb = math.sqrt(sum(x * x for x in b))
        if na == 0 or nb == 0:
            return 0.0
        return dot / (na * nb)

    @property
    def count(self) -> int:
        return len(self._records)


# 全局单例
_inst: Embedder | None = None
_cache_inst: DedupCache | None = None


def get_embedder(model_name: str = "BAAI/bge-m3", device: str = "cpu",
                 batch_size: int = 16,
                 api_url: str = DEFAULT_EMBED_API_URL) -> Embedder:
    global _inst
    if _inst is None:
        _inst = Embedder(api_url=api_url, model_name=model_name, device=device, batch_size=batch_size)
    return _inst


def get_dedup_cache(cache_path: str = "/root/knowledge-ingestion/data/processed_embeddings.jsonl") -> DedupCache:
    global _cache_inst
    if _cache_inst is None:
        _cache_inst = DedupCache(cache_path)
    return _cache_inst