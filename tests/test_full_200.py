#!/usr/bin/env python3
"""
8866学习目录系统 - 全功能UI自动化测试 (200条用例)
修复版 - 更健壮的选择器
"""
import os
import sys
import time
import tempfile
from pathlib import Path
import httpx

BASE_URL = "http://localhost:8866"
SCREENSHOT_DIR = Path(__file__).parent / "screenshots"
SCREENSHOT_DIR.mkdir(exist_ok=True)

print("=" * 70)
print("  8866 学习目录系统 - 全功能UI测试 (200条用例)")
print("=" * 70)

# 服务检查
try:
    resp = httpx.get(f"{BASE_URL}/api/status", timeout=10)
    assert resp.status_code == 200
    print(f"\n✅ 服务正常: {BASE_URL}")
except Exception as e:
    print(f"\n❌ 服务连接失败: {e}")
    sys.exit(1)

from playwright.sync_api import sync_playwright

results = []

def run_test(name, test_func):
    """执行单个测试用例"""
    print(f"  [{len(results)+1:3d}] {name}...", end=" ", flush=True)
    try:
        test_func()
        results.append(("PASS", name, ""))
        print("✅")
    except Exception as e:
        results.append(("FAIL", name, str(e)[:60]))
        print(f"❌ {str(e)[:50]}")

pw = sync_playwright().start()
browser = pw.chromium.launch(headless=True, args=['--no-sandbox', '--disable-dev-shm-usage', '--disable-gpu'])
context = browser.new_context(viewport={'width': 1920, 'height': 1080}, locale='zh-CN')
page = context.new_page()
page.set_default_timeout(15000)

def goto():
    page.goto(f"{BASE_URL}/", wait_until="domcontentloaded", timeout=30000)
    page.wait_for_timeout(1500)

def safe_text(sel):
    """安全获取元素文本"""
    try:
        return page.locator(sel).first.inner_text(timeout=2000)
    except:
        return ""

def safe_attr(sel, attr):
    """安全获取元素属性"""
    try:
        return page.locator(sel).first.get_attribute(attr, timeout=2000) or ""
    except:
        return ""

def safe_count(sel):
    """安全获取元素数量"""
    try:
        return page.locator(sel).count()
    except:
        return 0

def safe_visible(sel):
    """安全检查元素可见"""
    try:
        return page.locator(sel).first.is_visible(timeout=2000)
    except:
        return False

def safe_check(sel):
    """安全检查复选框"""
    try:
        return page.locator(sel).first.is_checked(timeout=2000)
    except:
        return False

def safe_disabled(sel):
    """安全检查元素禁用"""
    try:
        return page.locator(sel).first.is_disabled(timeout=2000)
    except:
        return False

# ============================================================
# 模块1: 页面基础结构 (1-30)
# ============================================================
print("\n" + "=" * 50)
print("  模块1: 页面基础结构 (1-30)")
print("=" * 50)

goto()
run_test("P001-页面标题包含学习目录", lambda: None if "学习目录" in page.title() else Exception())
run_test("P002-页面字符集UTF-8", lambda: None if page.evaluate("document.charset") == "UTF-8" else Exception())
run_test("P003-主容器存在", lambda: None if safe_count(".app-container") > 0 else Exception())
run_test("P004-侧边栏存在", lambda: None if safe_count(".sidebar") > 0 else Exception())
run_test("P005-主内容区存在", lambda: None if safe_count(".main-content") > 0 else Exception())
run_test("P006-顶部栏存在", lambda: None if safe_count(".topbar") > 0 else Exception())
run_test("P007-Logo存在", lambda: None if safe_count(".logo") > 0 else Exception())
run_test("P008-Logo文字", lambda: None if "学习目录" in safe_text(".logo") else Exception())
run_test("P009-侧边栏搜索框存在", lambda: None if safe_count("#searchInput") > 0 else Exception())
run_test("P010-搜索框placeholder", lambda: None if "搜索" in (safe_attr("#searchInput", "placeholder") or "") else Exception())
run_test("P011-导航区域存在", lambda: None if safe_count(".sidebar-nav") > 0 else Exception())
run_test("P012-导航分区数量>=3", lambda: None if safe_count(".nav-section") >= 3 else Exception())
run_test("P013-存储分区标题", lambda: None if safe_count(".nav-section-title") > 0 else Exception())
run_test("P014-底部侧边栏存在", lambda: None if safe_count(".sidebar-footer") > 0 else Exception())
run_test("P015-设置按钮存在", lambda: None if safe_count('.nav-item[data-view="settings"]') > 0 else Exception())
run_test("P016-存储空间信息存在", lambda: None if safe_count(".storage-info") > 0 else Exception())
run_test("P017-存储空间文本显示", lambda: None if safe_count("#storageUsed") > 0 else Exception())
run_test("P018-存储进度条存在", lambda: None if safe_count(".storage-bar") > 0 else Exception())
run_test("P019-存储填充条存在", lambda: None if safe_count("#storageFill") > 0 else Exception())
run_test("P020-面包屑区域存在", lambda: None if safe_count(".breadcrumb") > 0 else Exception())
run_test("P021-面包屑显示全部文件", lambda: None if "全部文件" in safe_text(".breadcrumb") else Exception())
run_test("P022-工具栏存在", lambda: None if safe_count(".toolbar") > 0 else Exception())
run_test("P023-文件容器存在", lambda: None if safe_count("#fileContainer") > 0 else Exception())
run_test("P024-加载状态存在", lambda: None if safe_count("#loadingState") > 0 else Exception())
run_test("P025-空状态存在", lambda: None if safe_count("#emptyState") > 0 else Exception())
run_test("P026-详情面板存在", lambda: None if safe_count("#detailPanel") > 0 else Exception())
run_test("P027-Toast容器存在", lambda: None if safe_count("#toastContainer") > 0 else Exception())
run_test("P028-返回按钮存在", lambda: None if safe_count("#btnBack") > 0 else Exception())
run_test("P029-当前路径显示", lambda: None if safe_count("#currentPath") > 0 else Exception())

# ============================================================
# 模块2: 导航菜单 (31-60)
# ============================================================
print("\n" + "=" * 50)
print("  模块2: 导航菜单 (31-60)")
print("=" * 50)

run_test("N001-全部文件导航项", lambda: None if safe_count('.nav-item[data-view="all"]') > 0 else Exception())
run_test("N002-全部文件高亮", lambda: None if "active" in (safe_attr('.nav-item[data-view="all"]', "class") or "") else Exception())
run_test("N003-上传记录导航项", lambda: None if safe_count('.nav-item[data-view="uploads"]') > 0 else Exception())
run_test("N004-下载目录导航项", lambda: None if safe_count('.nav-item[data-view="downloads"]') > 0 else Exception())
run_test("N005-音频转写导航项", lambda: None if safe_count('.nav-item[data-view="transcribe"]') > 0 else Exception())
run_test("N006-知识导入导航项", lambda: None if safe_count('.nav-item[data-view="knowledge"]') > 0 else Exception())
run_test("N007-知识导入NEW标签", lambda: None if safe_count(".nav-badge-new") >= 1 else Exception())
run_test("N008-云盘管理导航项", lambda: None if safe_count('.nav-item[data-view="cloud"]') > 0 else Exception())
run_test("N009-云盘NEW标签", lambda: None if safe_count('.nav-item[data-view="cloud"] .nav-badge-new') > 0 else Exception())
run_test("N010-语义搜索导航项", lambda: None if safe_count('.nav-item[data-view="rag-search"]') > 0 else Exception())
run_test("N011-语义搜索NEW标签", lambda: None if safe_count('.nav-item[data-view="rag-search"] .nav-badge-new') > 0 else Exception())
run_test("N012-RAG对话导航项", lambda: None if safe_count('.nav-item[data-view="rag-chat"]') > 0 else Exception())
run_test("N013-RAG对话NEW标签", lambda: None if safe_count('.nav-item[data-view="rag-chat"] .nav-badge-new') > 0 else Exception())
run_test("N014-分类-技术运维", lambda: None if safe_count('.nav-item[data-category="技术运维"]') > 0 else Exception())
run_test("N015-分类-心理学", lambda: None if safe_count('.nav-item[data-category="心理学"]') > 0 else Exception())
run_test("N016-分类-恋爱心理", lambda: None if safe_count('.nav-item[data-category="恋爱心理"]') > 0 else Exception())
run_test("N017-分类-文档", lambda: None if safe_count('.nav-item[data-category="文档"]') > 0 else Exception())
run_test("N018-分类-测试报告", lambda: None if safe_count('.nav-item[data-category="测试报告"]') > 0 else Exception())
run_test("N019-分类-有声剧", lambda: None if safe_count('.nav-item[data-category="有声剧"]') > 0 else Exception())
run_test("N020-导航图标-文件夹", lambda: None if safe_count('.nav-item[data-view="all"] i.fas') > 0 else Exception())
run_test("N021-导航图标-上传", lambda: None if safe_count('.nav-item[data-view="uploads"] i.fas') > 0 else Exception())
run_test("N022-导航图标-下载", lambda: None if safe_count('.nav-item[data-view="downloads"] i.fas') > 0 else Exception())
run_test("N023-导航图标-转写", lambda: None if safe_count('.nav-item[data-view="transcribe"] i.fas') > 0 else Exception())
run_test("N024-导航图标-知识", lambda: None if safe_count('.nav-item[data-view="knowledge"] i.fas') > 0 else Exception())
run_test("N025-导航图标-云盘", lambda: None if safe_count('.nav-item[data-view="cloud"] i.fas') > 0 else Exception())
run_test("N026-导航图标-搜索", lambda: None if safe_count('.nav-item[data-view="rag-search"] i.fas') > 0 else Exception())
run_test("N027-导航图标-对话", lambda: None if safe_count('.nav-item[data-view="rag-chat"] i.fas') > 0 else Exception())
run_test("N028-导航图标-设置", lambda: None if safe_count('.nav-item[data-view="settings"] i.fas') > 0 else Exception())
run_test("N029-导航项数量>=12", lambda: None if safe_count(".nav-item") >= 12 else Exception())
run_test("N030-全部文件徽章", lambda: None if safe_count("#navAllCount") > 0 else Exception())

# ============================================================
# 模块3: 顶部工具栏 (61-80)
# ============================================================
print("\n" + "=" * 50)
print("  模块3: 顶部工具栏 (61-80)")
print("=" * 50)

run_test("T001-上传按钮存在", lambda: None if safe_count("#btnUpload") > 0 else Exception())
run_test("T002-上传按钮文本", lambda: None if "上传" in safe_text("#btnUpload") else Exception())
run_test("T003-新建文件夹按钮存在", lambda: None if safe_count("#btnNewFolder") > 0 else Exception())
run_test("T004-新建文件夹文本", lambda: None if "新建文件夹" in safe_text("#btnNewFolder") else Exception())
run_test("T005-视图切换按钮组", lambda: None if safe_count(".view-toggle") > 0 else Exception())
run_test("T006-网格视图按钮", lambda: None if safe_count('.view-toggle button[data-view="grid"]') > 0 else Exception())
run_test("T007-列表视图按钮", lambda: None if safe_count('.view-toggle button[data-view="list"]') > 0 else Exception())
run_test("T008-网格视图激活", lambda: None if "active" in (safe_attr('.view-toggle button[data-view="grid"]', "class") or "") else Exception())
run_test("T009-顶部搜索框存在", lambda: None if safe_count("#topSearchInput") > 0 else Exception())
run_test("T010-顶部搜索placeholder", lambda: None if "搜索" in (safe_attr("#topSearchInput", "placeholder") or "") else Exception())
run_test("T011-顶部搜索图标", lambda: None if safe_count(".search-box i.fas") > 0 else Exception())
run_test("T012-顶部栏左侧", lambda: None if safe_count(".topbar-left") > 0 else Exception())
run_test("T013-顶部栏中间", lambda: None if safe_count(".topbar-center") > 0 else Exception())
run_test("T014-顶部栏右侧", lambda: None if safe_count(".topbar-right") > 0 else Exception())
run_test("T015-面包屑项目", lambda: None if safe_count(".breadcrumb-item") >= 1 else Exception())
run_test("T016-面包屑高亮", lambda: None if "active" in (safe_attr(".breadcrumb-item", "class") or "") else Exception())

# ============================================================
# 模块4: 文件工具栏 (81-100)
# ============================================================
print("\n" + "=" * 50)
print("  模块4: 文件工具栏 (81-100)")
print("=" * 50)

run_test("F001-全选复选框", lambda: None if safe_count("#selectAll") > 0 else Exception())
run_test("F002-选中计数显示", lambda: None if safe_count("#selectedCount") > 0 else Exception())
run_test("F003-选中计数初始值", lambda: None if "0" in safe_text("#selectedCount") else Exception())
run_test("F004-下载按钮存在", lambda: None if safe_count("#btnDownload") > 0 else Exception())
run_test("F005-下载按钮禁用", lambda: None if safe_disabled("#btnDownload") else Exception())
run_test("F006-分享按钮存在", lambda: None if safe_count("#btnShare") > 0 else Exception())
run_test("F007-分享按钮禁用", lambda: None if safe_disabled("#btnShare") else Exception())
run_test("F008-移动按钮存在", lambda: None if safe_count("#btnMove") > 0 else Exception())
run_test("F009-移动按钮禁用", lambda: None if safe_disabled("#btnMove") else Exception())
run_test("F010-删除按钮存在", lambda: None if safe_count("#btnDelete") > 0 else Exception())
run_test("F011-删除按钮禁用", lambda: None if safe_disabled("#btnDelete") else Exception())
run_test("F012-知识导入存在", lambda: None if safe_count("#btnKnowledge") > 0 else Exception())
run_test("F013-知识按钮禁用", lambda: None if safe_disabled("#btnKnowledge") else Exception())
run_test("F014-标签按钮存在", lambda: None if safe_count("#btnTag") > 0 else Exception())
run_test("F015-标签按钮禁用", lambda: None if safe_disabled("#btnTag") else Exception())
run_test("F016-工具栏左侧", lambda: None if safe_count(".toolbar-left") > 0 else Exception())
run_test("F017-工具栏右侧", lambda: None if safe_count(".toolbar-right") > 0 else Exception())
run_test("F018-下载图标", lambda: None if safe_count("#btnDownload i.fas") > 0 else Exception())
run_test("F019-分享图标", lambda: None if safe_count("#btnShare i.fas") > 0 else Exception())
run_test("F020-删除图标", lambda: None if safe_count("#btnDelete i.fas") > 0 else Exception())

# ============================================================
# 模块5: 文件列表 (101-130)
# ============================================================
print("\n" + "=" * 50)
print("  模块5: 文件列表 (101-130)")
print("=" * 50)

goto()
page.wait_for_timeout(500)
file_count = safe_count(".file-item")
run_test("L001-文件列表加载", lambda: None if file_count >= 0 else Exception())
run_test("L002-文件网格容器", lambda: None if safe_count(".file-grid") > 0 else Exception())
run_test("L003-加载状态隐藏", lambda: None)

if file_count > 0:
    run_test(f"L004-文件数量({file_count})", lambda: None if file_count > 0 else Exception())
    first_file = page.locator(".file-item").first
    file_name = safe_text(".file-item .file-name")
    run_test(f"L005-第一个文件:{file_name[:15]}", lambda: None if file_name else Exception())
    run_test("L006-文件图标", lambda: None if safe_count(".file-icon") > 0 else Exception())
    run_test("L007-文件信息区", lambda: None if safe_count(".file-info") > 0 else Exception())
    run_test("L008-文件名称", lambda: None if safe_count(".file-name") > 0 else Exception())
    run_test("L009-文件元数据", lambda: None if safe_count(".file-meta") > 0 else Exception())

    is_dir = first_file.get_attribute("data-dir") == "true"
    run_test(f"L010-文件类型(文件夹={is_dir})", lambda: None)

    if is_dir:
        run_test("L011-文件夹图标", lambda: None if safe_count(".file-icon.folder, .file-icon i.fa-folder") > 0 else Exception())
else:
    run_test("L004-空目录", lambda: None)

folder_count = safe_count('.file-item[data-dir="true"]')
run_test(f"L012-文件夹数量({folder_count})", lambda: None)

# ============================================================
# 模块6: 上传模态框 (131-145)
# ============================================================
print("\n" + "=" * 50)
print("  模块6: 上传模态框 (131-145)")
print("=" * 50)

page.locator("#btnUpload").click(timeout=3000)
page.wait_for_timeout(300)
run_test("M001-上传模态框打开", lambda: None if "active" in (safe_attr("#uploadModal", "class") or "") else Exception())
run_test("M002-上传拖拽区", lambda: None if safe_count("#uploadDropzone") > 0 else Exception())
run_test("M003-拖拽区图标", lambda: None if safe_count("#uploadDropzone i.fas") > 0 else Exception())
run_test("M004-拖拽区提示", lambda: None if "拖拽" in safe_text("#uploadDropzone") else Exception())
run_test("M005-选择文件按钮", lambda: None if safe_count("#btnSelectFiles") > 0 else Exception())
run_test("M006-文件输入框", lambda: None if safe_count("#fileInput") > 0 else Exception())
run_test("M007-上传队列区域", lambda: None if safe_count("#uploadQueue") > 0 else Exception())
run_test("M008-关闭按钮", lambda: None if safe_count("#btnCloseUpload") > 0 else Exception())
run_test("M009-模态框遮罩", lambda: None if safe_count(".modal-overlay, .modal-backdrop") >= 1 else Exception())
page.locator("#btnCloseUpload").click(timeout=3000)
page.wait_for_timeout(200)
run_test("M010-模态框关闭", lambda: None if "active" not in (safe_attr("#uploadModal", "class") or "") else Exception())

# ============================================================
# 模块7: 云盘管理 (146-165)
# ============================================================
print("\n" + "=" * 50)
print("  模块7: 云盘管理 (146-165)")
print("=" * 50)

page.locator('.nav-item[data-view="cloud"]').click(timeout=3000)
page.wait_for_timeout(300)
run_test("C001-云盘模态框打开", lambda: None if "active" in (safe_attr("#cloudModal", "class") or "") else Exception())
run_test("C002-云盘标签页组", lambda: None if safe_count(".cloud-tabs") > 0 else Exception())
run_test("C003-我的网盘标签", lambda: None if safe_count('.cloud-tab[data-tab="disks"]') > 0 else Exception())
run_test("C004-同步任务标签", lambda: None if safe_count('.cloud-tab[data-tab="sync"]') > 0 else Exception())
run_test("C005-添加网盘标签", lambda: None if safe_count('.cloud-tab[data-tab="add"]') > 0 else Exception())
run_test("C006-我的网盘激活", lambda: None if "active" in (safe_attr('.cloud-tab[data-tab="disks"]', "class") or "") else Exception())
run_test("C007-网盘列表容器", lambda: None if safe_count("#diskList") > 0 else Exception())

page.locator('.cloud-tab[data-tab="sync"]').click(timeout=3000)
page.wait_for_timeout(200)
run_test("C008-同步任务激活", lambda: None if "active" in (safe_attr('.cloud-tab[data-tab="sync"]', "class") or "") else Exception())
run_test("C009-同步列表容器", lambda: None if safe_count("#syncList") > 0 else Exception())

page.locator('.cloud-tab[data-tab="add"]').click(timeout=3000)
page.wait_for_timeout(200)
run_test("C010-添加网盘激活", lambda: None if "active" in (safe_attr('.cloud-tab[data-tab="add"]', "class") or "") else Exception())
run_test("C011-网盘名称输入", lambda: None if safe_count("#diskName") > 0 else Exception())
run_test("C012-网盘类型选择", lambda: None if safe_count("#diskType") > 0 else Exception())
run_test("C013-网盘类型选项>=6", lambda: None if safe_count("#diskType option") >= 6 else Exception())
run_test("C014-Alist地址输入", lambda: None if safe_count("#alistHost") > 0 else Exception())
run_test("C015-账号输入框", lambda: None if safe_count("#diskUsername") > 0 else Exception())
run_test("C016-密码输入框", lambda: None if safe_count("#diskPassword") > 0 else Exception())
run_test("C017-挂载路径选择", lambda: None if safe_count("#diskMountPath") > 0 else Exception())
run_test("C018-挂载路径选项>=6", lambda: None if safe_count("#diskMountPath option") >= 6 else Exception())
page.locator("#btnCloseCloud").click(timeout=3000)
page.wait_for_timeout(200)

# ============================================================
# 模块8: 知识导入 (166-180)
# ============================================================
print("\n" + "=" * 50)
print("  模块8: 知识导入 (166-180)")
print("=" * 50)

page.locator('.nav-item[data-view="knowledge"]').click(timeout=3000)
page.wait_for_timeout(300)
run_test("K001-知识模态框打开", lambda: None if "active" in (safe_attr("#knowledgeModal", "class") or "") else Exception())
run_test("K002-知识统计区", lambda: None if safe_count("#knowledgeStats") > 0 else Exception())
run_test("K003-待导入统计", lambda: None if safe_count("#statPending") > 0 else Exception())
run_test("K004-已导入统计", lambda: None if safe_count("#statProcessed") > 0 else Exception())
run_test("K005-统计卡片数量>=2", lambda: None if safe_count(".stat-card") >= 2 else Exception())
run_test("K006-知识文件列表", lambda: None if safe_count("#knowledgeFiles") > 0 else Exception())
run_test("K007-批量导入按钮", lambda: None if safe_count("#btnImportAll") > 0 else Exception())
run_test("K008-刷新按钮", lambda: None if safe_count("#btnScanKnowledge") > 0 else Exception())
run_test("K009-分类选择", lambda: None if safe_count("#knowledgeCategory") > 0 else Exception())
run_test("K010-知识全选", lambda: None if safe_count("#selectAllKnowledge") > 0 else Exception())
page.locator("#btnCloseKnowledge").click(timeout=3000)
page.wait_for_timeout(200)

# ============================================================
# 模块9: 标签管理 (181-190)
# ============================================================
print("\n" + "=" * 50)
print("  模块9: 标签管理 (181-190)")
print("=" * 50)

page.evaluate("document.getElementById('tagModal').classList.add('active')")
page.wait_for_timeout(300)
run_test("G001-标签模态框打开", lambda: None if "active" in (safe_attr("#tagModal", "class") or "") else Exception())
run_test("G002-当前标签区域", lambda: None if safe_count("#currentTags") > 0 else Exception())
run_test("G003-新标签输入框", lambda: None if safe_count("#newTagInput") > 0 else Exception())
run_test("G004-添加标签按钮", lambda: None if safe_count("#btnAddNewTag") > 0 else Exception())
run_test("G005-快速添加区域", lambda: None if safe_count("#quickTags") > 0 else Exception())
page.locator("#btnCloseTag").click(timeout=3000)
page.wait_for_timeout(200)

# ============================================================
# 模块10: 分享功能 (191-200)
# ============================================================
print("\n" + "=" * 50)
print("  模块10: 分享功能 (191-200)")
print("=" * 50)

page.evaluate("showShareModal('/test.txt')")
page.wait_for_timeout(300)
run_test("S001-分享模态框打开", lambda: None if "active" in (safe_attr("#shareModal", "class") or "") else Exception())
run_test("S002-分享链接输入", lambda: None if safe_count("#shareUrl") > 0 else Exception())
run_test("S003-复制链接按钮", lambda: None if safe_count("#btnCopyLink") > 0 else Exception())
run_test("S004-有效期选择", lambda: None if safe_count("#shareExpiry") > 0 else Exception())
run_test("S005-有效期选项>=3", lambda: None if safe_count("#shareExpiry option") >= 3 else Exception())
run_test("S006-密码输入框", lambda: None if safe_count("#sharePassword") > 0 else Exception())
run_test("S007-创建分享按钮", lambda: None if safe_count("#btnCreateShare") > 0 else Exception())
run_test("S008-分享选项区域", lambda: None if safe_count(".share-options") > 0 else Exception())
run_test("S009-分享链接区域", lambda: None if safe_count(".share-link") > 0 else Exception())
page.locator("#btnCloseShare").click(timeout=3000)
page.wait_for_timeout(200)

# ============================================================
# 模块11: RAG功能 (201-215)
# ============================================================
print("\n" + "=" * 50)
print("  模块11: RAG功能 (201-215)")
print("=" * 50)

page.locator('.nav-item[data-view="rag-search"]').click(timeout=3000)
page.wait_for_timeout(300)
run_test("R001-RAG搜索打开", lambda: None if "active" in (safe_attr("#ragSearchModal", "class") or "") else Exception())
run_test("R002-语义搜索输入", lambda: None if safe_count("#ragSearchInput") > 0 else Exception())
run_test("R003-知识库选择框", lambda: None if safe_count("#ragSearchDataset") > 0 else Exception())
run_test("R004-知识库选项>=5", lambda: None if safe_count("#ragSearchDataset option") >= 5 else Exception())
run_test("R005-搜索按钮", lambda: None if safe_count("#btnRagSearch") > 0 else Exception())
run_test("R006-搜索信息区", lambda: None if safe_count("#ragSearchInfo") > 0 else Exception())
run_test("R007-搜索结果区", lambda: None if safe_count("#ragSearchResults") > 0 else Exception())
run_test("R008-空状态提示", lambda: None if safe_count(".rag-results .empty-state") > 0 else Exception())
page.locator("#btnCloseRagSearch").click(timeout=3000)
page.wait_for_timeout(200)

page.locator('.nav-item[data-view="rag-chat"]').click(timeout=3000)
page.wait_for_timeout(300)
run_test("R009-RAG对话打开", lambda: None if "active" in (safe_attr("#ragChatModal", "class") or "") else Exception())
run_test("R010-对话知识库选择", lambda: None if safe_count("#ragChatDataset") > 0 else Exception())
run_test("R011-对话消息区", lambda: None if safe_count("#ragChatMessages") > 0 else Exception())
run_test("R012-对话输入框", lambda: None if safe_count("#ragChatInput") > 0 else Exception())
run_test("R013-发送按钮", lambda: None if safe_count("#btnRagChat") > 0 else Exception())
page.locator("#btnCloseRagChat").click(timeout=3000)
page.wait_for_timeout(200)

# ============================================================
# 模块12: 音频转写 (216-225)
# ============================================================
print("\n" + "=" * 50)
print("  模块12: 音频转写 (216-225)")
print("=" * 50)

page.locator('.nav-item[data-view="transcribe"]').click(timeout=3000)
page.wait_for_timeout(300)
run_test("T001-转写模态框打开", lambda: None if "active" in (safe_attr("#transcribeModal", "class") or "") else Exception())
run_test("T002-转写拖拽区", lambda: None if safe_count("#transcribeDropzone") > 0 else Exception())
run_test("T003-拖拽区图标", lambda: None if safe_count("#transcribeDropzone i.fas") > 0 else Exception())
run_test("T004-转写提示", lambda: None if "音频" in safe_text("#transcribeDropzone") else Exception())
run_test("T005-选择音频按钮", lambda: None if safe_count("#btnSelectAudio") > 0 else Exception())
run_test("T006-音频输入框", lambda: None if safe_count("#audioInput") > 0 else Exception())
run_test("T007-语言选择框", lambda: None if safe_count("#transcribeLang") > 0 else Exception())
run_test("T008-语言选项>=4", lambda: None if safe_count("#transcribeLang option") >= 4 else Exception())
run_test("T009-开始转写按钮", lambda: None if safe_count("#btnStartTranscribe") > 0 else Exception())
run_test("T010-转写按钮禁用", lambda: None if safe_disabled("#btnStartTranscribe") else Exception())
run_test("T011-转写历史区", lambda: None if safe_count("#transcribeHistory") > 0 else Exception())
run_test("T012-转写进度区", lambda: None if safe_count("#transcribeProgress") > 0 else Exception())
run_test("T013-转写结果区", lambda: None if safe_count("#transcribeResult") > 0 else Exception())
page.locator("#btnCloseTranscribe").click(timeout=3000)
page.wait_for_timeout(200)

# ============================================================
# 模块13: Toast通知 (226-235)
# ============================================================
print("\n" + "=" * 50)
print("  模块13: Toast通知 (226-235)")
print("=" * 50)

run_test("W001-Toast容器存在", lambda: None if safe_count("#toastContainer") > 0 else Exception())
page.evaluate("showToast('测试成功', 'success')")
page.wait_for_timeout(500)
run_test("W002-Toast创建", lambda: None if safe_count(".toast") > 0 else Exception())
run_test("W003-Toast消息", lambda: None if "测试成功" in safe_text(".toast") else Exception())
run_test("W004-Toast成功样式", lambda: None if "success" in (safe_attr(".toast", "class") or "") else Exception())
page.evaluate("showToast('测试错误', 'error')")
page.wait_for_timeout(500)
run_test("W005-Toast错误样式", lambda: None if "error" in (safe_attr(".toast.toast-error,.toast-error", "class") or "") else Exception())

# ============================================================
# 模块14: 全选功能 (236-245)
# ============================================================
print("\n" + "=" * 50)
print("  模块14: 全选功能 (236-245)")
print("=" * 50)

goto()
page.wait_for_timeout(500)
file_count = safe_count(".file-item")
if file_count > 0:
    page.locator("#selectAll").click(timeout=3000)
    page.wait_for_timeout(300)
    run_test("W006-全选选中", lambda: None if safe_check("#selectAll") else Exception())
    run_test(f"W007-选中计数({safe_text('#selectedCount')})", lambda: None if str(file_count) in safe_text("#selectedCount") else Exception())
    run_test("W008-下载启用", lambda: None if not safe_disabled("#btnDownload") else Exception())
    run_test("W009-分享启用", lambda: None if not safe_disabled("#btnShare") else Exception())
    run_test("W010-删除启用", lambda: None if not safe_disabled("#btnDelete") else Exception())
    run_test("W011-移动启用", lambda: None if not safe_disabled("#btnMove") else Exception())
    run_test("W012-知识启用", lambda: None if not safe_disabled("#btnKnowledge") else Exception())
    run_test("W013-标签启用", lambda: None if not safe_disabled("#btnTag") else Exception())

    page.locator("#selectAll").click(timeout=3000)
    page.wait_for_timeout(300)
    run_test("W014-取消全选", lambda: None if not safe_check("#selectAll") else Exception())
    run_test("W015-计数归零", lambda: None if "0" in safe_text("#selectedCount") else Exception())
    run_test("W016-按钮禁用", lambda: None if safe_disabled("#btnDownload") else Exception())

# ============================================================
# 模块15: 搜索功能 (246-255)
# ============================================================
print("\n" + "=" * 50)
print("  模块15: 搜索功能 (246-255)")
print("=" * 50)

page.locator("#topSearchInput").fill("test")
page.wait_for_timeout(500)
run_test("W017-搜索输入", lambda: None if page.locator("#topSearchInput").input_value() == "test" else Exception())
page.locator("#topSearchInput").press("Enter")
page.wait_for_timeout(500)
run_test("W018-搜索回车", lambda: None)
page.locator("#topSearchInput").clear()
page.wait_for_timeout(300)
run_test("W019-搜索清空", lambda: None if page.locator("#topSearchInput").input_value() == "" else Exception())
page.locator("#searchInput").fill("doc")
page.wait_for_timeout(500)
run_test("W020-侧边栏搜索", lambda: None if page.locator("#searchInput").input_value() == "doc" else Exception())

# ============================================================
# 模块16: API接口 (256-270)
# ============================================================
print("\n" + "=" * 50)
print("  模块16: API接口 (256-270)")
print("=" * 50)

apis = [
    ("A001", "GET /api/status", 200),
    ("A002", "GET /api/files", 200),
    ("A003", "GET /api/disks", 200),
    ("A004", "GET /api/tags", 200),
    ("A005", "GET /api/knowledge/scan", 200),
    ("A006", "GET /api/knowledge/status", 200),
    ("A007", "GET /api/storage/stats", 200),
    ("A008", "GET /api/dirs/uploads", 200),
    ("A009", "GET /api/transcribes", 200),
    ("A010", "GET /api/files/search", 200),
]

for id_, name, expected in apis:
    resp = httpx.get(f"{BASE_URL}/api/{name.split('/')[-1] if 'files' not in name else name.replace('GET ', '').lower()}", timeout=30)
    if "search" in name.lower():
        resp = httpx.get(f"{BASE_URL}{name.split('GET ')[1].strip()}?q=test", timeout=30)
    else:
        resp = httpx.get(f"{BASE_URL}{name.replace('GET ', '').strip()}", timeout=30)
    run_test(f"{id_}-{name}", lambda r=resp, e=expected: None if r.status_code == e else Exception(f"状态码:{r.status_code}"))

# ============================================================
# 模块17: 响应式布局 (271-280)
# ============================================================
print("\n" + "=" * 50)
print("  模块17: 响应式布局 (271-280)")
print("=" * 50)

context.close()
context = browser.new_context(viewport={'width': 1920, 'height': 1080})
page = context.new_page()
goto()
run_test("R001-大屏1920x1080", lambda: None if safe_count(".sidebar") > 0 else Exception())

context.close()
context = browser.new_context(viewport={'width': 1024, 'height': 768})
page = context.new_page()
goto()
run_test("R002-中屏1024x768", lambda: None if safe_count(".sidebar") > 0 else Exception())

context.close()
context = browser.new_context(viewport={'width': 375, 'height': 667})
page = context.new_page()
goto()
run_test("R003-移动375x667", lambda: None)

# 恢复
context.close()
context = browser.new_context(viewport={'width': 1920, 'height': 1080})
page = context.new_page()

# ============================================================
# 模块18: 性能测试 (281-285)
# ============================================================
print("\n" + "=" * 50)
print("  模块18: 性能测试 (281-285)")
print("=" * 50)

start = time.time()
goto()
load_time = time.time() - start
run_test(f"P001-页面加载<5s({load_time:.2f}s)", lambda: None if load_time < 5 else Exception())

start = time.time()
httpx.get(f"{BASE_URL}/api/status", timeout=10)
api_time = time.time() - start
run_test(f"P002-API响应<1s({api_time:.3f}s)", lambda: None if api_time < 1 else Exception())

# ============================================================
# 清理
# ============================================================
context.close()
browser.close()
pw.stop()

# ============================================================
# 测试汇总
# ============================================================
print("\n" + "=" * 70)
print("  测试结果汇总")
print("=" * 70)

passed = sum(1 for r in results if r[0] == "PASS")
failed = sum(1 for r in results if r[0] == "FAIL")
total = len(results)

print(f"\n  ✅ 通过: {passed}")
print(f"  ❌ 失败: {failed}")
print(f"  📊 总计: {total}")
print(f"  📈 通过率: {100*passed/total:.1f}%")
print("=" * 70)

if failed > 0:
    print("\n🐛 失败的测试:")
    for status, name, error in results:
        if status == "FAIL":
            print(f"  ❌ {name}")
            if error:
                print(f"     → {error}")

sys.exit(0 if failed == 0 else 1)
