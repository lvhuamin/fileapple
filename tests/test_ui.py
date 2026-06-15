#!/usr/bin/env python3
"""
8866学习目录系统 - 全功能Playwright UI自动化测试
运行: python3 tests/test_ui.py
"""

import os
import sys
import time
import json
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Optional

# 确保无 asyncio 冲突
os.environ.pop("PYTEST_CURRENT_TEST", None)

import httpx
from playwright.sync_api import sync_playwright, Page, Browser


# ========== 配置 ==========

BASE_URL = "http://localhost:8866"
TEST_TIMEOUT = 30000
SCREENSHOT_DIR = Path(__file__).parent / "screenshots"
REPORT_DIR = Path(__file__).parent / "reports"


# ========== 测试基类 ==========

class TestBase:
    """测试基类"""

    playwright: Optional[sync_playwright] = None
    browser: Optional[Browser] = None
    page: Optional[Page] = None
    context = None

    @classmethod
    def setup_class(cls):
        """类初始化"""
        cls.screenshot_dir = SCREENSHOT_DIR
        cls.screenshot_dir.mkdir(exist_ok=True)
        cls.report_dir = REPORT_DIR
        cls.report_dir.mkdir(exist_ok=True)

        # 验证服务
        try:
            resp = httpx.get(f"{BASE_URL}/api/files", timeout=5)
            assert resp.status_code == 200
            print(f"\n✅ 服务正常: {BASE_URL}")
        except Exception as e:
            print(f"\n❌ 服务连接失败: {e}")
            sys.exit(1)

    @classmethod
    def teardown_class(cls):
        """类清理"""
        pass

    def setup_method(self):
        """方法初始化"""
        self._init_browser()

    def teardown_method(self):
        """方法清理"""
        self._cleanup()

    def _init_browser(self):
        """初始化浏览器"""
        self.playwright = sync_playwright().start()
        self.browser = self.playwright.chromium.launch(
            headless=True,
            args=['--no-sandbox', '--disable-dev-shm-usage', '--disable-gpu'],
            executable_path='/usr/bin/chromium'
        )
        self.context = self.browser.new_context(
            viewport={'width': 1920, 'height': 1080},
            locale='zh-CN'
        )
        self.page = self.context.new_page()
        self.page.set_default_timeout(TEST_TIMEOUT)

    def _cleanup(self):
        """清理资源"""
        try:
            if self.page and not self.page.is_closed():
                self.page.close()
        except:
            pass
        try:
            if self.context:
                self.context.close()
        except:
            pass
        try:
            if self.browser:
                self.browser.close()
        except:
            pass
        try:
            if self.playwright:
                self.playwright.stop()
        except:
            pass

    def _goto(self, path: str = "/"):
        """访问页面"""
        self.page.goto(f"{BASE_URL}{path}", wait_until="domcontentloaded")
        self._wait_for_load()

    def _wait_for_load(self, timeout: int = 10000):
        """等待加载"""
        try:
            self.page.wait_for_load_state("networkidle", timeout=timeout)
        except:
            pass

    def _screenshot(self, name: str, full_page: bool = True) -> Path:
        """截图"""
        ts = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        path = self.screenshot_dir / f"{name}_{ts}.png"
        self.page.screenshot(path=str(path), full_page=full_page)
        print(f"  📸 {path.name}")
        return path

    def _wait_for_selector(self, selector: str, timeout: int = 10000):
        """等待元素"""
        self.page.wait_for_selector(selector, timeout=timeout)

    def _click(self, selector: str):
        """点击"""
        self.page.locator(selector).click()

    def _fill(self, selector: str, value: str):
        """填写"""
        self.page.locator(selector).fill(value)

    def _is_visible(self, selector: str) -> bool:
        """元素可见"""
        return self.page.locator(selector).is_visible()

    def _get_text(self, selector: str) -> str:
        """获取文本"""
        loc = self.page.locator(selector)
        if loc.count() > 1:
            return " ".join(loc.all_text_contents())
        return loc.text_content()

    def _count(self, selector: str) -> int:
        """计数"""
        return self.page.locator(selector).count()


# ========== 测试用例 ==========

class TestPageBasics(TestBase):
    """页面基础测试"""

    def test_01_page_title_and_meta(self):
        """测试页面标题和元信息"""
        self._goto()
        title = self.page.title()
        assert "学习目录" in title, f"标题不正确: {title}"

    def test_02_page_structure(self):
        """测试页面结构完整性"""
        self._goto()
        assert self._is_visible(".app-container"), "主容器缺失"
        assert self._is_visible(".sidebar"), "侧边栏缺失"
        assert self._is_visible(".main-content"), "主内容区缺失"

    def test_03_sidebar_structure(self):
        """测试侧边栏结构"""
        self._goto()
        assert self._is_visible(".sidebar-header"), "侧边栏头部缺失"
        assert self._is_visible(".logo"), "Logo缺失"
        assert self._is_visible(".sidebar-nav"), "导航缺失"

    def test_04_topbar_structure(self):
        """测试顶部栏结构"""
        self._goto()
        assert self._is_visible(".topbar"), "顶部栏缺失"
        assert self._is_visible("#currentPath"), "路径显示缺失"
        assert self._is_visible("#btnUpload"), "上传按钮缺失"

    def test_05_content_area_structure(self):
        """测试内容区结构"""
        self._goto()
        assert self._is_visible(".breadcrumb"), "面包屑缺失"
        assert self._is_visible(".toolbar"), "工具栏缺失"
        assert self._is_visible("#fileContainer"), "文件容器缺失"

    def test_06_toolbar_structure(self):
        """测试工具栏结构"""
        self._goto()
        assert self._is_visible("#btnUpload"), "上传按钮缺失"
        assert self._is_visible("#btnDownload"), "下载按钮缺失"
        assert self._is_visible("#btnShare"), "分享按钮缺失"
        assert self._is_visible("#btnDelete"), "删除按钮缺失"

    def test_07_nav_sections(self):
        """测试导航分区"""
        self._goto()
        sections = self._get_text(".nav-section-title")
        assert "存储" in sections, "存储分区缺失"

    def test_08_nav_items(self):
        """测试导航项"""
        self._goto()
        nav_count = self._count(".nav-item")
        assert nav_count >= 10, f"导航项数量不足: {nav_count}"

    def test_09_category_navigation(self):
        """测试分类导航"""
        self._goto()
        categories = ["技术运维", "心理学", "文档", "有声剧"]
        for cat in categories:
            assert self._count(f'.nav-item[data-category="{cat}"]') > 0, f"分类 {cat} 缺失"

    def test_10_storage_display(self):
        """测试存储信息显示"""
        self._goto()
        assert self._is_visible("#storageUsed"), "存储使用量显示缺失"


class TestFileList(TestBase):
    """文件列表测试"""

    def _wait_for_file_load(self):
        try:
            self._wait_for_selector(".file-container")
            self.page.wait_for_timeout(500)
        except:
            pass

    def test_11_file_container_display(self):
        """测试文件容器显示"""
        self._goto()
        self._wait_for_file_load()
        assert self._is_visible("#fileContainer"), "文件容器未显示"

    def test_12_file_grid_view(self):
        """测试网格视图"""
        self._goto()
        self._wait_for_file_load()
        grid_btn = self.page.locator('.view-toggle button[data-view="grid"]')
        grid_btn.click()
        self.page.wait_for_timeout(300)
        assert self._is_visible(".file-grid"), "网格视图未显示"

    def test_13_file_list_view(self):
        """测试列表视图"""
        self._goto()
        self._wait_for_file_load()
        list_btn = self.page.locator('.view-toggle button[data-view="list"]')
        list_btn.click()
        self.page.wait_for_timeout(300)
        assert self._is_visible(".file-list-view"), "列表视图未显示"

    def test_14_file_icon_display(self):
        """测试文件图标显示"""
        self._goto()
        self._wait_for_file_load()
        icons = self.page.locator(".file-icon")
        assert icons.count() > 0, "文件图标未显示"

    def test_15_file_metadata(self):
        """测试文件元数据显示"""
        self._goto()
        self._wait_for_file_load()
        meta_elements = self.page.locator(".file-meta")
        assert meta_elements.count() > 0, "文件元数据未显示"

    def test_16_breadcrumb_display(self):
        """测试面包屑导航显示"""
        self._goto()
        assert self._is_visible(".breadcrumb"), "面包屑未显示"


class TestFileOperations(TestBase):
    """文件操作测试"""

    def _wait_for_file_load(self):
        try:
            self._wait_for_selector(".file-container")
            self.page.wait_for_timeout(500)
        except:
            pass

    def test_17_file_single_click(self):
        """测试文件单击"""
        self._goto()
        self._wait_for_file_load()
        items = self.page.locator(".file-item")
        if items.count() > 0:
            items.first.click()
            self.page.wait_for_timeout(300)

    def test_18_file_double_click_folder(self):
        """测试文件夹双击导航"""
        self._goto()
        self._wait_for_file_load()
        folders = self.page.locator(".file-item[data-dir='true']")
        if folders.count() > 0:
            folders.first.dblclick()
            self.page.wait_for_timeout(500)

    def test_19_toolbar_button_state(self):
        """测试工具栏按钮状态"""
        self._goto()
        self._wait_for_file_load()
        download_btn = self.page.locator("#btnDownload")
        share_btn = self.page.locator("#btnShare")
        assert download_btn.is_disabled(), "无选中时下载按钮应禁用"
        assert share_btn.is_disabled(), "无选中时分享按钮应禁用"


class TestModals(TestBase):
    """模态框测试"""

    def test_20_upload_modal_open_close(self):
        """测试上传模态框打开关闭"""
        self._goto()
        self._click("#btnUpload")
        self._wait_for_load()
        assert self._is_visible("#uploadModal.active"), "上传模态框未打开"
        self._click("#btnCloseUpload")
        self.page.wait_for_timeout(300)

    def test_21_upload_dropzone(self):
        """测试上传拖拽区域"""
        self._goto()
        self._click("#btnUpload")
        self._wait_for_load()
        dropzone = self.page.locator("#uploadDropzone")
        assert dropzone.is_visible(), "拖拽区域未显示"

    def test_22_cloud_modal_structure(self):
        """测试云盘管理模态框结构"""
        self._goto()
        self._click('.nav-item[data-view="cloud"]')
        self._wait_for_load()
        assert self._is_visible("#cloudModal.active"), "云盘模态框未打开"
        assert self._is_visible(".cloud-tabs"), "标签页未显示"

    def test_23_cloud_tab_switching(self):
        """测试云盘标签切换"""
        self._goto()
        self._click('.nav-item[data-view="cloud"]')
        self._wait_for_load()
        self._click('[data-tab="sync"]')
        self.page.wait_for_timeout(200)
        # cloud-sync 内容可能为空导致零高度，检查 active 类而非 is_visible
        has_active = self.page.locator("#cloud-sync").evaluate(
            'el => el.classList.contains("active")'
        )
        assert has_active, "同步任务Tab未激活(.active类缺失)"

    def test_24_add_disk_form(self):
        """测试添加网盘表单"""
        self._goto()
        self._click('.nav-item[data-view="cloud"]')
        self._wait_for_load()
        self._click('[data-tab="add"]')
        assert self._is_visible("#diskName"), "网盘名称输入框缺失"
        assert self._is_visible("#diskType"), "网盘类型选择框缺失"

    def test_25_knowledge_modal_structure(self):
        """测试知识导入模态框结构"""
        self._goto()
        self._click('.nav-item[data-view="knowledge"]')
        self._wait_for_load()
        assert self._is_visible("#knowledgeModal.active"), "知识导入模态框未打开"

    def test_26_share_modal_structure(self):
        """测试分享模态框结构"""
        self._goto()
        self.page.evaluate("showShareModal('/test.txt')")
        self.page.wait_for_timeout(300)
        assert self._is_visible("#shareModal.active"), "分享模态框未打开"
        assert self._is_visible("#shareUrl"), "分享链接输入框缺失"


class TestSearch(TestBase):
    """搜索功能测试"""

    def test_27_sidebar_search(self):
        """测试侧边栏搜索"""
        self._goto()
        search_input = self.page.locator("#searchInput")
        assert search_input.is_visible(), "侧边栏搜索框未显示"
        search_input.fill("test")
        self.page.wait_for_timeout(500)

    def test_28_topbar_search(self):
        """测试顶部搜索框"""
        self._goto()
        search_input = self.page.locator("#topSearchInput")
        assert search_input.is_visible(), "顶部搜索框未显示"
        search_input.fill("test")
        self.page.wait_for_timeout(500)


class TestNavigation(TestBase):
    """导航测试"""

    def test_29_nav_all_files(self):
        """测试全部文件导航"""
        self._goto()
        self._click('.nav-item[data-view="all"]')
        self._wait_for_load()
        path_text = self._get_text("#currentPath")
        assert "全部文件" in path_text

    def test_30_nav_uploads(self):
        """测试上传记录导航"""
        self._goto()
        self._click('.nav-item[data-view="uploads"]')
        self._wait_for_load()

    def test_31_nav_knowledge(self):
        """测试知识导入导航"""
        self._goto()
        self._click('.nav-item[data-view="knowledge"]')
        self._wait_for_load()
        assert self._is_visible("#knowledgeModal.active"), "知识导入模态框未打开"

    def test_32_nav_cloud(self):
        """测试云盘管理导航"""
        self._goto()
        self._click('.nav-item[data-view="cloud"]')
        self._wait_for_load()
        assert self._is_visible("#cloudModal.active"), "云盘管理模态框未打开"


class TestViewToggle(TestBase):
    """视图切换测试"""

    def test_33_view_toggle_buttons(self):
        """测试视图切换按钮"""
        self._goto()
        assert self._is_visible('.view-toggle button[data-view="grid"]'), "网格视图按钮缺失"
        assert self._is_visible('.view-toggle button[data-view="list"]'), "列表视图按钮缺失"

    def test_34_switch_to_list_view(self):
        """测试切换到列表视图"""
        self._goto()
        self._click('.view-toggle button[data-view="list"]')
        self.page.wait_for_timeout(300)
        assert self._is_visible(".file-list-view"), "列表视图未显示"

    def test_35_switch_to_grid_view(self):
        """测试切换到网格视图"""
        self._goto()
        self._click('.view-toggle button[data-view="grid"]')
        self.page.wait_for_timeout(300)
        assert self._is_visible(".file-grid"), "网格视图未显示"


class TestToast(TestBase):
    """Toast通知测试"""

    def test_36_toast_container(self):
        """测试Toast容器"""
        self._goto()
        # toast 容器在无通知时为空(零高度)，Playwright is_visible 会返回 False
        # 检查 DOM 存在性即可
        count = self.page.locator("#toastContainer").count()
        assert count > 0, "Toast容器DOM缺失"

    def test_37_toast_creation(self):
        """测试Toast创建"""
        self._goto()
        self.page.evaluate("showToast('测试消息', 'success')")
        self.page.wait_for_timeout(500)
        assert self._count(".toast") > 0, "Toast未显示"


class TestAPI(TestBase):
    """API接口测试"""

    def test_38_api_files_list(self):
        """测试文件列表API"""
        resp = httpx.get(f"{BASE_URL}/api/files", timeout=10)
        assert resp.status_code == 200
        data = resp.json()
        assert "items" in data or "files" in data

    def test_39_api_files_search(self):
        """测试文件搜索API"""
        resp = httpx.get(f"{BASE_URL}/api/files/search?q=test", timeout=10)
        assert resp.status_code == 200

    def test_40_api_disks_list(self):
        """测试云盘列表API"""
        resp = httpx.get(f"{BASE_URL}/api/disks", timeout=10)
        assert resp.status_code == 200

    def test_41_api_knowledge_status(self):
        """测试知识状态API"""
        resp = httpx.get(f"{BASE_URL}/api/knowledge/status", timeout=10)
        assert resp.status_code == 200

    def test_42_api_status(self):
        """测试状态API"""
        resp = httpx.get(f"{BASE_URL}/api/status", timeout=10)
        assert resp.status_code == 200


class TestResponsive(TestBase):
    """响应式布局测试"""

    def test_43_large_screen(self):
        """测试大屏"""
        self.context.close()
        self.context = self.browser.new_context(viewport={'width': 1920, 'height': 1080})
        self.page = self.context.new_page()
        self._goto()
        assert self._is_visible(".sidebar"), "侧边栏未显示"

    def test_44_medium_screen(self):
        """测试中屏"""
        self.context.close()
        self.context = self.browser.new_context(viewport={'width': 1024, 'height': 768})
        self.page = self.context.new_page()
        self._goto()
        assert self._is_visible(".sidebar"), "侧边栏未显示"


class TestPerformance(TestBase):
    """性能测试"""

    def test_45_page_load_time(self):
        """测试页面加载时间"""
        start = time.time()
        self._goto()
        load_time = time.time() - start
        print(f"\n  页面加载时间: {load_time:.2f}s")
        assert load_time < 10, f"页面加载过慢: {load_time:.2f}s"


# ========== 运行器 ==========

def run_tests():
    """运行所有测试"""
    print("=" * 70)
    print("  8866 学习目录系统 - 全功能UI自动化测试")
    print("=" * 70)

    test_classes = [
        TestPageBasics,
        TestFileList,
        TestFileOperations,
        TestModals,
        TestSearch,
        TestNavigation,
        TestViewToggle,
        TestToast,
        TestAPI,
        TestResponsive,
        TestPerformance,
    ]

    # 收集所有测试方法
    all_tests = []
    for cls in test_classes:
        cls.setup_class()
        for name in dir(cls):
            if name.startswith("test_"):
                all_tests.append((cls, name))

    print(f"\n共 {len(all_tests)} 个测试用例\n")

    passed = 0
    failed = 0
    results = []

    for i, (cls, name) in enumerate(all_tests, 1):
        print(f"[{i}/{len(all_tests)}] {name}", end=" ")
        instance = cls()
        try:
            instance.setup_method()
            getattr(instance, name)()
            results.append((name, "✅"))
            passed += 1
            print("✅")
        except Exception as e:
            results.append((name, f"❌ {str(e)[:40]}"))
            failed += 1
            print(f"❌ {e}")
        finally:
            instance.teardown_method()

    # 汇总
    print("\n" + "=" * 70)
    print("  测试结果汇总")
    print("=" * 70)

    for name, result in results:
        print(f"  {result} {name}")

    print(f"\n" + "-" * 70)
    print(f"  总计: {passed} 通过, {failed} 失败, {len(all_tests)} 总计")
    print(f"  截图: {SCREENSHOT_DIR}")
    print("=" * 70)

    return failed == 0


if __name__ == "__main__":
    success = run_tests()
    sys.exit(0 if success else 1)
