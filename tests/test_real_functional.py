#!/usr/bin/env python3
"""8866 真实功能测试 — 验证实际业务逻辑而非DOM存在"""
from playwright.sync_api import sync_playwright
import httpx
import json
import os
import sys
import time

BASE_URL = "http://localhost:8866"
UPLOADS = "/root/.openclaw/workspace/learning/uploads"

pw = sync_playwright().start()
browser = pw.chromium.launch(headless=True, args=['--no-sandbox', '--disable-dev-shm-usage'])
page = browser.new_page(viewport={'width': 1920, 'height': 1080})

results = []

def test(name, func):
    try:
        func()
        results.append(("PASS", name))
        print(f"  ✅ {name}")
    except AssertionError as e:
        results.append(("FAIL", name, str(e)))
        print(f"  ❌ {name}: {e}")
    except Exception as e:
        results.append(("FAIL", name, str(e)[:100]))
        print(f"  ❌ {name}: {str(e)[:80]}")

def goto():
    page.goto(f"{BASE_URL}/", wait_until="networkidle", timeout=15000)
    page.wait_for_timeout(2000)

# ============================================================
# 模块1: 文件上传真实流程
# ============================================================
print("\n[1. 文件上传]")

def test_upload_file():
    """上传一个真实文件并验证出现在列表中"""
    # 创建测试文件
    test_file = "/tmp/test_upload_real.txt"
    with open(test_file, "w") as f:
        f.write("这是一个自动化测试文件 " + str(time.time()))
    
    # 打开上传模态框
    page.click('.nav-item[data-view="upload"]')
    page.wait_for_timeout(500)
    
    # 通过file input上传
    page.locator("#fileInput").set_input_files(test_file)
    page.wait_for_timeout(2000)
    
    # 关闭模态框
    page.keyboard.press("Escape")
    page.wait_for_timeout(1000)
    
    # 验证文件出现在列表中
    goto()
    items = page.locator(".file-item").all()
    names = [item.locator(".file-name").inner_text() for item in items]
    assert "test_upload_real.txt" in names, f"上传文件未出现在列表: {names[:5]}"

test("上传文件并验证列表", test_upload_file)


def test_file_detail_correct():
    """点击文件验证详情面板显示正确内容"""
    goto()
    # 点击第一个文件
    first = page.locator(".file-item").first
    fname = first.locator(".file-name").inner_text()
    first.click()
    page.wait_for_timeout(500)
    
    # 验证详情面板显示
    panel = page.locator("#detailPanel.active")
    assert panel.count() > 0, "详情面板未打开"
    
    # 验证文件名正确
    detail_name = panel.locator(".detail-value").first.inner_text()
    assert detail_name == fname, f"详情文件名不匹配: 期望={fname}, 实际={detail_name}"

test("文件详情显示正确", test_file_detail_correct)


def test_detail_panel_close():
    """点击关闭按钮能关闭详情面板"""
    goto()
    page.locator(".file-item").first.click()
    page.wait_for_timeout(500)
    assert page.locator("#detailPanel.active").count() > 0, "详情面板未打开"
    
    # 点击关闭
    page.locator("#detailPanel .icon-btn").click()
    page.wait_for_timeout(300)
    assert page.locator("#detailPanel.active").count() == 0, "详情面板未关闭"

test("详情面板关闭", test_detail_panel_close)

# ============================================================
# 模块2: 导航切换真实验证
# ============================================================
print("\n[2. 导航切换]")

def test_nav_uploads():
    """点击上传记录导航，显示上传目录文件"""
    page.click('.nav-item[data-view="uploads"]')
    page.wait_for_timeout(1000)
    # 验证面包屑或标题变化
    title = page.locator(".content-header h2, .breadcrumb-item.active").first.inner_text()
    assert "上传" in title or "uploads" in title.lower(), f"未切换到上传记录: {title}"

test("导航-上传记录", test_nav_uploads)


def test_nav_downloads():
    """点击下载目录导航"""
    page.click('.nav-item[data-view="downloads"]')
    page.wait_for_timeout(1000)
    title = page.locator(".content-header h2, .breadcrumb-item.active").first.inner_text()
    assert "下载" in title or "downloads" in title.lower() or "目录" in title, f"未切换到下载目录: {title}"

test("导航-下载目录", test_nav_downloads)


def test_nav_transcribe_opens_modal():
    """点击音频转写打开模态框"""
    page.click('.nav-item[data-view="transcribe"]')
    page.wait_for_timeout(500)
    modal = page.locator("#transcribeModal.active")
    assert modal.count() > 0, "转写模态框未打开"
    
    # 验证模态框内容
    assert "转写" in modal.inner_text() or "音频" in modal.inner_text(), "模态框内容不正确"

test("导航-转写模态框", test_nav_transcribe_opens_modal)


def test_nav_knowledge_shows_stats():
    """点击知识导入显示统计数据"""
    page.click('.nav-item[data-view="knowledge"]')
    page.wait_for_timeout(2000)
    modal = page.locator("#knowledgeModal.active")
    assert modal.count() > 0, "知识模态框未打开"
    
    text = modal.inner_text()
    # 应该显示待导入数量
    assert "待导入" in text or "已导入" in text, f"知识模态框无统计: {text[:200]}"

test("导航-知识导入统计", test_nav_knowledge_shows_stats)


def test_nav_cloud_shows_disks():
    """点击云盘管理显示网盘列表"""
    page.click('.nav-item[data-view="cloud"]')
    page.wait_for_timeout(2000)
    modal = page.locator("#cloudModal.active")
    assert modal.count() > 0, "云盘模态框未打开"
    
    text = modal.inner_text()
    # 应该有网盘名称
    assert "网盘" in text or "_td" in text or "_dup" in text, f"云盘列表为空: {text[:200]}"

test("导航-云盘列表", test_nav_cloud_shows_disks)

# ============================================================
# 模块3: 搜索功能真实验证
# ============================================================
print("\n[3. 搜索功能]")

def test_search_filters_files():
    """输入搜索词后文件列表过滤"""
    goto()
    original_count = page.locator(".file-item").count()
    
    # 搜索 pdf
    page.fill("#searchInput", "pdf")
    page.wait_for_timeout(1000)
    
    filtered_count = page.locator(".file-item").count()
    assert filtered_count < original_count, f"搜索未过滤: 之前={original_count}, 之后={filtered_count}"
    
    # 清空搜索
    page.fill("#searchInput", "")
    page.wait_for_timeout(1000)
    restored_count = page.locator(".file-item").count()
    assert restored_count >= filtered_count, "清空搜索后未恢复"

test("搜索过滤文件", test_search_filters_files)


def test_search_no_results():
    """搜索不存在的关键词显示空状态"""
    goto()
    page.fill("#searchInput", "xyznonexistent12345")
    page.wait_for_timeout(1000)
    
    count = page.locator(".file-item").count()
    # 可能显示空状态或0个文件
    assert count == 0 or page.locator(".empty-state").count() > 0, f"搜索无结果时未显示空状态: {count} items"

test("搜索无结果", test_search_no_results)

# ============================================================
# 模块4: 文件选中和批量操作
# ============================================================
print("\n[4. 文件选中]")

def test_select_single():
    """单击文件选中，工具栏按钮启用"""
    goto()
    first = page.locator(".file-item").first
    first.click()
    page.wait_for_timeout(300)
    
    # 验证选中
    assert "selected" in (first.get_attribute("class") or ""), "文件未选中"
    
    # 验证计数
    count_text = page.locator("#selectedCount").inner_text()
    assert "1" in count_text, f"选中计数错误: {count_text}"
    
    # 验证按钮启用
    assert not page.locator("#btnDelete").is_disabled(), "删除按钮未启用"
    assert not page.locator("#btnDownload").is_disabled(), "下载按钮未启用"

test("单选文件", test_select_single)


def test_select_toggle():
    """再次点击取消选中"""
    goto()
    first = page.locator(".file-item").first
    first.click()
    page.wait_for_timeout(300)
    assert "selected" in (first.get_attribute("class") or ""), "第一次未选中"
    
    first.click()
    page.wait_for_timeout(300)
    # 取消选中后按钮应禁用
    assert page.locator("#btnDelete").is_disabled(), "取消选中后删除按钮未禁用"

test("取消选中", test_select_toggle)


def test_select_all():
    """全选功能"""
    goto()
    # 点击全选
    page.locator("#selectAll").click()
    page.wait_for_timeout(500)
    
    count_text = page.locator("#selectedCount").inner_text()
    # 应该显示全部文件数
    assert "项已选中" in count_text, f"全选计数错误: {count_text}"
    
    # 所有文件应选中
    selected = page.locator(".file-item.selected").count()
    total = page.locator(".file-item").count()
    assert selected == total, f"全选不完整: 选中={selected}, 总数={total}"

test("全选功能", test_select_all)

# ============================================================
# 模块5: 视图切换
# ============================================================
print("\n[5. 视图切换]")

def test_list_view():
    """切换到列表视图"""
    goto()
    page.click('.view-toggle button[data-view="list"]')
    page.wait_for_timeout(500)
    
    # 验证列表视图激活
    list_btn = page.locator('.view-toggle button[data-view="list"]')
    assert "active" in (list_btn.get_attribute("class") or ""), "列表按钮未激活"
    
    # 验证文件项布局变化
    first_item = page.locator(".file-item").first
    display = first_item.evaluate("el => getComputedStyle(el).display")
    assert display == "flex", f"列表视图布局错误: {display}"

test("列表视图", test_list_view)


def test_grid_view():
    """切换回网格视图"""
    page.click('.view-toggle button[data-view="grid"]')
    page.wait_for_timeout(500)
    
    grid_btn = page.locator('.view-toggle button[data-view="grid"]')
    assert "active" in (grid_btn.get_attribute("class") or ""), "网格按钮未激活"

test("网格视图", test_grid_view)

# ============================================================
# 模块6: API真实验证
# ============================================================
print("\n[6. API验证]")

def test_api_files_structure():
    """验证文件API返回正确结构"""
    resp = httpx.get(f"{BASE_URL}/api/files", timeout=10)
    assert resp.status_code == 200
    data = resp.json()
    assert "items" in data, f"API缺少items字段: {data.keys()}"
    assert len(data["items"]) > 0, "文件列表为空"
    
    # 验证文件结构
    item = data["items"][0]
    assert "name" in item, f"文件缺少name: {item.keys()}"
    assert "size" in item, f"文件缺少size: {item.keys()}"
    assert "path" in item, f"文件缺少path: {item.keys()}"

test("API文件结构", test_api_files_structure)


def test_api_storage_stats():
    """验证存储统计API"""
    resp = httpx.get(f"{BASE_URL}/api/storage/stats", timeout=10)
    assert resp.status_code == 200
    data = resp.json()
    assert "uploads_size" in data, f"缺少uploads_size: {data.keys()}"
    assert data["uploads_size"] > 0, f"存储大小为0: {data['uploads_size']}"
    assert data["uploads_count"] > 0, f"文件数为0: {data['uploads_count']}"

test("API存储统计", test_api_storage_stats)


def test_api_knowledge_stats():
    """验证知识统计API"""
    resp = httpx.get(f"{BASE_URL}/api/knowledge/stats", timeout=10)
    assert resp.status_code == 200
    data = resp.json()
    assert "pending" in data, f"缺少pending: {data.keys()}"
    assert "total" in data, f"缺少total: {data.keys()}"
    assert data["total"] > 0, f"知识文件总数为0"

test("API知识统计", test_api_knowledge_stats)


def test_api_disks():
    """验证云盘API"""
    resp = httpx.get(f"{BASE_URL}/api/disks", timeout=10)
    assert resp.status_code == 200
    data = resp.json()
    assert "disks" in data, f"缺少disks: {data.keys()}"
    assert len(data["disks"]) > 0, "云盘列表为空"
    
    disk = data["disks"][0]
    assert "name" in disk, f"云盘缺少name: {disk.keys()}"
    assert "type" in disk, f"云盘缺少type: {disk.keys()}"

test("API云盘列表", test_api_disks)


def test_api_files_search():
    """验证文件搜索API"""
    resp = httpx.get(f"{BASE_URL}/api/files/search?q=pdf", timeout=10)
    assert resp.status_code == 200
    data = resp.json()
    assert "items" in data or "results" in data, f"搜索API结构异常: {data.keys()}"

test("API文件搜索", test_api_files_search)

# ============================================================
# 模块7: 模态框交互
# ============================================================
print("\n[7. 模态框交互]")

def test_upload_modal_flow():
    """上传模态框完整流程"""
    page.click('.nav-item[data-view="upload"]')
    page.wait_for_timeout(500)
    
    modal = page.locator("#uploadModal.active")
    assert modal.count() > 0, "上传模态框未打开"
    
    # 验证拖拽区
    dropzone = modal.locator("#uploadDropzone, .upload-dropzone")
    assert dropzone.count() > 0, "拖拽区不存在"
    
    # 验证文件选择按钮
    btn = modal.locator("text=选择文件, text=选择")
    assert btn.count() > 0, "选择文件按钮不存在"
    
    # Escape关闭
    page.keyboard.press("Escape")
    page.wait_for_timeout(300)
    assert page.locator("#uploadModal.active").count() == 0, "模态框未关闭"

test("上传模态框流程", test_upload_modal_flow)


def test_cloud_modal_tabs():
    """云盘模态框标签页切换"""
    page.click('.nav-item[data-view="cloud"]')
    page.wait_for_timeout(2000)
    
    # 点击同步任务标签
    page.click("text=同步任务")
    page.wait_for_timeout(500)
    
    # 验证标签切换
    sync_tab = page.locator('[data-tab="sync"]')
    assert "active" in (sync_tab.get_attribute("class") or ""), "同步任务标签未激活"
    
    # 点击添加网盘标签
    page.click("text=添加网盘")
    page.wait_for_timeout(500)
    
    # 验证表单出现
    name_input = page.locator("#diskName, input[placeholder*='名称']")
    assert name_input.count() > 0, "添加网盘表单未显示"

test("云盘标签切换", test_cloud_modal_tabs)


def test_knowledge_file_list():
    """知识导入文件列表加载"""
    page.click('.nav-item[data-view="knowledge"]')
    page.wait_for_timeout(2000)
    
    # 验证文件列表有内容
    file_items = page.locator("#knowledgeFileList .knowledge-file-item, .knowledge-file-item")
    assert file_items.count() > 0, "知识文件列表为空"
    
    # 验证有复选框
    checkbox = file_items.first.locator("input[type='checkbox']")
    assert checkbox.count() > 0, "知识文件无复选框"

test("知识文件列表", test_knowledge_file_list)

# ============================================================
# 模块8: 响应式测试
# ============================================================
print("\n[8. 响应式]")

def test_mobile_sidebar():
    """移动端侧边栏"""
    page.set_viewport_size({"width": 375, "height": 667})
    page.wait_for_timeout(500)
    
    # 侧边栏应该隐藏或缩小
    sidebar = page.locator(".sidebar")
    width = sidebar.evaluate("el => el.getBoundingClientRect().width")
    assert width < 300, f"移动端侧边栏过宽: {width}px"
    
    # 恢复
    page.set_viewport_size({"width": 1920, "height": 1080})

test("移动端布局", test_mobile_sidebar)

# ============================================================
# 汇总
# ============================================================
print("\n" + "=" * 60)
passed = sum(1 for r in results if r[0] == "PASS")
failed = sum(1 for r in results if r[0] == "FAIL")
print(f"  ✅ 通过: {passed}")
print(f"  ❌ 失败: {failed}")
print(f"  📊 总计: {len(results)}")
print(f"  📈 通过率: {passed/len(results)*100:.1f}%")

if failed > 0:
    print("\n  失败用例:")
    for r in results:
        if r[0] == "FAIL":
            print(f"    ❌ {r[1]}: {r[2]}")

browser.close()
pw.stop()
sys.exit(0 if failed == 0 else 1)
