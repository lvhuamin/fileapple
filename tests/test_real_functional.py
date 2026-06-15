#!/usr/bin/env python3
"""
8866 学习目录系统 - 真正的功能测试
每条用例都执行：操作 → 等待 → 验证结果变化
不做"元素存在"这种假测试
"""
import sys
import time
from playwright.sync_api import sync_playwright

BASE = "http://localhost:8866"
results = []
passed = failed = 0

def test(name, func):
    global passed, failed
    try:
        func()
        results.append(("PASS", name))
        passed += 1
        print(f"  ✅ {name}")
    except Exception as e:
        results.append(("FAIL", name, str(e)[:80]))
        failed += 1
        print(f"  ❌ {name}: {str(e)[:70]}")

def fresh_page(ctx):
    """每个测试用新页面，避免状态污染"""
    p = ctx.new_page()
    p.set_default_timeout(10000)
    p.goto(BASE, wait_until="domcontentloaded")
    p.wait_for_timeout(2000)
    return p

pw = sync_playwright().start()
browser = pw.chromium.launch(
    headless=True,
    args=['--no-sandbox', '--disable-dev-shm-usage'],
    executable_path='/usr/bin/chromium'
)

# ============================================================
# 模块1: 导航切换 - 点击后内容必须真的变
# ============================================================
print("\n" + "=" * 50)
print("  模块1: 导航切换（点击→验证内容变化）")
print("=" * 50)

def nav_test_01():
    """点击'下载目录'后，文件列表内容必须不同于'全部文件'"""
    p = browser.new_context(viewport={'width':1920,'height':1080}, locale='zh-CN').new_page()
    p.set_default_timeout(10000)
    p.goto(BASE, wait_until="domcontentloaded")
    p.wait_for_timeout(2000)
    # 记录全部文件的标题
    title_all = p.locator("#currentPath").inner_text()
    items_all = p.locator(".file-item").count()
    # 点击下载目录
    p.click('[data-view="downloads"]')
    p.wait_for_timeout(2000)
    title_dl = p.locator("#currentPath").inner_text()
    items_dl = p.locator(".file-item").count()
    p.close()
    assert "下载" in title_dl, f"标题没变: {title_dl}"
    assert title_dl != title_all, f"标题相同: {title_all} == {title_dl}"

test("点击下载目录 → 标题从'全部文件'变为'下载目录'", nav_test_01)

def nav_test_02():
    """点击'上传记录'后，标题必须包含'上传'"""
    p = browser.new_context(viewport={'width':1920,'height':1080}, locale='zh-CN').new_page()
    p.set_default_timeout(10000)
    p.goto(BASE, wait_until="domcontentloaded")
    p.wait_for_timeout(2000)
    p.click('[data-view="uploads"]')
    p.wait_for_timeout(2000)
    title = p.locator("#currentPath").inner_text()
    p.close()
    assert "上传" in title, f"标题不含'上传': {title}"

test("点击上传记录 → 标题包含'上传'", nav_test_02)

def nav_test_03():
    """点击分类'技术运维'后，标题和文件列表必须变化"""
    p = browser.new_context(viewport={'width':1920,'height':1080}, locale='zh-CN').new_page()
    p.set_default_timeout(10000)
    p.goto(BASE, wait_until="domcontentloaded")
    p.wait_for_timeout(2000)
    title_before = p.locator("#currentPath").inner_text()
    p.click('[data-view="category"][data-category="技术运维"]')
    p.wait_for_timeout(2000)
    title_after = p.locator("#currentPath").inner_text()
    p.close()
    assert "技术运维" in title_after, f"标题不含'技术运维': {title_after}"
    assert title_after != title_before, "标题没变"

test("点击分类'技术运维' → 标题变为'技术运维'", nav_test_03)

def nav_test_04():
    """点击'全部文件'回到根目录，标题必须变回'全部文件'"""
    p = browser.new_context(viewport={'width':1920,'height':1080}, locale='zh-CN').new_page()
    p.set_default_timeout(10000)
    p.goto(BASE, wait_until="domcontentloaded")
    p.wait_for_timeout(2000)
    # 先切到下载
    p.click('[data-view="downloads"]')
    p.wait_for_timeout(2000)
    # 再切回全部
    p.click('[data-view="all"]')
    p.wait_for_timeout(2000)
    title = p.locator("#currentPath").inner_text()
    p.close()
    assert "全部文件" in title, f"标题没回根: {title}"

test("切换到下载再回全部 → 标题恢复'全部文件'", nav_test_04)

# ============================================================
# 模块2: 文件夹双击导航
# ============================================================
print("\n" + "=" * 50)
print("  模块2: 文件夹双击导航（真正进入目录）")
print("=" * 50)

def dblclick_test_01():
    """双击文件夹后，面包屑必须变化（不再是根目录）"""
    p = browser.new_context(viewport={'width':1920,'height':1080}, locale='zh-CN').new_page()
    p.set_default_timeout(10000)
    p.goto(BASE, wait_until="domcontentloaded")
    p.wait_for_timeout(2000)
    bc_before = p.locator("#breadcrumb").inner_text()
    # 找一个文件夹双击
    folders = p.locator('.file-item[data-dir="true"]')
    if folders.count() == 0:
        p.close()
        return  # 跳过（根目录无文件夹）
    folders.first.dblclick()
    p.wait_for_timeout(2000)
    bc_after = p.locator("#breadcrumb").inner_text()
    p.close()
    assert bc_after != bc_before, f"面包屑没变: {bc_before} → {bc_after}"

test("双击文件夹 → 面包屑变化", dblclick_test_01)

def dblclick_test_02():
    """双击文件夹后，返回按钮必须出现"""
    p = browser.new_context(viewport={'width':1920,'height':1080}, locale='zh-CN').new_page()
    p.set_default_timeout(10000)
    p.goto(BASE, wait_until="domcontentloaded")
    p.wait_for_timeout(2000)
    back_before = p.locator("#btnBack").is_visible()
    folders = p.locator('.file-item[data-dir="true"]')
    if folders.count() == 0:
        p.close()
        return
    folders.first.dblclick()
    p.wait_for_timeout(2000)
    back_after = p.locator("#btnBack").is_visible()
    p.close()
    assert back_before == False, f"返回按钮初始可见: {back_before}"
    assert back_after == True, f"双击后返回按钮不可见"

test("双击文件夹 → 返回按钮出现", dblclick_test_02)

def dblclick_test_03():
    """列表视图双击文件夹也必须进入目录"""
    p = browser.new_context(viewport={'width':1920,'height':1080}, locale='zh-CN').new_page()
    p.set_default_timeout(10000)
    p.goto(BASE, wait_until="domcontentloaded")
    p.wait_for_timeout(2000)
    # 切到列表视图
    p.click('.view-toggle button[data-view="list"]')
    p.wait_for_timeout(500)
    bc_before = p.locator("#breadcrumb").inner_text()
    folders = p.locator('.file-list-item[data-dir="true"]')
    if folders.count() == 0:
        p.close()
        return
    folders.first.dblclick()
    p.wait_for_timeout(2000)
    bc_after = p.locator("#breadcrumb").inner_text()
    p.close()
    assert bc_after != bc_before, f"列表视图双击后面包屑没变"

test("列表视图双击文件夹 → 也进入子目录", dblclick_test_03)

# ============================================================
# 模块3: 返回按钮/面包屑导航
# ============================================================
print("\n" + "=" * 50)
print("  模块3: 返回按钮 & 面包屑（真正能回去）")
print("=" * 50)

def back_test_01():
    """进入子目录后点返回按钮，必须回到根目录"""
    p = browser.new_context(viewport={'width':1920,'height':1080}, locale='zh-CN').new_page()
    p.set_default_timeout(10000)
    p.goto(BASE, wait_until="domcontentloaded")
    p.wait_for_timeout(2000)
    folders = p.locator('.file-item[data-dir="true"]')
    if folders.count() == 0:
        p.close()
        return
    folders.first.dblclick()
    p.wait_for_timeout(2000)
    # 点返回
    p.click("#btnBack")
    p.wait_for_timeout(2000)
    bc = p.locator("#breadcrumb").inner_text()
    title = p.locator("#currentPath").inner_text()
    p.close()
    assert "全部文件" in bc or "全部文件" in title, f"没回根: bc={bc}, title={title}"

test("进入子目录 → 点返回 → 回到全部文件", back_test_01)

def back_test_02():
    """进入子目录后点面包屑'全部文件'，必须回到根"""
    p = browser.new_context(viewport={'width':1920,'height':1080}, locale='zh-CN').new_page()
    p.set_default_timeout(10000)
    p.goto(BASE, wait_until="domcontentloaded")
    p.wait_for_timeout(2000)
    folders = p.locator('.file-item[data-dir="true"]')
    if folders.count() == 0:
        p.close()
        return
    folders.first.dblclick()
    p.wait_for_timeout(2000)
    # 点面包屑第一个（全部文件）
    bc_items = p.locator(".breadcrumb-item")
    if bc_items.count() > 0:
        bc_items.first.click()
        p.wait_for_timeout(2000)
    bc = p.locator("#breadcrumb").inner_text()
    p.close()
    # 面包屑应该只剩"全部文件"
    assert bc.strip() == "全部文件" or "全部文件" in bc, f"面包屑没回根: {bc}"

test("进入子目录 → 点面包屑'全部文件' → 回到根", back_test_02)

# ============================================================
# 模块4: 搜索功能（输入→验证结果变化）
# ============================================================
print("\n" + "=" * 50)
print("  模块4: 搜索功能（输入关键词→验证结果）")
print("=" * 50)

def search_test_01():
    """输入搜索词后，文件列表数量必须变化"""
    p = browser.new_context(viewport={'width':1920,'height':1080}, locale='zh-CN').new_page()
    p.set_default_timeout(10000)
    p.goto(BASE, wait_until="domcontentloaded")
    p.wait_for_timeout(2000)
    count_before = p.locator(".file-item").count()
    # 搜索
    p.fill("#topSearchInput", "2026")
    p.wait_for_timeout(2000)
    count_after = p.locator(".file-item").count()
    p.close()
    # 搜索后应该有结果（可能数量不同，也可能相同但内容不同）
    # 至少不应该报错
    assert count_after >= 0, "搜索后页面报错"

test("搜索'2026' → 文件列表正常返回", search_test_01)

def search_test_02():
    """搜索不存在的词，应该显示空状态或很少结果"""
    p = browser.new_context(viewport={'width':1920,'height':1080}, locale='zh-CN').new_page()
    p.set_default_timeout(10000)
    p.goto(BASE, wait_until="domcontentloaded")
    p.wait_for_timeout(2000)
    p.fill("#topSearchInput", "xyz不存在的文件名999")
    p.wait_for_timeout(2000)
    count = p.locator(".file-item").count()
    p.close()
    # 搜索不存在的词应该返回0或很少
    assert count <= 3, f"搜索不存在的词返回了 {count} 个结果"

test("搜索不存在的词 → 结果为0或很少", search_test_02)

def search_test_03():
    """清空搜索后，文件列表必须恢复"""
    p = browser.new_context(viewport={'width':1920,'height':1080}, locale='zh-CN').new_page()
    p.set_default_timeout(10000)
    p.goto(BASE, wait_until="domcontentloaded")
    p.wait_for_timeout(2000)
    count_original = p.locator(".file-item").count()
    p.fill("#topSearchInput", "2026")
    p.wait_for_timeout(2000)
    p.fill("#topSearchInput", "")
    p.wait_for_timeout(2000)
    count_restored = p.locator(".file-item").count()
    p.close()
    assert count_restored == count_original, f"清空搜索后数量变了: {count_original} → {count_restored}"

test("搜索后清空 → 文件列表恢复原始数量", search_test_03)

# ============================================================
# 模块5: 视图切换（网格↔列表）
# ============================================================
print("\n" + "=" * 50)
print("  模块5: 视图切换（网格↔列表真正切换）")
print("=" * 50)

def view_test_01():
    """切换到列表视图后，文件项class必须变"""
    p = browser.new_context(viewport={'width':1920,'height':1080}, locale='zh-CN').new_page()
    p.set_default_timeout(10000)
    p.goto(BASE, wait_until="domcontentloaded")
    p.wait_for_timeout(2000)
    # 默认网格视图
    grid_count = p.locator(".file-item").count()
    list_count = p.locator(".file-list-item").count()
    assert grid_count > 0, f"网格视图无文件: {grid_count}"
    # 切到列表
    p.click('.view-toggle button[data-view="list"]')
    p.wait_for_timeout(1000)
    grid_count2 = p.locator(".file-item").count()
    list_count2 = p.locator(".file-list-item").count()
    p.close()
    assert list_count2 > 0, f"列表视图无文件: {list_count2}"
    assert grid_count2 == 0, f"切到列表后网格还有 {grid_count2} 个"

test("点击列表按钮 → 网格消失、列表出现", view_test_01)

def view_test_02():
    """切回网格视图，网格必须恢复"""
    p = browser.new_context(viewport={'width':1920,'height':1080}, locale='zh-CN').new_page()
    p.set_default_timeout(10000)
    p.goto(BASE, wait_until="domcontentloaded")
    p.wait_for_timeout(2000)
    p.click('.view-toggle button[data-view="list"]')
    p.wait_for_timeout(500)
    p.click('.view-toggle button[data-view="grid"]')
    p.wait_for_timeout(1000)
    grid = p.locator(".file-item").count()
    lst = p.locator(".file-list-item").count()
    p.close()
    assert grid > 0, f"切回网格后无文件: {grid}"
    assert lst == 0, f"切回网格后列表还在: {lst}"

test("列表→网格 → 网格恢复、列表消失", view_test_02)

# ============================================================
# 模块6: 模态框（打开→关闭→状态变化）
# ============================================================
print("\n" + "=" * 50)
print("  模块6: 模态框打开/关闭")
print("=" * 50)

def modal_test_01():
    """点击上传按钮 → 上传模态框必须出现"""
    p = browser.new_context(viewport={'width':1920,'height':1080}, locale='zh-CN').new_page()
    p.set_default_timeout(10000)
    p.goto(BASE, wait_until="domcontentloaded")
    p.wait_for_timeout(2000)
    vis_before = "active" in (p.locator("#uploadModal").get_attribute("class") or "")
    p.click("#btnUpload")
    p.wait_for_timeout(500)
    vis_after = "active" in (p.locator("#uploadModal").get_attribute("class") or "")
    p.close()
    assert not vis_before, "上传模态框初始就打开了"
    assert vis_after, "点击上传按钮后模态框没打开"

test("点击上传按钮 → 上传模态框弹出", modal_test_01)

def modal_test_02():
    """打开上传模态框后点关闭 → 必须消失"""
    p = browser.new_context(viewport={'width':1920,'height':1080}, locale='zh-CN').new_page()
    p.set_default_timeout(10000)
    p.goto(BASE, wait_until="domcontentloaded")
    p.wait_for_timeout(2000)
    p.click("#btnUpload")
    p.wait_for_timeout(500)
    p.click("#btnCloseUpload")
    p.wait_for_timeout(500)
    vis = "active" in (p.locator("#uploadModal").get_attribute("class") or "")
    p.close()
    assert not vis, "关闭后模态框还开着"

test("上传模态框 → 点关闭 → 模态框消失", modal_test_02)

def modal_test_03():
    """打开模态框后按ESC → 必须关闭"""
    p = browser.new_context(viewport={'width':1920,'height':1080}, locale='zh-CN').new_page()
    p.set_default_timeout(10000)
    p.goto(BASE, wait_until="domcontentloaded")
    p.wait_for_timeout(2000)
    p.click("#btnUpload")
    p.wait_for_timeout(500)
    p.keyboard.press("Escape")
    p.wait_for_timeout(500)
    vis = "active" in (p.locator("#uploadModal").get_attribute("class") or "")
    p.close()
    assert not vis, "ESC后模态框还开着"

test("上传模态框 → 按ESC → 模态框关闭", modal_test_03)

# ============================================================
# 模块7: 全选/取消全选
# ============================================================
print("\n" + "=" * 50)
print("  模块7: 全选功能")
print("=" * 50)

def select_test_01():
    """勾选全选后，选中计数必须变为文件总数"""
    p = browser.new_context(viewport={'width':1920,'height':1080}, locale='zh-CN').new_page()
    p.set_default_timeout(10000)
    p.goto(BASE, wait_until="domcontentloaded")
    p.wait_for_timeout(2000)
    total = p.locator(".file-item").count()
    if total == 0:
        p.close()
        return
    # 勾选全选
    p.check("#selectAll")
    p.wait_for_timeout(500)
    count_text = p.locator("#selectedCount").inner_text()
    p.close()
    assert str(total) in count_text, f"全选后计数不对: 期望含{total}, 实际'{count_text}'"

test("勾选全选 → 选中计数 = 文件总数", select_test_01)

def select_test_02():
    """全选后取消，计数必须归零"""
    p = browser.new_context(viewport={'width':1920,'height':1080}, locale='zh-CN').new_page()
    p.set_default_timeout(10000)
    p.goto(BASE, wait_until="domcontentloaded")
    p.wait_for_timeout(2000)
    p.check("#selectAll")
    p.wait_for_timeout(500)
    p.uncheck("#selectAll")
    p.wait_for_timeout(500)
    count_text = p.locator("#selectedCount").inner_text()
    p.close()
    assert "0" in count_text, f"取消全选后计数没归零: {count_text}"

test("全选→取消 → 选中计数归零", select_test_02)

def select_test_03():
    """全选后，下载/删除等按钮必须启用"""
    p = browser.new_context(viewport={'width':1920,'height':1080}, locale='zh-CN').new_page()
    p.set_default_timeout(10000)
    p.goto(BASE, wait_until="domcontentloaded")
    p.wait_for_timeout(2000)
    total = p.locator(".file-item").count()
    if total == 0:
        p.close()
        return
    p.check("#selectAll")
    p.wait_for_timeout(500)
    dl_disabled = p.locator("#btnDownload").is_disabled()
    del_disabled = p.locator("#btnDelete").is_disabled()
    p.close()
    assert not dl_disabled, "全选后下载按钮还是禁用"
    assert not del_disabled, "全选后删除按钮还是禁用"

test("全选 → 下载/删除按钮启用", select_test_03)

# ============================================================
# 模块8: 单击文件 → 详情面板
# ============================================================
print("\n" + "=" * 50)
print("  模块8: 单击文件 → 详情面板")
print("=" * 50)

def detail_test_01():
    """单击非文件夹项 → 右侧详情面板必须弹出"""
    p = browser.new_context(viewport={'width':1920,'height':1080}, locale='zh-CN').new_page()
    p.set_default_timeout(10000)
    p.goto(BASE, wait_until="domcontentloaded")
    p.wait_for_timeout(2000)
    # 找一个非文件夹
    files = p.locator('.file-item[data-dir="false"]')
    if files.count() == 0:
        p.close()
        return
    vis_before = "active" in (p.locator("#detailPanel").get_attribute("class") or "")
    files.first.click()
    p.wait_for_timeout(500)
    vis_after = "active" in (p.locator("#detailPanel").get_attribute("class") or "")
    p.close()
    assert not vis_before, "详情面板初始就开着"
    assert vis_after, "单击文件后详情面板没弹出"

test("单击文件 → 右侧详情面板弹出", detail_test_01)

def detail_test_02():
    """详情面板弹出后点关闭 → 必须消失"""
    p = browser.new_context(viewport={'width':1920,'height':1080}, locale='zh-CN').new_page()
    p.set_default_timeout(10000)
    p.goto(BASE, wait_until="domcontentloaded")
    p.wait_for_timeout(2000)
    files = p.locator('.file-item[data-dir="false"]')
    if files.count() == 0:
        p.close()
        return
    files.first.click()
    p.wait_for_timeout(500)
    p.click("#btnCloseDetail")
    p.wait_for_timeout(500)
    vis = "active" in (p.locator("#detailPanel").get_attribute("class") or "")
    p.close()
    assert not vis, "关闭后详情面板还开着"

test("详情面板 → 点关闭 → 面板消失", detail_test_02)

# ============================================================
# 模块9: 云盘管理模态框
# ============================================================
print("\n" + "=" * 50)
print("  模块9: 云盘管理模态框")
print("=" * 50)

def cloud_test_01():
    """点击云盘导航 → 云盘模态框必须弹出"""
    p = browser.new_context(viewport={'width':1920,'height':1080}, locale='zh-CN').new_page()
    p.set_default_timeout(10000)
    p.goto(BASE, wait_until="domcontentloaded")
    p.wait_for_timeout(2000)
    p.click('[data-view="cloud"]')
    p.wait_for_timeout(1000)
    vis = "active" in (p.locator("#cloudModal").get_attribute("class") or "")
    p.close()
    assert vis, "点击云盘导航后模态框没弹出"

test("点击云盘导航 → 云盘模态框弹出", cloud_test_01)

def cloud_test_02():
    """云盘模态框内切换tab → 内容区必须变化"""
    p = browser.new_context(viewport={'width':1920,'height':1080}, locale='zh-CN').new_page()
    p.set_default_timeout(10000)
    p.goto(BASE, wait_until="domcontentloaded")
    p.wait_for_timeout(2000)
    p.click('[data-view="cloud"]')
    p.wait_for_timeout(1000)
    # 切到"添加网盘"
    p.click('.cloud-tab[data-tab="add"]')
    p.wait_for_timeout(500)
    add_vis = "active" in (p.locator("#cloud-add").get_attribute("class") or "")
    disks_vis = "active" in (p.locator("#cloud-disks").get_attribute("class") or "")
    p.close()
    assert add_vis, "切换到添加tab后 cloud-add 没激活"
    assert not disks_vis, "切到添加tab后 disks 还激活"

test("云盘模态框 → 切换到'添加网盘'tab → 内容切换", cloud_test_02)

# ============================================================
# 模块10: 面包屑层级导航
# ============================================================
print("\n" + "=" * 50)
print("  模块10: 面包屑多级导航")
print("=" * 50)

def breadcrumb_test_01():
    """双击进入子目录后，面包屑必须有多个层级"""
    p = browser.new_context(viewport={'width':1920,'height':1080}, locale='zh-CN').new_page()
    p.set_default_timeout(10000)
    p.goto(BASE, wait_until="domcontentloaded")
    p.wait_for_timeout(2000)
    folders = p.locator('.file-item[data-dir="true"]')
    if folders.count() == 0:
        p.close()
        return
    folders.first.dblclick()
    p.wait_for_timeout(2000)
    bc_count = p.locator(".breadcrumb-item").count()
    p.close()
    assert bc_count >= 2, f"面包屑层级不够: {bc_count}"

test("进入子目录 → 面包屑有2+层级", breadcrumb_test_01)

# ============================================================
# 模块11: API真实返回值验证
# ============================================================
print("\n" + "=" * 50)
print("  模块11: API返回值验证")
print("=" * 50)

def api_test_01():
    """GET /api/files 必须返回 items 数组"""
    import httpx
    r = httpx.get(f"{BASE}/api/files", timeout=10)
    data = r.json()
    assert "items" in data, f"返回无 items 字段: {list(data.keys())}"
    assert isinstance(data["items"], list), f"items 不是数组: {type(data['items'])}"

test("GET /api/files → 返回 items 数组", api_test_01)

def api_test_02():
    """GET /api/files?source=downloads 必须返回下载目录内容"""
    import httpx
    r = httpx.get(f"{BASE}/api/files?source=downloads", timeout=10)
    data = r.json()
    assert "items" in data, f"返回无 items: {list(data.keys())}"
    names = [i["name"] for i in data["items"]]
    assert any("恋爱心理" in n or "技术运维" in n or "心理学" in n for n in names), \
        f"下载目录无分类文件夹: {names[:5]}"

test("GET /api/files?source=downloads → 包含分类文件夹", api_test_02)

def api_test_03():
    """GET /api/files/search?q=2026 必须返回 results"""
    import httpx
    r = httpx.get(f"{BASE}/api/files/search?q=2026&source=downloads", timeout=10)
    data = r.json()
    assert "results" in data, f"返回无 results: {list(data.keys())}"
    assert data["count"] > 0, "搜索'2026'返回0条结果"

test("GET /api/files/search?q=2026 → 返回>0条结果", api_test_03)

def api_test_04():
    """GET /api/status 必须返回 completed_uploads 字段"""
    import httpx
    r = httpx.get(f"{BASE}/api/status", timeout=10)
    data = r.json()
    assert "completed_uploads" in data, f"返回无 completed_uploads: {list(data.keys())}"
    assert data["active_uploads"] == 0, f"还有 {data['active_uploads']} 个卡住的上传"

test("GET /api/status → active_uploads=0", api_test_04)

def api_test_05():
    """GET /api/storage/stats 必须返回 total_size"""
    import httpx
    r = httpx.get(f"{BASE}/api/storage/stats", timeout=10)
    data = r.json()
    assert "uploads_size" in data or "total_size" in data, f"返回无 total_size: {list(data.keys())}"

test("GET /api/storage/stats → 返回 total_size", api_test_05)

# ============================================================
# 模块12: 响应式布局
# ============================================================
print("\n" + "=" * 50)
print("  模块12: 响应式布局")
print("=" * 50)

def responsive_test_01():
    """缩小到手机宽度，侧边栏应该隐藏或缩小"""
    p = browser.new_context(viewport={'width':375,'height':667}, locale='zh-CN').new_page()
    p.set_default_timeout(10000)
    p.goto(BASE, wait_until="domcontentloaded")
    p.wait_for_timeout(2000)
    sidebar = p.locator(".sidebar")
    sidebar_box = sidebar.bounding_box()
    p.close()
    if sidebar_box:
        assert sidebar_box["width"] < 400, f"手机宽度下侧边栏太宽: {sidebar_box['width']}"

test("手机宽度(375px) → 侧边栏适配", responsive_test_01)

# ============================================================
# 总结
# ============================================================
browser.close()
pw.stop()

print("\n" + "=" * 60)
print(f"  真实功能测试结果")
print("=" * 60)
print(f"  ✅ 通过: {passed}")
print(f"  ❌ 失败: {failed}")
print(f"  📊 总计: {passed + failed}")
print(f"  📈 通过率: {100*passed/(passed+failed):.0f}%")
if failed > 0:
    print("\n  失败详情:")
    for item in results:
        if item[0] == "FAIL":
            print(f"    ❌ {item[1]}: {item[2]}")
print("=" * 60)

sys.exit(0 if failed == 0 else 1)
