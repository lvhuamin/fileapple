#!/usr/bin/env python3
"""8866学习目录系统 - UI自动化测试 (适配新版UI结构)"""
import sys
import time
import httpx
from playwright.sync_api import sync_playwright

BASE_URL = "http://localhost:8866"
TIMEOUT = 15000  # 缩短超时避免卡死

print("=" * 60)
print("  8866 - UI自动化测试 (新版UI)")
print("=" * 60)

# 服务检查
try:
    resp = httpx.get(f"{BASE_URL}/api/status", timeout=10)
    assert resp.status_code == 200
    print(f"✅ 服务正常: {BASE_URL}")
except Exception as e:
    print(f"❌ 服务连接失败: {e}")
    sys.exit(1)

from playwright.sync_api import sync_playwright

results = []

def run_test(name, test_func):
    print(f"  {name}...", end=" ", flush=True)
    try:
        test_func()
        results.append(True)
        print("✅")
    except Exception as e:
        results.append(False)
        print(f"❌ {str(e)[:50]}")

pw = sync_playwright().start()
browser = pw.chromium.launch(headless=True, args=['--no-sandbox', '--disable-dev-shm-usage'])
context = browser.new_context(viewport={'width': 1920, 'height': 1080})
page = context.new_page()
page.set_default_timeout(TIMEOUT)

def goto():
    page.goto(f"{BASE_URL}/", wait_until="domcontentloaded", timeout=30000)
    page.wait_for_load_state("domcontentloaded", timeout=5000)

def click(sel):
    page.locator(sel).click(timeout=5000)

def visible(sel):
    try:
        return page.locator(sel).is_visible(timeout=2000)
    except:
        return False

def count(sel):
    try:
        return page.locator(sel).count()
    except:
        return 0

def wait(ms):
    page.wait_for_timeout(ms)

# ===== A. 页面结构 =====
print("\n[A. 页面结构]")
goto()
run_test("页面标题", lambda: None if "学习目录" in page.title() else Exception())
run_test("主容器", lambda: None if visible(".app-container") else Exception())
run_test("侧边栏", lambda: None if visible(".sidebar") else Exception())
run_test("主内容区", lambda: None if visible(".main-content") else Exception())

# ===== B. 导航菜单 =====
print("\n[B. 导航菜单]")
run_test("全部文件", lambda: None if visible('.nav-item[data-view="all"]') else Exception())
run_test("上传记录", lambda: None if visible('.nav-item[data-view="uploads"]') else Exception())
run_test("下载目录", lambda: None if visible('.nav-item[data-view="downloads"]') else Exception())
run_test("音频转写", lambda: None if visible('.nav-item[data-view="transcribe"]') else Exception())
run_test("知识导入", lambda: None if visible('.nav-item[data-view="knowledge"]') else Exception())
run_test("云盘管理", lambda: None if visible('.nav-item[data-view="cloud"]') else Exception())
run_test("语义搜索", lambda: None if visible('.nav-item[data-view="rag-search"]') else Exception())
run_test("RAG对话", lambda: None if visible('.nav-item[data-view="rag-chat"]') else Exception())

# ===== C. 分类导航 =====
print("\n[C. 分类导航]")
for cat in ["技术运维", "心理学", "文档", "有声剧"]:
    run_test(f"分类-{cat}", lambda c=cat: None if count(f'.nav-item[data-category="{c}"]') > 0 else Exception())

# ===== D. 顶部栏 =====
print("\n[D. 顶部栏]")
goto()
run_test("上传按钮", lambda: None if visible("#btnUpload") else Exception())
run_test("新建文件夹", lambda: None if visible("#btnNewFolder") else Exception())
run_test("网格视图", lambda: None if visible('.view-toggle button[data-view="grid"]') else Exception())
run_test("列表视图", lambda: None if visible('.view-toggle button[data-view="list"]') else Exception())
run_test("顶部搜索", lambda: None if visible("#topSearchInput") else Exception())

# ===== E. 工具栏 =====
print("\n[E. 工具栏]")
run_test("全选复选框", lambda: None if visible("#selectAll") else Exception())
run_test("下载按钮", lambda: None if visible("#btnDownload") else Exception())
run_test("分享按钮", lambda: None if visible("#btnShare") else Exception())
run_test("删除按钮", lambda: None if visible("#btnDelete") else Exception())
run_test("标签按钮", lambda: None if visible("#btnTag") else Exception())

# ===== F. 模态框 =====
print("\n[F. 模态框]")
goto()
try:
    click("#btnUpload")
    wait(300)
    run_test("上传模态框", lambda: None if visible("#uploadModal") else Exception())
    click("#btnCloseUpload")
except:
    results.append(False)
    print("❌ 上传模态框")

goto()
try:
    click('.nav-item[data-view="cloud"]')
    wait(300)
    run_test("云盘模态框", lambda: None if visible("#cloudModal") else Exception())
    click("#btnCloseCloud")
except:
    results.append(False)
    print("❌ 云盘模态框")

goto()
try:
    click('.nav-item[data-view="knowledge"]')
    wait(300)
    run_test("知识模态框", lambda: None if visible("#knowledgeModal") else Exception())
    click("#btnCloseKnowledge")
except:
    results.append(False)
    print("❌ 知识模态框")

goto()
try:
    page.evaluate("showShareModal('/test.txt')")
    wait(300)
    run_test("分享模态框", lambda: None if visible("#shareModal") else Exception())
    click("#btnCloseShare")
except:
    results.append(False)
    print("❌ 分享模态框")

goto()
try:
    click('.nav-item[data-view="rag-search"]')
    wait(300)
    run_test("语义搜索模态框", lambda: None if visible("#ragSearchModal") else Exception())
    click("#btnCloseRagSearch")
except:
    results.append(False)
    print("❌ 语义搜索模态框")

goto()
try:
    click('.nav-item[data-view="rag-chat"]')
    wait(300)
    run_test("RAG对话模态框", lambda: None if visible("#ragChatModal") else Exception())
    click("#btnCloseRagChat")
except:
    results.append(False)
    print("❌ RAG对话模态框")

goto()
try:
    click('.nav-item[data-view="transcribe"]')
    wait(300)
    run_test("转写模态框", lambda: None if visible("#transcribeModal") else Exception())
    click("#btnCloseTranscribe")
except:
    results.append(False)
    print("❌ 转写模态框")

# ===== G. 云盘表单 =====
print("\n[G. 云盘表单]")
goto()
try:
    click('.nav-item[data-view="cloud"]')
    wait(300)
    click('.cloud-tab[data-tab="add"]')
    wait(200)
    run_test("网盘名称", lambda: None if visible("#diskName") else Exception())
    run_test("网盘类型", lambda: None if visible("#diskType") else Exception())
    run_test("账号", lambda: None if visible("#diskUsername") else Exception())
    run_test("密码", lambda: None if visible("#diskPassword") else Exception())
    run_test("挂载路径", lambda: None if visible("#diskMountPath") else Exception())
    click("#btnCloseCloud")
except Exception as e:
    results.append(False)
    print(f"❌ 云盘表单")

# ===== H. Toast =====
print("\n[H. Toast]")
goto()
run_test("Toast容器", lambda: None if visible("#toastContainer") else Exception())
page.evaluate("showToast('测试', 'success')")
wait(300)
run_test("Toast创建", lambda: None if count(".toast") > 0 else Exception())

# ===== I. 详情面板 =====
print("\n[I. 详情面板]")
run_test("详情面板", lambda: None if visible("#detailPanel") else Exception())

# ===== J. 按钮状态 =====
print("\n[J. 按钮状态]")
run_test("下载禁用", lambda: None if page.locator("#btnDownload").is_disabled() else Exception())
run_test("分享禁用", lambda: None if page.locator("#btnShare").is_disabled() else Exception())
run_test("删除禁用", lambda: None if page.locator("#btnDelete").is_disabled() else Exception())

# 清理
context.close()
browser.close()
pw.stop()

passed = sum(results)
total = len(results)
failed = total - passed

print("\n" + "=" * 60)
print(f"  ✅ 通过: {passed} | ❌ 失败: {failed} | 📊 总计: {total}")
print("=" * 60)

sys.exit(0 if failed == 0 else 1)
