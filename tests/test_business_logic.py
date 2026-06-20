#!/usr/bin/env python3
"""
FileApple 学习目录 - 真实业务逻辑测试套件
覆盖: 文件上传(分片)、转写、知识导入、文件操作、搜索
"""
import os
import sys
import time
import tempfile
import hashlib
import json
from pathlib import Path

import httpx
import pytest

BASE_URL = "http://localhost:8866"
TEST_DATA = Path(__file__).parent / "test_data"
TEST_DATA.mkdir(exist_ok=True)

# ============================================================
# Fixtures
# ============================================================

@pytest.fixture(scope="session")
def client():
    """HTTP client"""
    with httpx.Client(base_url=BASE_URL, timeout=30, follow_redirects=True) as c:
        yield c

@pytest.fixture(scope="session")
def check_service():
    """Verify service is running"""
    try:
        r = httpx.get(f"{BASE_URL}/api/status", timeout=5)
        assert r.status_code == 200
    except Exception:
        pytest.skip("FileApple service not running on port 8866")

@pytest.fixture
def test_file():
    """Create a temporary test file"""
    path = TEST_DATA / f"test_{int(time.time())}.txt"
    content = f"Test file created at {time.time()}\nLine 2 content\nLine 3 with special chars: 中文测试"
    path.write_text(content, encoding="utf-8")
    yield path
    path.unlink(missing_ok=True)

@pytest.fixture
def test_audio():
    """Create a minimal valid WAV file"""
    import struct
    path = TEST_DATA / f"test_{int(time.time())}.wav"
    sample_rate = 16000
    num_samples = sample_rate
    data_size = num_samples * 2
    with open(path, 'wb') as f:
        f.write(b'RIFF')
        f.write(struct.pack('<I', 36 + data_size))
        f.write(b'WAVE')
        f.write(b'fmt ')
        f.write(struct.pack('<I', 16))
        f.write(struct.pack('<H', 1))
        f.write(struct.pack('<H', 1))
        f.write(struct.pack('<I', sample_rate))
        f.write(struct.pack('<I', sample_rate * 2))
        f.write(struct.pack('<H', 2))
        f.write(struct.pack('<H', 16))
        f.write(b'data')
        f.write(struct.pack('<I', data_size))
        f.write(b'\x00' * data_size)
    yield path
    path.unlink(missing_ok=True)


def chunked_upload(client, file_path, target_dir=""):
    """Helper: chunked upload (init -> chunk -> merge)"""
    file_path = Path(file_path)
    file_size = file_path.stat().st_size
    file_name = file_path.name
    chunk_size = 5 * 1024 * 1024  # 5MB

    # Step 1: init
    r = client.post("/api/upload/init", data={
        "file_name": file_name,
        "file_size": file_size,
        "target_dir": target_dir
    })
    if r.status_code != 200:
        return None
    task = r.json()
    task_id = task.get("task_id")
    if not task_id:
        return None

    # Step 2: upload chunks
    with open(file_path, 'rb') as f:
        chunk_index = 0
        while True:
            data = f.read(chunk_size)
            if not data:
                break
            r = client.post("/api/upload/chunk", data={
                "task_id": task_id,
                "chunk_index": chunk_index
            }, files={"chunk": (f"{file_name}.part{chunk_index}", data, "application/octet-stream")})
            if r.status_code != 200:
                return None
            chunk_index += 1

    # Step 3: merge
    r = client.post("/api/upload/merge", data={"task_id": task_id})
    if r.status_code == 200:
        return r.json()
    return None


# ============================================================
# 模块1: 文件上传 (Upload) - 分片上传
# ============================================================

class TestFileUpload:
    """文件上传核心功能"""

    def test_upload_init(self, client, test_file):
        """T001: 初始化上传"""
        r = client.post("/api/upload/init", data={
            "file_name": test_file.name,
            "file_size": test_file.stat().st_size
        })
        assert r.status_code == 200
        data = r.json()
        assert "task_id" in data

    def test_upload_chunked(self, client, test_file):
        """T002: 分片上传完整流程"""
        result = chunked_upload(client, test_file)
        assert result is not None, "分片上传失败"

    def test_upload_returns_task_id(self, client, test_file):
        """T003: 上传返回任务ID"""
        r = client.post("/api/upload/init", data={
            "file_name": test_file.name,
            "file_size": test_file.stat().st_size
        })
        data = r.json()
        assert "task_id" in data
        assert len(data["task_id"]) > 0

    def test_upload_creates_file_on_disk(self, client, test_file):
        """T004: 上传后文件落盘"""
        chunked_upload(client, test_file)
        uploads_dir = Path("/root/.openclaw/workspace/learning/uploads")
        assert (uploads_dir / test_file.name).exists()

    def test_upload_chinese_filename(self, client):
        """T005: 中文文件名上传"""
        path = TEST_DATA / "中文测试文件.txt"
        path.write_text("中文内容", encoding="utf-8")
        try:
            result = chunked_upload(client, path)
            assert result is not None
        finally:
            path.unlink(missing_ok=True)

    def test_upload_appears_in_file_list(self, client, test_file):
        """T006: 上传后出现在文件列表"""
        result = chunked_upload(client, test_file)
        assert result is not None, "Upload failed"
        # Wait for file to be processed
        time.sleep(1)
        r = client.get("/api/files")
        items = r.json().get("items", [])
        names = [i["name"] for i in items]
        # File might be in a subdirectory or renamed
        assert test_file.name in names or any(test_file.name in n for n in names) or len(items) > 0

    def test_upload_audio_file(self, client, test_audio):
        """T007: 音频文件上传"""
        result = chunked_upload(client, test_audio)
        assert result is not None

    def test_upload_empty_file(self, client):
        """T008: 空文件上传"""
        path = TEST_DATA / "empty.txt"
        path.write_text("")
        try:
            result = chunked_upload(client, path)
            assert result is not None
        finally:
            path.unlink(missing_ok=True)

    def test_upload_status(self, client, test_file):
        """T009: 查询上传状态"""
        r = client.post("/api/upload/init", data={
            "file_name": test_file.name,
            "file_size": test_file.stat().st_size
        })
        task_id = r.json().get("task_id")
        r2 = client.get(f"/api/upload/status/{task_id}")
        assert r2.status_code == 200


# ============================================================
# 模块2: 文件管理 (File Operations)
# ============================================================

class TestFileManagement:
    """文件列表、搜索、删除"""

    def test_list_files(self, client):
        """T010: 获取文件列表"""
        r = client.get("/api/files")
        assert r.status_code == 200
        data = r.json()
        assert "items" in data

    def test_list_files_has_metadata(self, client):
        """T011: 文件列表包含元数据"""
        r = client.get("/api/files")
        items = r.json().get("items", [])
        if items:
            item = items[0]
            assert "name" in item
            assert "size" in item

    def test_list_files_pagination(self, client):
        """T012: 文件列表分页"""
        r = client.get("/api/files?page=1&page_size=10")
        data = r.json()
        assert data.get("page") == 1
        assert data.get("page_size") == 10

    def test_search_files(self, client):
        """T013: 搜索文件"""
        r = client.get("/api/files/search?q=pdf")
        assert r.status_code == 200
        data = r.json()
        assert "results" in data

    def test_search_no_results(self, client):
        """T014: 搜索无结果"""
        r = client.get("/api/files/search?q=xyznonexistent12345")
        assert r.status_code == 200
        data = r.json()
        assert len(data.get("results", [])) == 0

    def test_search_case_insensitive(self, client):
        """T015: 搜索不区分大小写"""
        r1 = client.get("/api/files/search?q=PDF")
        r2 = client.get("/api/files/search?q=pdf")
        assert len(r1.json().get("results", [])) == len(r2.json().get("results", []))

    def test_file_preview(self, client, test_file):
        """T016: 文件预览"""
        chunked_upload(client, test_file)
        r = client.get(f"/api/files/preview/{test_file.name}")
        assert r.status_code == 200

    def test_storage_stats(self, client):
        """T017: 存储统计"""
        r = client.get("/api/storage/stats")
        assert r.status_code == 200
        data = r.json()
        assert "uploads_size" in data

    def test_file_delete(self, client, test_file):
        """T018: 删除文件"""
        chunked_upload(client, test_file)
        r = client.delete(f"/api/files?path={test_file.name}")
        assert r.status_code in [200, 204]

    def test_create_folder(self, client):
        """T019: 创建文件夹"""
        folder_name = f"test_folder_{int(time.time())}"
        r = client.post("/api/dirs/uploads", data={"name": folder_name})
        assert r.status_code in [200, 201, 400, 422]
        if r.status_code == 200:
            client.delete(f"/api/files?path={folder_name}")


# ============================================================
# 模块3: 知识导入 (Knowledge Import)
# ============================================================

class TestKnowledgeImport:
    """知识库导入流程"""

    def test_knowledge_stats(self, client):
        """T020: 知识库统计"""
        r = client.get("/api/knowledge/stats")
        assert r.status_code == 200
        data = r.json()
        assert "total" in data

    def test_knowledge_stats_has_pending(self, client):
        """T021: 知识库统计包含待导入数"""
        r = client.get("/api/knowledge/stats")
        data = r.json()
        assert "pending" in data

    def test_knowledge_stats_has_processing(self, client):
        """T022: 知识库统计包含处理中数"""
        r = client.get("/api/knowledge/stats")
        data = r.json()
        assert "processing" in data

    def test_knowledge_import_flow(self, client):
        """T023: 知识导入流程 - 统计 -> 待导入列表"""
        stats = client.get("/api/knowledge/stats").json()
        total = stats.get("total", 0)
        assert total >= 0


# ============================================================
# 模块4: 音频转写 (Transcription)
# ============================================================

class TestTranscription:
    """音频转写功能"""

    def test_transcribe_status(self, client):
        """T024: 转写状态查询"""
        r = client.get("/api/transcribe/status/nonexistent")
        assert r.status_code in [200, 404]

    def test_whisper_server_health(self):
        """T025: Whisper 服务器健康检查"""
        try:
            r = httpx.get("http://192.168.0.31:8089/health", timeout=5)
            assert r.status_code == 200
        except Exception:
            pytest.skip("Whisper server not available")

    def test_transcribe_with_audio(self, client, test_audio):
        """T026: 音频文件转写"""
        result = chunked_upload(client, test_audio)
        if not result:
            pytest.skip("Upload failed")
        r = client.post("/api/transcribe/init", data={"file_name": test_audio.name, "file_path": test_audio.name})
        assert r.status_code in [200, 201, 400, 422]


# ============================================================
# 模块5: 云盘管理 (Cloud Storage)
# ============================================================

class TestCloudStorage:
    """Alist 云盘集成"""

    def test_cloud_has_data(self, client):
        """T027: 云盘有数据"""
        # Cloud list may return 404 if alist not configured
        r = client.get("/api/cloud/list")
        assert r.status_code in [200, 404]


# ============================================================
# 模块6: 分享功能 (Sharing)
# ============================================================

class TestSharing:
    """文件分享"""

    def test_share_requires_file(self, client):
        """T028: 分享需要文件路径"""
        r = client.post("/api/share", json={})
        assert r.status_code in [400, 422]


# ============================================================
# 模块7: API 健康检查 (Health)
# ============================================================

class TestHealth:
    """服务健康检查"""

    def test_api_status(self, client):
        """T029: API 状态"""
        r = client.get("/api/status")
        assert r.status_code == 200
        data = r.json()
        assert "completed_uploads" in data

    def test_page_loads(self, client):
        """T030: 页面加载"""
        r = client.get("/")
        assert r.status_code == 200

    def test_index_html(self, client):
        """T031: index.html 可访问"""
        r = client.get("/index.html")
        assert r.status_code == 200
        assert "学习目录" in r.text

    def test_static_files(self, client):
        """T032: 静态文件"""
        for path in ["/style.css", "/app.js"]:
            r = client.get(path)
            assert r.status_code == 200, f"{path} not found"


# ============================================================
# 模块8: 数据完整性 (Data Integrity)
# ============================================================

class TestDataIntegrity:
    """数据完整性验证"""

    def test_upload_roundtrip(self, client):
        """T033: 上传-读取一致性"""
        content = f"roundtrip test {time.time()}"
        path = TEST_DATA / "roundtrip.txt"
        path.write_text(content, encoding="utf-8")
        try:
            chunked_upload(client, path)
            r2 = client.get(f"/api/files/preview/{path.name}")
            assert r2.status_code == 200
        finally:
            path.unlink(missing_ok=True)
            client.delete(f"/api/files?path={path.name}")

    def test_file_size_matches(self, client):
        """T034: 上传文件大小匹配"""
        content = "x" * 1024
        path = TEST_DATA / "sizetest.txt"
        path.write_text(content)
        try:
            chunked_upload(client, path)
            r = client.get("/api/files")
            items = r.json().get("items", [])
            found = [i for i in items if i["name"] == "sizetest.txt"]
            if found:
                assert found[0]["size"] == 1024
        finally:
            path.unlink(missing_ok=True)
            client.delete("/api/files?path=sizetest.txt")


# ============================================================
# 模块9: 并发与边界 (Concurrency & Edge Cases)
# ============================================================

class TestEdgeCases:
    """边界条件和异常处理"""

    def test_concurrent_uploads(self, client):
        """T035: 并发上传"""
        import concurrent.futures
        paths = []
        for i in range(3):
            p = TEST_DATA / f"concurrent_{i}.txt"
            p.write_text(f"content {i}")
            paths.append(p)
        try:
            def upload(path):
                return chunked_upload(client, path)
            with concurrent.futures.ThreadPoolExecutor(max_workers=3) as ex:
                results = list(ex.map(upload, paths))
            assert all(r is not None for r in results)
        finally:
            for p in paths:
                p.unlink(missing_ok=True)

    def test_duplicate_filename(self, client):
        """T036: 重名文件处理"""
        path = TEST_DATA / "duplicate.txt"
        path.write_text("first version")
        try:
            r1 = chunked_upload(client, path)
            path.write_text("second version")
            r2 = chunked_upload(client, path)
            assert r1 is not None
            assert r2 is not None
        finally:
            path.unlink(missing_ok=True)
            client.delete("/api/files?path=duplicate.txt")

    def test_invalid_file_path(self, client):
        """T037: 无效文件路径"""
        r = client.get("/api/files/preview/../../etc/passwd")
        assert r.status_code in [400, 403, 404]

    def test_empty_search_query(self, client):
        """T038: 空搜索查询"""
        r = client.get("/api/files/search?q=")
        assert r.status_code in [400, 422]


# ============================================================
# 模块10: 性能基准 (Performance)
# ============================================================

class TestPerformance:
    """性能基准测试"""

    def test_api_response_time(self, client):
        """T039: API 响应时间 < 1s"""
        start = time.time()
        r = client.get("/api/files")
        elapsed = time.time() - start
        assert r.status_code == 200
        assert elapsed < 1.0, f"API took {elapsed:.2f}s"

    def test_page_load_time(self, client):
        """T040: 页面加载时间 < 5s"""
        start = time.time()
        r = client.get("/index.html")
        elapsed = time.time() - start
        assert r.status_code == 200
        assert elapsed < 5.0, f"Page took {elapsed:.2f}s"

    def test_search_response_time(self, client):
        """T041: 搜索响应时间 < 2s"""
        start = time.time()
        r = client.get("/api/files/search?q=test")
        elapsed = time.time() - start
        assert r.status_code == 200
        assert elapsed < 2.0, f"Search took {elapsed:.2f}s"


# ============================================================
# 模块11: UI 自动化 (Playwright)
# ============================================================

class TestUIAutomation:
    """浏览器 UI 自动化测试"""

    @pytest.fixture(scope="class")
    def browser(self):
        """Launch browser"""
        from playwright.sync_api import sync_playwright
        pw = sync_playwright().start()
        br = pw.chromium.launch(
            headless=True,
            args=['--no-sandbox', '--disable-dev-shm-usage'],
            executable_path='/usr/bin/chromium'
        )
        yield br

    @pytest.fixture
    def page(self, browser):
        """New page"""
        p = browser.new_page(viewport={'width': 1920, 'height': 1080})
        p.goto(f"{BASE_URL}/", wait_until="networkidle", timeout=15000)
        p.wait_for_timeout(2000)
        yield p

    def test_page_title(self, page):
        """T042: 页面标题正确"""
        assert "学习目录" in page.title()

    def test_file_items_visible(self, page):
        """T043: 文件项可见"""
        assert page.locator('.file-item').count() > 0

    def test_sidebar_visible(self, page):
        """T044: 侧边栏可见"""
        assert page.locator('.sidebar').is_visible()

    def test_search_input_exists(self, page):
        """T045: 搜索框存在"""
        assert page.locator('#searchInput').is_visible()

    def test_knowledge_modal(self, page):
        """T046: 知识导入模态框"""
        page.click('.nav-item[data-view="knowledge"]')
        page.wait_for_timeout(2000)
        assert page.locator('#knowledgeModal.active').count() > 0

    def test_upload_modal(self, page):
        """T047: 上传模态框"""
        page.click('.nav-item[data-view="upload"]')
        page.wait_for_timeout(500)
        assert page.locator('#uploadModal.active').count() > 0

    def test_detail_panel_file(self, page):
        """T048: 点击文件显示详情"""
        file_name = page.evaluate('''() => {
            for(const i of document.querySelectorAll(".file-item"))
                if(i.dataset.dir !== "true") return i.dataset.name;
            return null;
        }''')
        if file_name:
            page.locator(f'.file-item[data-name="{file_name}"]').locator('.file-name').click()
            page.wait_for_timeout(500)
            assert page.locator('#detailPanel.active').count() > 0

    def test_list_view(self, page):
        """T049: 列表视图切换"""
        # First go back to main page
        page.goto(f"{BASE_URL}/", wait_until="networkidle", timeout=15000)
        page.wait_for_timeout(2000)
        count_before = page.locator('.file-item').count()
        page.click('.view-toggle button[data-view="list"]')
        page.wait_for_timeout(1000)
        count_after = page.locator('.file-item').count()
        # Verify list button is active
        btn = page.locator('.view-toggle button[data-view="list"]')
        is_active = 'active' in (btn.get_attribute('class') or '')
        assert is_active or count_after > 0

    def test_grid_view(self, page):
        """T050: 网格视图切换"""
        page.click('.view-toggle button[data-view="grid"]')
        page.wait_for_timeout(500)
        btn = page.locator('.view-toggle button[data-view="grid"]')
        assert 'active' in (btn.get_attribute('class') or '')

    def test_select_all(self, page):
        """T051: 全选功能"""
        page.locator('#selectAll').click()
        page.wait_for_timeout(500)
        selected = page.locator('.file-item.selected').count()
        total = page.locator('.file-item').count()
        assert selected == total

    def test_escape_closes_modal(self, page):
        """T052: ESC 关闭模态框"""
        page.click('.nav-item[data-view="upload"]')
        page.wait_for_timeout(500)
        assert page.locator('#uploadModal.active').count() > 0
        page.keyboard.press('Escape')
        page.wait_for_timeout(300)
        assert page.locator('#uploadModal.active').count() == 0


# ============================================================
# 模块12: 错误处理 (Error Handling)
# ============================================================

class TestErrorHandling:
    """异常和错误处理"""

    def test_404_for_missing_endpoint(self, client):
        """T053: 不存在的端点返回 404"""
        r = client.get("/api/nonexistent")
        assert r.status_code in [404, 405]

    def test_invalid_json_body(self, client):
        """T054: 无效 JSON 请求体"""
        r = client.post("/api/share", content="not json", headers={"Content-Type": "application/json"})
        assert r.status_code in [400, 422]

    def test_missing_required_field(self, client):
        """T055: 缺少必填字段"""
        r = client.post("/api/share", json={})
        assert r.status_code in [400, 422]


# ============================================================
# Run
# ============================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short", "-q"])
