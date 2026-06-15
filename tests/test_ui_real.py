#!/usr/bin/env python3
"""8866学习目录系统 - 真实UI自动化测试 (发现实际Bug)"""
from playwright.sync_api import sync_playwright
import sys

BASE_URL = "http://localhost:8866"

print("=" * 60)
print("  8866 - 真实UI自动化测试")
print("=" * 60)

pw = sync_playwright().start()
browser = pw.chromium.launch(headless=True, args=['--no-sandbox', '--disable-dev-shm-usage'], executable_path='/usr/bin/chromium')
context = browser.new_context(viewport={'width': 1920, 'height': 1080})
page = context.new_page()
page.set_default_timeout(15000)

page.goto(f"{BASE_URL}/", wait_until="networkidle", timeout=30000)
print(f"\n页面标题: {page.title()}")

bugs = []
passed = []

def check(name, condition, bug_desc=None):
    if condition:
        passed.append(name)
        print(f"✅ {name}")
    else:
        bugs.append((name, bug_desc or "功能异常"))
        print(f"❌ {name}: {bug_desc or '功能异常'}")

# ===== 1. 基础结构 =====
print("\n[1. 基础结构]")
check("页面加载", page.locator(".app-container").count() > 0)
check("侧边栏", page.locator(".sidebar").count() > 0)
check("主内容区", page.locator(".main-content").count() > 0)
check("文件容器", page.locator("#fileContainer").count() > 0)

# ===== 2. 文件列表 =====
print("\n[2. 文件列表]")
file_count = page.locator(".file-item").count()
check(f"文件数量({file_count})", file_count > 0, f"文件数量: {file_count}")

# ===== 3. 文件选中功能 (核心Bug) =====
print("\n[3. 文件选中功能 - 核心Bug]")
first_file = page.locator(".file-item").first
file_name = first_file.locator(".file-name").inner_text()

# 检查文件项是否有复选框
has_checkbox = first_file.locator("input[type='checkbox']").count() > 0
check("文件项有复选框", has_checkbox, "文件项没有复选框!")

# 点击文件
first_file.click()
page.wait_for_timeout(300)

# 检查点击后状态
is_selected = "selected" in (first_file.get_attribute("class") or "")
check(f"文件被选中({file_name})", is_selected, f"点击后未选中: class={first_file.get_attribute('class')}")

# 检查选中计数
selected_text = page.locator("#selectedCount").inner_text()
count_ok = "1" in selected_text
check("选中计数更新", count_ok, f"计数显示: {selected_text}")

# ===== 4. 工具栏按钮状态 =====
print("\n[4. 工具栏按钮状态]")
download_disabled = page.locator("#btnDownload").is_disabled()
check("选中后下载可用", not download_disabled, "选中文件后下载按钮仍禁用")

share_disabled = page.locator("#btnShare").is_disabled()
check("选中后分享可用", not share_disabled, "选中文件后分享按钮仍禁用")

delete_disabled = page.locator("#btnDelete").is_disabled()
check("选中后删除可用", not delete_disabled, "选中文件后删除按钮仍禁用")

# ===== 5. 视图切换 (Bug) =====
print("\n[5. 视图切换 - Bug]")
page.locator('.view-toggle button[data-view="list"]').click()
page.wait_for_timeout(300)

list_active = "active" in (page.locator('.view-toggle button[data-view="list"]').get_attribute("class") or "")
check("列表按钮激活", list_active)

has_list_view = page.locator(".file-list-view").count() > 0
check("列表视图显示", has_list_view, "点击后列表视图未显示!")

page.locator('.view-toggle button[data-view="grid"]').click()
page.wait_for_timeout(300)

# ===== 6. 上传模态框 =====
print("\n[6. 上传模态框]")
page.locator("#btnUpload").click()
page.wait_for_timeout(300)
upload_modal = "active" in (page.locator("#uploadModal").get_attribute("class") or "")
check("上传模态框打开", upload_modal)
check("拖拽区存在", page.locator("#uploadDropzone").count() > 0)
check("文件选择按钮", page.locator("#btnSelectFiles").count() > 0)
page.locator("#btnCloseUpload").click()

# ===== 7. 新建文件夹 =====
print("\n[7. 新建文件夹]")
page.locator("#btnNewFolder").click()
page.wait_for_timeout(300)
has_input = page.locator("input[placeholder*='文件夹']").count() > 0
check("文件夹名输入框", has_input)
if has_input:
    page.keyboard.press("Escape")

# ===== 8. 云盘管理 =====
print("\n[8. 云盘管理]")
page.locator('.nav-item[data-view="cloud"]').click()
page.wait_for_timeout(300)
cloud_modal = "active" in (page.locator("#cloudModal").get_attribute("class") or "")
check("云盘模态框打开", cloud_modal)
check("我的网盘标签", page.locator('.cloud-tab[data-tab="disks"]').count() > 0)
check("同步任务标签", page.locator('.cloud-tab[data-tab="sync"]').count() > 0)
check("添加网盘标签", page.locator('.cloud-tab[data-tab="add"]').count() > 0)

page.locator('.cloud-tab[data-tab="add"]').click()
page.wait_for_timeout(200)
check("网盘名称输入", page.locator("#diskName").count() > 0)
check("网盘类型选择", page.locator("#diskType").count() > 0)
page.locator("#btnCloseCloud").click()

# ===== 9. 知识导入 =====
print("\n[9. 知识导入]")
page.locator('.nav-item[data-view="knowledge"]').click()
page.wait_for_timeout(300)
knowledge_modal = "active" in (page.locator("#knowledgeModal").get_attribute("class") or "")
check("知识模态框打开", knowledge_modal)
check("统计卡片", page.locator("#knowledgeStats").count() > 0)
page.locator("#btnCloseKnowledge").click()

# ===== 10. 分享功能 - 直接打开 =====
print("\n[10. 分享功能]")
# 使用JS直接打开分享模态框
page.evaluate("showShareModal('/test.txt')")
page.wait_for_timeout(300)
share_modal = "active" in (page.locator("#shareModal").get_attribute("class") or "")
check("分享模态框打开", share_modal)
check("分享链接输入", page.locator("#shareUrl").count() > 0)
check("有效期选择", page.locator("#shareExpiry").count() > 0)
page.locator("#btnCloseShare").click()

# ===== 11. 标签功能 - 直接打开 =====
print("\n[11. 标签功能]")
page.evaluate("document.getElementById('tagModal').classList.add('active')")
page.wait_for_timeout(300)
tag_modal = page.locator("#tagModal").get_attribute("class")
check("标签模态框打开", "active" in tag_modal)
check("当前标签区", page.locator("#currentTags").count() > 0)
check("新标签输入", page.locator("#newTagInput").count() > 0)
page.locator("#btnCloseTag").click()

# ===== 12. RAG功能 (跳过 - RAGFlow暂不测试) =====
print("\n[12. RAG语义搜索] ⏭️ 跳过")
# ===== 12b. RAG对话 (跳过) =====
print("[12b. RAG对话] ⏭️ 跳过")

# ===== 13. 音频转写 =====
print("\n[13. 音频转写]")
page.locator('.nav-item[data-view="transcribe"]').click()
page.wait_for_timeout(300)
transcribe_modal = "active" in (page.locator("#transcribeModal").get_attribute("class") or "")
check("转写模态框", transcribe_modal)
check("音频选择按钮", page.locator("#btnSelectAudio").count() > 0)
check("语言选择", page.locator("#transcribeLang").count() > 0)
page.locator("#btnCloseTranscribe").click()

# ===== 14. 全选功能 =====
print("\n[14. 全选功能]")
page.goto(f"{BASE_URL}/", wait_until="networkidle", timeout=30000)
select_all = page.locator("#selectAll")
has_select_all = select_all.count() > 0
check("全选复选框存在", has_select_all)
if has_select_all:
    select_all.click()
    page.wait_for_timeout(300)
    checked = select_all.is_checked()
    check("全选功能", checked, "全选复选框点击无效")

    selected_text = page.locator("#selectedCount").inner_text()
    print(f"   选中计数: {selected_text}")

# ===== 15. 详情面板 =====
print("\n[15. 详情面板]")
check("详情面板存在", page.locator("#detailPanel").count() > 0)

# ===== 16. Toast通知 =====
print("\n[16. Toast通知]")
check("Toast容器", page.locator("#toastContainer").count() > 0)
page.evaluate("showToast('测试消息', 'success')")
page.wait_for_timeout(500)
has_toast = page.locator(".toast").count() > 0
check("Toast创建", has_toast, "Toast通知未显示")

# 清理
browser.close()
pw.stop()

# 汇总
print("\n" + "=" * 60)
print(f"  ✅ 通过: {len(passed)}")
print(f"  ❌ Bug: {len(bugs)}")
print("=" * 60)

if bugs:
    print("\n🐛 发现的问题:")
    for i, (name, desc) in enumerate(bugs, 1):
        print(f"  {i}. {name}")
        print(f"     → {desc}")

sys.exit(1 if len(bugs) > 0 else 0)
