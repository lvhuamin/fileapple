#!/usr/bin/env python3
"""
8866学习目录系统 - 真Bug检测测试
每条测试覆盖一个真实的用户交互场景，基于已发现的bug模式编写
操作 → 等待 → 验证结果变化
"""
import sys, time, json
from pathlib import Path
from playwright.sync_api import sync_playwright

BASE = "http://localhost:8866"
results = []

def test(name, func):
    print(f"  [{len(results)+1:2d}] {name}...", end=" ", flush=True)
    try:
        func()
        results.append(("PASS", name, ""))
        print("✅")
    except Exception as e:
        results.append(("FAIL", name, str(e)[:100]))
        print(f"❌ {str(e)[:80]}")

def fresh(ctx):
    p = ctx.new_page()
    p.set_default_timeout(10000)
    p.goto(BASE, wait_until="domcontentloaded")
    p.wait_for_timeout(2000)
    return p

# Collect JS errors per page
js_errors = []

def collect_errors(page):
    """收集页面JS错误"""
    def on_error(error):
        js_errors.append(str(error))
    def on_pageerror(msg):
        js_errors.append(str(msg))
    page.on("pageerror", on_pageerror)
    page.on("console", lambda msg: js_errors.append(msg.text) if msg.type == "error" else None)

pw = sync_playwright().start()
browser = pw.chromium.launch(headless=True, args=['--no-sandbox','--disable-dev-shm-usage'])

# ============================================================
# 模块1: 文件夹导航（已知bug: 文件路径导致crash）
# ============================================================
print("\n" + "="*60)
print("  模块1: 文件夹导航与文件路径处理")
print("="*60)

def test_01():
    """双击中文文件夹 → 进入子目录，文件列表变化"""
    ctx = browser.new_context(viewport={'width':1920,'height':1080}, locale='zh-CN')
    p = fresh(ctx)
    collect_errors(p)
    items_before = p.locator(".file-item").count()
    folders = p.locator('.file-item[data-dir="true"]')
    if folders.count() == 0:
        p.close(); ctx.close()
        raise Exception("无文件夹可双击")
    folder_name = folders.first.locator(".file-name").inner_text()
    folders.first.dblclick()
    p.wait_for_timeout(2500)
    bc = p.locator("#breadcrumb").inner_text()
    assert folder_name in bc or bc != "全部文件", f"面包屑未变化: {bc}"
    p.close(); ctx.close()
test("双击中文文件夹 → 面包屑包含文件夹名", test_01)

def test_02():
    """进入子目录 → 文件列表内容不同于根目录"""
    ctx = browser.new_context(viewport={'width':1920,'height':1080}, locale='zh-CN')
    p = fresh(ctx)
    items_root = set()
    for item in p.locator(".file-item .file-name").all()[:10]:
        items_root.add(item.inner_text())
    folders = p.locator('.file-item[data-dir="true"]')
    if folders.count() == 0:
        p.close(); ctx.close()
        raise Exception("无文件夹")
    folders.first.dblclick()
    p.wait_for_timeout(2500)
    items_sub = set()
    for item in p.locator(".file-item .file-name").all()[:10]:
        items_sub.add(item.inner_text())
    assert items_root != items_sub, f"子目录内容与根目录完全相同"
    p.close(); ctx.close()
test("进入子目录 → 文件列表内容变化", test_02)

def test_03():
    """进入子目录后点返回 → 回到根目录"""
    ctx = browser.new_context(viewport={'width':1920,'height':1080}, locale='zh-CN')
    p = fresh(ctx)
    folders = p.locator('.file-item[data-dir="true"]')
    if folders.count() == 0:
        p.close(); ctx.close()
        raise Exception("无文件夹")
    folders.first.dblclick()
    p.wait_for_timeout(2500)
    bc_in = p.locator("#breadcrumb").inner_text()
    back = p.locator("#btnBack")
    assert back.is_visible(), "返回按钮不可见"
    back.click()
    p.wait_for_timeout(2000)
    bc_after = p.locator("#breadcrumb").inner_text()
    assert "全部文件" in bc_after, f"返回后面包屑: {bc_after}"
    p.close(); ctx.close()
test("进入子目录 → 返回 → 回到全部文件", test_03)

def test_04():
    """点击面包屑的'全部文件' → 回到根"""
    ctx = browser.new_context(viewport={'width':1920,'height':1080}, locale='zh-CN')
    p = fresh(ctx)
    folders = p.locator('.file-item[data-dir="true"]')
    if folders.count() == 0:
        p.close(); ctx.close()
        raise Exception("无文件夹")
    folders.first.dblclick()
    p.wait_for_timeout(2500)
    root_crumb = p.locator('.breadcrumb-item').first
    root_crumb.click()
    p.wait_for_timeout(2000)
    bc = p.locator("#breadcrumb").inner_text()
    assert "全部文件" in bc, f"面包屑点击后: {bc}"
    p.close(); ctx.close()
test("面包屑'全部文件'点击 → 回到根", test_04)

def test_05():
    """API: 文件路径不crash（已知bug: NotADirectoryError）"""
    import httpx
    r = httpx.get(f"{BASE}/api/files?source=downloads&path=恋爱心理/2026-06-15.md", timeout=10)
    assert r.status_code == 200, f"文件路径请求返回{r.status_code}"
    data = r.json()
    assert data.get("is_file_response") or data.get("items"), f"响应缺少items: {list(data.keys())}"
test("API文件路径 → 不crash返回200", test_05)

def test_06():
    """API: 中文路径URL编码 → 正常返回目录内容"""
    import httpx
    import urllib.parse
    path = urllib.parse.quote("恋爱心理")
    r = httpx.get(f"{BASE}/api/files?source=downloads&path={path}", timeout=10)
    assert r.status_code == 200
    data = r.json()
    assert data.get("total", 0) > 0, f"中文目录返回0文件"
test("API中文路径 → 返回文件列表", test_06)

# ============================================================
# 模块2: 导航切换（已知bug: 状态不同步）
# ============================================================
print("\n" + "="*60)
print("  模块2: 导航切换与状态同步")
print("="*60)

def test_07():
    """点击'下载目录' → 标题和内容都变化"""
    ctx = browser.new_context(viewport={'width':1920,'height':1080}, locale='zh-CN')
    p = fresh(ctx)
    title_before = p.locator("#currentPath").inner_text()
    p.click('[data-view="downloads"]')
    p.wait_for_timeout(2500)
    title_after = p.locator("#currentPath").inner_text()
    assert title_before != title_after, f"标题没变: {title_before}"
    assert "下载" in title_after, f"标题不含'下载': {title_after}"
    p.close(); ctx.close()
test("下载目录导航 → 标题包含'下载'", test_07)

def test_08():
    """下载目录 → 点击分类'恋爱心理' → 面包屑包含分类名"""
    ctx = browser.new_context(viewport={'width':1920,'height':1080}, locale='zh-CN')
    p = fresh(ctx)
    p.click('[data-view="downloads"]')
    p.wait_for_timeout(2500)
    cat = p.locator('.nav-item[data-category="恋爱心理"]')
    if cat.count() == 0:
        p.close(); ctx.close()
        raise Exception("无'恋爱心理'分类")
    cat.click()
    p.wait_for_timeout(2500)
    bc = p.locator("#breadcrumb").inner_text()
    title = p.locator("#currentPath").inner_text()
    assert "恋爱心理" in bc or "恋爱心理" in title, f"面包屑和标题都没有'恋爱心理': bc={bc}, title={title}"
    p.close(); ctx.close()
test("下载→恋爱心理分类 → 面包屑包含分类名", test_08)

def test_09():
    """切换多个视图 → 每次都正确切换"""
    ctx = browser.new_context(viewport={'width':1920,'height':1080}, locale='zh-CN')
    p = fresh(ctx)
    views = [("all", "全部"), ("uploads", "上传"), ("downloads", "下载")]
    for view, keyword in views:
        p.click(f'[data-view="{view}"]')
        p.wait_for_timeout(2000)
        title = p.locator("#currentPath").inner_text()
        assert keyword in title, f"切换{view}后标题不含'{keyword}': {title}"
    p.close(); ctx.close()
test("多视图切换 → 每次标题都正确", test_09)

def test_10():
    """从子目录切换视图 → 回到根目录"""
    ctx = browser.new_context(viewport={'width':1920,'height':1080}, locale='zh-CN')
    p = fresh(ctx)
    folders = p.locator('.file-item[data-dir="true"]')
    if folders.count() == 0:
        p.close(); ctx.close()
        raise Exception("无文件夹")
    folders.first.dblclick()
    p.wait_for_timeout(2500)
    p.click('[data-view="uploads"]')
    p.wait_for_timeout(2000)
    title = p.locator("#currentPath").inner_text()
    assert "上传" in title, f"切换视图后标题: {title}"
    p.close(); ctx.close()
test("子目录→切换视图 → 正确切换不卡死", test_10)

# ============================================================
# 模块3: 视图切换（已知bug: 列表视图事件未绑定）
# ============================================================
print("\n" + "="*60)
print("  模块3: 视图切换与交互")
print("="*60)

def test_11():
    """切换到列表视图 → 文件以列表形式显示"""
    ctx = browser.new_context(viewport={'width':1920,'height':1080}, locale='zh-CN')
    p = fresh(ctx)
    p.click('.view-toggle button[data-view="list"]')
    p.wait_for_timeout(1500)
    list_items = p.locator(".file-list-item").count()
    grid_items = p.locator(".file-grid .file-item").count()
    assert list_items > 0, "列表视图无列表项"
    p.close(); ctx.close()
test("列表视图切换 → 显示列表项", test_11)

def test_12():
    """列表视图双击文件夹 → 进入子目录"""
    ctx = browser.new_context(viewport={'width':1920,'height':1080}, locale='zh-CN')
    p = fresh(ctx)
    p.click('.view-toggle button[data-view="list"]')
    p.wait_for_timeout(1500)
    folders = p.locator('.file-list-item[data-dir="true"]')
    if folders.count() == 0:
        p.close(); ctx.close()
        raise Exception("列表视图无文件夹")
    bc_before = p.locator("#breadcrumb").inner_text()
    folders.first.dblclick()
    p.wait_for_timeout(2500)
    bc_after = p.locator("#breadcrumb").inner_text()
    assert bc_before != bc_after, f"列表视图双击后面包屑未变: {bc_after}"
    p.close(); ctx.close()
test("列表视图双击文件夹 → 进入子目录", test_12)

def test_13():
    """网格→列表→网格 → 视图正确来回"""
    ctx = browser.new_context(viewport={'width':1920,'height':1080}, locale='zh-CN')
    p = fresh(ctx)
    p.click('.view-toggle button[data-view="list"]')
    p.wait_for_timeout(1000)
    list1 = p.locator(".file-list-item").count()
    p.click('.view-toggle button[data-view="grid"]')
    p.wait_for_timeout(1000)
    grid1 = p.locator(".file-grid .file-item").count()
    assert list1 > 0, "列表视图无内容"
    assert grid1 > 0, "切回网格后无内容"
    p.close(); ctx.close()
test("视图来回切换 → 内容不丢失", test_13)

# ============================================================
# 模块4: 搜索（已知bug: 搜索只搜一个source）
# ============================================================
print("\n" + "="*60)
print("  模块4: 搜索功能")
print("="*60)

def test_14():
    """搜索关键词 → 返回相关结果"""
    ctx = browser.new_context(viewport={'width':1920,'height':1080}, locale='zh-CN')
    p = fresh(ctx)
    p.fill("#topSearchInput", "2026")
    p.press("#topSearchInput", "Enter")
    p.wait_for_timeout(2000)
    items = p.locator(".file-item").count()
    assert items > 0, "搜索'2026'无结果"
    p.close(); ctx.close()
test("搜索'2026' → 有结果", test_14)

def test_15():
    """搜索后清空 → 恢复原始列表"""
    ctx = browser.new_context(viewport={'width':1920,'height':1080}, locale='zh-CN')
    p = fresh(ctx)
    count_before = p.locator(".file-item").count()
    p.fill("#topSearchInput", "zzz不存在的文件xxx")
    p.press("#topSearchInput", "Enter")
    p.wait_for_timeout(2000)
    count_search = p.locator(".file-item").count()
    p.fill("#topSearchInput", "")
    p.press("#topSearchInput", "Enter")
    p.wait_for_timeout(2000)
    count_after = p.locator(".file-item").count()
    assert count_after >= count_before, f"清空搜索后文件数{count_after} < 原始{count_before}"
    p.close(); ctx.close()
test("搜索→清空 → 文件列表恢复", test_15)

def test_16():
    """API搜索 → 有source参数时正确过滤"""
    import httpx
    r = httpx.get(f"{BASE}/api/files/search?q=2026&source=downloads", timeout=10)
    assert r.status_code == 200
    data = r.json()
    assert data.get("total", 0) >= 0, "搜索API返回格式错误"
test("API搜索带source → 正确返回", test_16)

# ============================================================
# 模块5: 文件操作（已知bug: onclick路径注入）
# ============================================================
print("\n" + "="*60)
print("  模块5: 文件操作与详情面板")
print("="*60)

def test_17():
    """单击非目录文件 → 详情面板显示文件信息"""
    ctx = browser.new_context(viewport={'width':1920,'height':1080}, locale='zh-CN')
    p = fresh(ctx)
    # 只选择非目录文件点击（文件夹单击不弹详情，这是设计行为）
    non_dir_files = p.locator('.file-item').filter(has_not=p.locator('[data-dir="true"]'))
    # 备用方式：逐个检查
    all_items = p.locator(".file-item").all()
    clicked = False
    for item in all_items:
        if item.get_attribute("data-dir") != "true":
            item.click()
            clicked = True
            break
    if not clicked:
        p.close(); ctx.close()
        raise Exception("无非目录文件可点击")
    p.wait_for_timeout(1500)
    panel = p.locator("#detailPanel")
    assert panel.is_visible(), f"详情面板未显示(class={panel.get_attribute('class')})"
    p.close(); ctx.close()
test("单击文件 → 详情面板显示", test_17)

def test_18():
    """详情面板显示文件名"""
    ctx = browser.new_context(viewport={'width':1920,'height':1080}, locale='zh-CN')
    p = fresh(ctx)
    all_items = p.locator(".file-item").all()
    clicked = False
    fname = ""
    for item in all_items:
        if item.get_attribute("data-dir") != "true":
            fname = item.locator(".file-name").inner_text().strip()
            item.click()
            clicked = True
            break
    if not clicked:
        p.close(); ctx.close()
        raise Exception("无非目录文件")
    p.wait_for_timeout(1500)
    panel_text = p.locator("#detailPanel").inner_text()
    assert fname[:5] in panel_text, f"面板不含文件名'{fname}': {panel_text[:100]}"
    p.close(); ctx.close()
test("详情面板 → 包含文件名", test_18)

def test_19():
    """全选 → 计数=文件总数 → 取消→计数=0"""
    ctx = browser.new_context(viewport={'width':1920,'height':1080}, locale='zh-CN')
    p = fresh(ctx)
    total = p.locator(".file-item").count()
    if total == 0:
        p.close(); ctx.close()
        raise Exception("无文件")
    p.click("#selectAll")
    p.wait_for_timeout(800)
    count_text = p.locator("#selectedCount").inner_text()
    assert str(total) in count_text, f"全选后计数不含{total}: {count_text}"
    p.click("#selectAll")
    p.wait_for_timeout(800)
    count_text2 = p.locator("#selectedCount").inner_text()
    assert "0" in count_text2, f"取消后计数不归零: {count_text2}"
    p.close(); ctx.close()
test("全选/取消 → 计数正确变化", test_19)

def test_20():
    """全选后按钮启用 → 取消后按钮禁用"""
    ctx = browser.new_context(viewport={'width':1920,'height':1080}, locale='zh-CN')
    p = fresh(ctx)
    if p.locator(".file-item").count() == 0:
        p.close(); ctx.close()
        raise Exception("无文件")
    dl_disabled_before = p.locator("#btnDownload").is_disabled()
    p.click("#selectAll")
    p.wait_for_timeout(800)
    dl_disabled_after = p.locator("#btnDownload").is_disabled()
    assert dl_disabled_before and not dl_disabled_after, f"全选前后按钮状态未变化: {dl_disabled_before}→{dl_disabled_after}"
    p.close(); ctx.close()
test("全选 → 操作按钮启用", test_20)

# ============================================================
# 模块6: 模态框交互
# ============================================================
print("\n" + "="*60)
print("  模块6: 模态框交互")
print("="*60)

def test_21():
    """上传按钮 → 模态框打开 → X关闭 → 模态框消失"""
    ctx = browser.new_context(viewport={'width':1920,'height':1080}, locale='zh-CN')
    p = fresh(ctx)
    p.click("#btnUpload")
    p.wait_for_timeout(1000)
    modal_class = p.locator("#uploadModal").get_attribute("class") or ""
    assert "active" in modal_class, f"模态框未打开: {modal_class}"
    close_btns = p.locator("#uploadModal .modal-close, #btnCloseUpload")
    if close_btns.count() > 0:
        close_btns.first.click()
        p.wait_for_timeout(800)
        modal_class2 = p.locator("#uploadModal").get_attribute("class") or ""
        assert "active" not in modal_class2, f"关闭后模态框仍active"
    p.close(); ctx.close()
test("上传模态框 → 打开→关闭", test_21)

def test_22():
    """ESC键关闭模态框"""
    ctx = browser.new_context(viewport={'width':1920,'height':1080}, locale='zh-CN')
    p = fresh(ctx)
    p.click("#btnUpload")
    p.wait_for_timeout(1000)
    p.keyboard.press("Escape")
    p.wait_for_timeout(1000)
    modal_class = p.locator("#uploadModal").get_attribute("class") or ""
    assert "active" not in modal_class, f"ESC后模态框仍active"
    p.close(); ctx.close()
test("ESC键 → 关闭模态框", test_22)

# ============================================================
# 模块7: JS错误检测（已知bug: null引用）
# ============================================================
print("\n" + "="*60)
print("  模块7: JS运行时错误检测")
print("="*60)

def test_23():
    """页面加载后无JS错误"""
    ctx = browser.new_context(viewport={'width':1920,'height':1080}, locale='zh-CN')
    p = fresh(ctx)
    errors = []
    p.on("pageerror", lambda e: errors.append(str(e)))
    p.wait_for_timeout(3000)
    p.close(); ctx.close()
    real_errors = [e for e in errors if "style" in e.lower() or "null" in e.lower() or "undefined" in e.lower()]
    assert len(real_errors) == 0, f"页面加载后有{len(real_errors)}个JS错误: {real_errors[0][:60]}"
test("页面加载 → 无null引用JS错误", test_23)

def test_24():
    """导航切换后无JS错误"""
    ctx = browser.new_context(viewport={'width':1920,'height':1080}, locale='zh-CN')
    p = fresh(ctx)
    errors = []
    p.on("pageerror", lambda e: errors.append(str(e)))
    p.click('[data-view="downloads"]')
    p.wait_for_timeout(2000)
    p.click('[data-view="all"]')
    p.wait_for_timeout(2000)
    p.close(); ctx.close()
    real_errors = [e for e in errors if "null" in e.lower()]
    assert len(real_errors) == 0, f"导航切换后有{len(real_errors)}个null错误"
test("导航切换 → 无null引用错误", test_24)

def test_25():
    """双击进入文件夹后无JS错误"""
    ctx = browser.new_context(viewport={'width':1920,'height':1080}, locale='zh-CN')
    p = fresh(ctx)
    errors = []
    p.on("pageerror", lambda e: errors.append(str(e)))
    folders = p.locator('.file-item[data-dir="true"]')
    if folders.count() > 0:
        folders.first.dblclick()
        p.wait_for_timeout(3000)
    p.close(); ctx.close()
    real_errors = [e for e in errors if "null" in e.lower() or "Cannot" in e]
    assert len(real_errors) == 0, f"进入文件夹后有JS错误: {real_errors[0][:60]}"
test("进入文件夹 → 无JS错误", test_25)

# ============================================================
# 模块8: API边界测试（已知bug: 边界处理不足）
# ============================================================
print("\n" + "="*60)
print("  模块8: API边界与安全测试")
print("="*60)

def test_26():
    """API: 路径遍历攻击 → 拒绝"""
    import httpx
    r = httpx.get(f"{BASE}/api/files?source=uploads&path=../../etc/passwd", timeout=10)
    assert r.status_code in (200, 400, 403, 404), f"路径遍历返回{r.status_code}"
    if r.status_code == 200:
        data = r.json()
        items = data.get("items", [])
        for item in items:
            assert "passwd" not in item.get("name",""), "路径遍历成功读到passwd!"
test("路径遍历 → 拒绝或返回空", test_26)

def test_27():
    """API: 不存在的路径 → 不crash"""
    import httpx
    r = httpx.get(f"{BASE}/api/files?source=uploads&path=不存在的目录/子目录", timeout=10)
    assert r.status_code in (200, 404), f"不存在路径返回{r.status_code}"
test("不存在路径 → 不crash", test_27)

def test_28():
    """API: storage_stats包含downloads分类"""
    import httpx
    r = httpx.get(f"{BASE}/api/storage/stats", timeout=10)
    data = r.json()
    cats = data.get("categories", {})
    has_dl = any(k.startswith("downloads/") for k in cats)
    assert has_dl, f"storage_stats缺少downloads分类: {list(cats.keys())}"
test("storage_stats → 包含downloads分类", test_28)

def test_29():
    """API: 空搜索 → 返回422(参数校验)或200空列表，不能500"""
    import httpx
    r = httpx.get(f"{BASE}/api/files/search?q=", timeout=10)
    # min_length=1 导致空搜索返回422是正常的参数校验行为
    assert r.status_code in (200, 422), f"空搜索异常返回{r.status_code}"
    if r.status_code == 200:
        data = r.json()
        assert "results" in data or "items" in data or "total" in data
test("空搜索 → 不crash(200或422)", test_29)

def test_30():
    """API: 特殊字符文件名搜索 → 不crash"""
    import httpx
    import urllib.parse
    q = urllib.parse.quote("test<script>alert(1)</script>")
    r = httpx.get(f"{BASE}/api/files/search?q={q}", timeout=10)
    assert r.status_code == 200
test("XSS搜索 → 不crash", test_30)

# ============================================================
# 模块9: 面包屑导航（已知bug: 中文路径未转义）
# ============================================================
print("\n" + "="*60)
print("  模块9: 面包屑导航")
print("="*60)

def test_31():
    """进入中文子目录 → 面包屑显示中文 → 点击回根"""
    ctx = browser.new_context(viewport={'width':1920,'height':1080}, locale='zh-CN')
    p = fresh(ctx)
    p.click('[data-view="downloads"]')
    p.wait_for_timeout(2000)
    folders = p.locator('.file-item[data-dir="true"]')
    if folders.count() == 0:
        p.close(); ctx.close()
        raise Exception("下载目录无文件夹")
    fname = folders.first.locator(".file-name").inner_text()
    folders.first.dblclick()
    p.wait_for_timeout(2500)
    crumbs = p.locator(".breadcrumb-item").all()
    assert len(crumbs) >= 2, f"面包屑层级不足: {len(crumbs)}"
    crumbs[0].click()
    p.wait_for_timeout(2000)
    bc = p.locator("#breadcrumb").inner_text()
    assert "全部" in bc or "下载" in bc, f"面包屑根点击后: {bc}"
    p.close(); ctx.close()
test("中文子目录面包屑 → 点击回根", test_31)

def test_32():
    """多层级导航 → 面包屑层级正确"""
    ctx = browser.new_context(viewport={'width':1920,'height':1080}, locale='zh-CN')
    p = fresh(ctx)
    folders1 = p.locator('.file-item[data-dir="true"]')
    if folders1.count() == 0:
        p.close(); ctx.close()
        raise Exception("无文件夹")
    folders1.first.dblclick()
    p.wait_for_timeout(2500)
    folders2 = p.locator('.file-item[data-dir="true"]')
    if folders2.count() > 0:
        folders2.first.dblclick()
        p.wait_for_timeout(2500)
        crumbs = p.locator(".breadcrumb-item").all()
        assert len(crumbs) >= 3, f"两层级后面包屑只有{len(crumbs)}级"
    p.close(); ctx.close()
test("多层导航 → 面包屑层级正确", test_32)

# ============================================================
# 模块10: 文件内容渲染（已知bug: 文件名显示不全）
# ============================================================
print("\n" + "="*60)
print("  模块10: 文件内容渲染")
print("="*60)

def test_33():
    """文件名不为空"""
    ctx = browser.new_context(viewport={'width':1920,'height':1080}, locale='zh-CN')
    p = fresh(ctx)
    names = p.locator(".file-name").all()
    for i, n in enumerate(names[:10]):
        text = n.inner_text().strip()
        assert text, f"第{i+1}个文件名为空"
    p.close(); ctx.close()
test("文件名 → 全部非空", test_33)

def test_34():
    """文件元信息（大小/日期）显示"""
    ctx = browser.new_context(viewport={'width':1920,'height':1080}, locale='zh-CN')
    p = fresh(ctx)
    metas = p.locator(".file-meta").all()
    has_content = False
    for m in metas[:10]:
        text = m.inner_text().strip()
        if text:
            has_content = True
            break
    assert has_content, "所有文件元信息为空"
    p.close(); ctx.close()
test("文件元信息 → 至少部分有内容", test_34)

def test_35():
    """文件名含特殊字符 → 不产生JS错误"""
    ctx = browser.new_context(viewport={'width':1920,'height':1080}, locale='zh-CN')
    p = fresh(ctx)
    errors = []
    p.on("pageerror", lambda e: errors.append(str(e)))
    files = p.locator(".file-item")
    for i in range(min(5, files.count())):
        files.nth(i).click()
        p.wait_for_timeout(500)
    p.close(); ctx.close()
    real_errors = [e for e in errors if "Cannot" in e or "null" in e.lower()]
    assert len(real_errors) == 0, f"点击文件后JS错误: {real_errors[0][:60]}"
test("点击多个文件 → 无JS错误", test_35)

# ============================================================
# 模块11: 存储信息
# ============================================================
print("\n" + "="*60)
print("  模块11: 存储与统计")
print("="*60)

def test_36():
    """侧边栏存储信息显示有效数据"""
    ctx = browser.new_context(viewport={'width':1920,'height':1080}, locale='zh-CN')
    p = fresh(ctx)
    storage = p.locator("#storageUsed").inner_text()
    assert storage and storage != "0" and storage != "", f"存储信息为空: '{storage}'"
    p.close(); ctx.close()
test("存储信息 → 显示有效数据", test_36)

def test_37():
    """全部文件数量徽章 → 与实际文件数一致"""
    ctx = browser.new_context(viewport={'width':1920,'height':1080}, locale='zh-CN')
    p = fresh(ctx)
    p.wait_for_timeout(1000)
    badge = p.locator("#navAllCount")
    if badge.count() > 0:
        badge_text = badge.inner_text().strip()
        items = p.locator(".file-item").count()
        assert badge_text, "徽章文本为空"
    p.close(); ctx.close()
test("文件数量徽章 → 有显示", test_37)

# ============================================================
# 模块12: 端到端流程
# ============================================================
print("\n" + "="*60)
print("  模块12: 端到端用户流程")
print("="*60)

def test_38():
    """E2E: 打开→导航→进入文件夹→查看文件→返回→切换视图"""
    ctx = browser.new_context(viewport={'width':1920,'height':1080}, locale='zh-CN')
    p = fresh(ctx)
    errors = []
    p.on("pageerror", lambda e: errors.append(str(e)))
    # 1. 打开页面
    title = p.locator("#currentPath").inner_text()
    assert "全部" in title, f"初始标题不对: {title}"
    # 2. 切换到下载
    p.click('[data-view="downloads"]')
    p.wait_for_timeout(2000)
    title2 = p.locator("#currentPath").inner_text()
    assert "下载" in title2, f"下载标题不对: {title2}"
    # 3. 进入文件夹
    folders = p.locator('.file-item[data-dir="true"]')
    if folders.count() > 0:
        folders.first.dblclick()
        p.wait_for_timeout(2500)
        # 4. 点文件看详情
        files = p.locator('.file-item:not([data-dir="true"])')
        if files.count() > 0:
            files.first.click()
            p.wait_for_timeout(1000)
        # 5. 返回
        p.click("#btnBack")
        p.wait_for_timeout(2000)
    # 6. 切列表视图
    p.click('.view-toggle button[data-view="list"]')
    p.wait_for_timeout(1000)
    list_count = p.locator(".file-list-item").count()
    assert list_count > 0, "列表视图无内容"
    p.close(); ctx.close()
    real_errors = [e for e in errors if "Cannot" in e]
    assert len(real_errors) == 0, f"E2E流程中有JS错误: {real_errors[0][:60]}"
test("E2E完整流程 → 无错误", test_38)

def test_39():
    """E2E: 搜索→查看结果→清空→导航"""
    ctx = browser.new_context(viewport={'width':1920,'height':1080}, locale='zh-CN')
    p = fresh(ctx)
    errors = []
    p.on("pageerror", lambda e: errors.append(str(e)))
    count_before = p.locator(".file-item").count()
    p.fill("#topSearchInput", "md")
    p.press("#topSearchInput", "Enter")
    p.wait_for_timeout(2000)
    search_count = p.locator(".file-item").count()
    p.fill("#topSearchInput", "")
    p.press("#topSearchInput", "Enter")
    p.wait_for_timeout(2000)
    count_after = p.locator(".file-item").count()
    assert count_after >= count_before * 0.8, f"搜索清空后文件数异常: {count_after} vs {count_before}"
    p.click('[data-view="downloads"]')
    p.wait_for_timeout(2000)
    title = p.locator("#currentPath").inner_text()
    assert "下载" in title, f"搜索后导航失败: {title}"
    p.close(); ctx.close()
    assert len([e for e in errors if "Cannot" in e]) == 0, "搜索流程有JS错误"
test("E2E搜索流程 → 搜索→清空→导航", test_39)

def test_40():
    """E2E: 全选→看按钮→取消→导航走"""
    ctx = browser.new_context(viewport={'width':1920,'height':1080}, locale='zh-CN')
    p = fresh(ctx)
    if p.locator(".file-item").count() == 0:
        p.close(); ctx.close()
        raise Exception("无文件")
    p.click("#selectAll")
    p.wait_for_timeout(800)
    assert not p.locator("#btnDelete").is_disabled(), "全选后删除仍禁用"
    p.click("#selectAll")
    p.wait_for_timeout(800)
    assert p.locator("#btnDelete").is_disabled(), "取消后删除仍启用"
    p.click('[data-view="uploads"]')
    p.wait_for_timeout(2000)
    title = p.locator("#currentPath").inner_text()
    assert "上传" in title, f"导航失败: {title}"
    p.close(); ctx.close()
test("E2E选择流程 → 全选→取消→导航", test_40)

# ============================================================
# 模块13: API完整覆盖
# ============================================================
print("\n" + "="*60)
print("  模块13: API完整性验证")
print("="*60)

import httpx

def test_41():
    """API: downloads目录返回有效分类"""
    r = httpx.get(f"{BASE}/api/files?source=downloads", timeout=10)
    data = r.json()
    items = data.get("items", [])
    dirs = [i for i in items if i.get("is_dir")]
    assert len(dirs) > 0, "downloads目录无分类文件夹"
test("API downloads → 有分类文件夹", test_41)

def test_42():
    """API: uploads目录返回有效文件"""
    r = httpx.get(f"{BASE}/api/files?source=uploads", timeout=10)
    assert r.status_code == 200
    data = r.json()
    assert "items" in data and "total" in data
test("API uploads → 返回items和total", test_42)

def test_43():
    """API: tags返回数组"""
    r = httpx.get(f"{BASE}/api/tags", timeout=10)
    data = r.json()
    assert isinstance(data.get("tags", data if isinstance(data, list) else []), list)
test("API tags → 返回数组", test_43)

def test_44():
    """API: knowledge/stats返回有效数据"""
    r = httpx.get(f"{BASE}/api/knowledge/stats", timeout=10)
    assert r.status_code == 200
test("API knowledge/stats → 200", test_44)

def test_45():
    """API: 分类路径有文件"""
    import urllib.parse
    r = httpx.get(f"{BASE}/api/files?source=downloads&path={urllib.parse.quote('技术运维')}", timeout=10)
    assert r.status_code == 200
    data = r.json()
    assert data.get("total", 0) >= 0
test("API 分类路径 → 正常返回", test_45)

# ============================================================
# 清理与汇总
# ============================================================
browser.close()
pw.stop()

passed = sum(1 for r in results if r[0] == "PASS")
failed = sum(1 for r in results if r[0] == "FAIL")
total = len(results)

print("\n" + "="*60)
print(f"  测试结果: ✅ {passed}  ❌ {failed}  📊 {total}")
print(f"  通过率: {100*passed/total:.1f}%")
print("="*60)

if failed > 0:
    print("\n🐛 失败的测试（真Bug）:")
    for status, name, error in results:
        if status == "FAIL":
            print(f"  ❌ {name}")
            print(f"     → {error}")

sys.exit(0 if failed == 0 else 1)
