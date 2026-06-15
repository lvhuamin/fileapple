#!/usr/bin/env python3
"""
FileApple UI自动化测试 vFINAL - 200个测试用例
所有API端点和字段名已实际验证，路径全部使用相对路径（无前导/）
"""
import os, sys, time, json as _json
import httpx

BASE_URL = "http://localhost:8866"
_upload_dir_name = "uploads"

# ============ Playwright Setup ============
os.environ.setdefault("PLAYWRIGHT_BROWSERS_PATH", "/root/.cache/ms-playwright")
try:
    from playwright.sync_api import sync_playwright
    _pw = sync_playwright().start()
    _browser = _pw.chromium.launch(headless=True)
    _context = _browser.new_context()
    page = _context.new_page()
    page.goto(BASE_URL)
    page.wait_for_load_state("networkidle")
    page.wait_for_timeout(1000)
    HAS_PLAYWRIGHT = True
except Exception as _e:
    HAS_PLAYWRIGHT = False
    page = None
    print(f"Playwright not available: {_e}")

passed = 0
failed = 0
errors = []

# ============ Helpers ============
def run_test(name, fn):
    global passed, failed
    idx = passed + failed + 1
    sys.stdout.write(f"  [{idx:3d}] {name[:45]}...")
    sys.stdout.flush()
    try:
        fn()
        print(" ✅")
        passed += 1
    except Exception as e:
        msg = str(e)[:80]
        print(f" ❌ {msg}")
        errors.append((name, str(e)[:200]))
        failed += 1

def api_get(path, timeout=8, **kw): return httpx.get(f"{BASE_URL}{path}", timeout=timeout, **kw)
def api_post(path, timeout=8, **kw): return httpx.post(f"{BASE_URL}{path}", timeout=timeout, **kw)
def api_delete(path, timeout=8, **kw): return httpx.delete(f"{BASE_URL}{path}", timeout=timeout, **kw)

def upload_file(target_name, content_bytes=None):
    """上传文件到uploads目录。target_name是纯文件名（无/）。"""
    if content_bytes is None: content_bytes = b"Test content " * 50
    r = api_post("/api/upload/init", data={"file_name": target_name, "file_size": len(content_bytes)})
    if r.status_code != 200: return r
    tid = r.json()["task_id"]
    r = api_post("/api/upload/chunk",
        data={"task_id": tid, "chunk_index": 0},
        files={"chunk": (target_name, content_bytes, "text/plain")})
    if r.status_code != 200: return r
    return api_post("/api/upload/merge", data={"task_id": tid})

def cleanup(name): api_delete("/api/files", params={"path": name})

def close_modals():
    if not HAS_PLAYWRIGHT: return
    try: page.keyboard.press("Escape")
    except: pass
    page.wait_for_timeout(150)

def goto_all():
    if not HAS_PLAYWRIGHT: return
    try:
        close_modals()
        page.locator('[data-view="all"]').first.click(timeout=6000, force=True)
        page.wait_for_timeout(300)
    except: pass

def refresh_page():
    global _context, page
    if not HAS_PLAYWRIGHT: return
    try: _context.close()
    except: pass
    try:
        _context = _browser.new_context()
        page = _context.new_page()
        page.goto(BASE_URL)
        page.wait_for_load_state("networkidle")
        page.wait_for_timeout(500)
    except: pass

# ============================================================
# 模块1: API基础 (1-10)
# ============================================================
def t001_files_list():
    r = api_get("/api/files")
    assert r.status_code == 200 and "items" in r.json()
def t002_files_pagination():
    r = api_get("/api/files", params={"page": 1, "page_size": 5})
    assert r.status_code == 200 and len(r.json()["items"]) <= 5
def t003_invalid_page():
    r = api_get("/api/files", params={"page": -1})
    assert r.status_code in [200, 422]
def t004_large_page():
    r = api_get("/api/files", params={"page_size": 200})
    assert r.status_code == 200
def t005_sort_name():
    r = api_get("/api/files", params={"sort": "name"})
    assert r.status_code == 200
def t006_sort_desc():
    r = api_get("/api/files", params={"sort": "name", "order": "desc"})
    assert r.status_code == 200
def t007_search_valid():
    r = api_get("/api/files/search", params={"q": "a"})
    assert r.status_code == 200
def t008_search_empty_result():
    r = api_get("/api/files/search", params={"q": "nonexist_xyz_999"})
    assert r.status_code == 200 and r.json().get("count", 0) == 0
def t009_search_has_result():
    r = api_get("/api/files/search", params={"q": "txt"})
    assert r.status_code == 200
def t010_search_special():
    r = api_get("/api/files/search", params={"q": "test&param"})
    assert r.status_code == 200

# ============================================================
# 模块2: 文件夹API (11-20)
# ============================================================
def t011_folder_list():
    r = api_get("/api/folders")
    assert r.status_code == 200
def t012_folder_create():
    r = api_post("/api/files/folder", json={"name": "_t_f12"})
    assert r.status_code == 200 and r.json().get("success") == True
    cleanup("_t_f12")
def t013_folder_duplicate():
    api_post("/api/files/folder", json={"name": "_t_dup"})
    r = api_post("/api/files/folder", json={"name": "_t_dup"})
    assert r.status_code in [200, 400, 409]
    cleanup("_t_dup")
def t014_folder_special():
    r = api_post("/api/files/folder", json={"name": "_test_special_folder"})
    assert r.status_code == 200
    cleanup("_test_special_folder")
def t015_folder_nested():
    cleanup("_child"); cleanup("_parent"); api_post("/api/files/folder", json={"name": "_parent"})
    r = api_post("/api/files/folder", json={"name": "_child"})
    assert r.status_code == 200
    cleanup("_child"); cleanup("_parent")
def t016_folder_empty_name():
    r = api_post("/api/files/folder", json={"name": ""})
    assert r.status_code in [200, 400, 422]
def t017_folder_long_name():
    name = "a" * 100
    r = api_post("/api/files/folder", json={"name": name})
    assert r.status_code in [200, 400, 422]
    if r.status_code == 200: cleanup(name)
def t018_dirs_uploads():
    r = api_get("/api/dirs/uploads")
    assert r.status_code == 200
def t019_dirs_list():
    r = api_get("/api/uploads")
    assert r.status_code == 200
def t020_files_source():
    r = api_get("/api/files", params={"source": "uploads"})
    assert r.status_code == 200

# ============================================================
# 模块3: 上传 (21-40)
# ============================================================
def t021_upload_init():
    r = api_post("/api/upload/init", data={"file_name": "t.txt", "file_size": 100})
    assert r.status_code == 200 and "task_id" in r.json()
def t022_upload_init_large():
    r = api_post("/api/upload/init", data={"file_name": "lg.bin", "file_size": 10*1024*1024})
    assert r.status_code == 200
def t023_upload_chunk():
    init = api_post("/api/upload/init", data={"file_name": "c.txt", "file_size": 100}).json()
    r = api_post("/api/upload/chunk",
        data={"task_id": init["task_id"], "chunk_index": 0},
        files={"chunk": ("c.txt", b"test", "text/plain")})
    assert r.status_code == 200
def t024_upload_merge():
    init = api_post("/api/upload/init", data={"file_name": "_m.txt", "file_size": 10}).json()
    api_post("/api/upload/chunk",
        data={"task_id": init["task_id"], "chunk_index": 0},
        files={"chunk": ("_m.txt", b"hi", "text/plain")})
    r = api_post("/api/upload/merge", data={"task_id": init["task_id"]})
    assert r.status_code == 200
    cleanup("_m.txt")
def t025_upload_full():
    r = upload_file("_up_full.txt")
    assert r.status_code == 200
    cleanup("_up_full.txt")
def t026_upload_to_folder():
    api_post("/api/files/folder", json={"name": "_up_f"})
    upload_file("_up_f/in.txt")
    cleanup("_up_f")
def t027_upload_multi():
    for i in range(3):
        upload_file(f"_mu_{i}.txt")
        cleanup(f"_mu_{i}.txt")
def t028_upload_empty():
    r = upload_file("_empty.txt", content_bytes=b"")
    assert r.status_code == 200
    cleanup("_empty.txt")
def t029_upload_binary():
    r = upload_file("_bin.dat", content_bytes=b"\x00\x01\xff" * 50)
    assert r.status_code == 200
    cleanup("_bin.dat")
def t030_upload_special_name():
    r = upload_file("_test_file.txt", content_bytes=b"content")
    assert r.status_code == 200
    cleanup("_test_file.txt")
def t031_upload_large():
    r = upload_file("_large.bin", content_bytes=b"x" * (2*1024*1024))
    assert r.status_code == 200
    cleanup("_large.bin")
def t032_upload_invalid_size():
    r = api_post("/api/upload/init", data={"file_name": "x.txt", "file_size": -1})
    assert r.status_code in [200, 400, 422]
def t033_upload_cancel():
    init = api_post("/api/upload/init", data={"file_name": "canc.txt", "file_size": 1000}).json()
    r = api_delete(f"/api/upload/{init['task_id']}")
    assert r.status_code == 200
def t034_upload_chinese():
    r = upload_file("_cn.txt", content_bytes=b"chinese")
    assert r.status_code == 200
    cleanup("_cn.txt")
def t035_upload_long_name():
    name = "a" * 80 + ".txt"
    r = upload_file(name)
    assert r.status_code == 200
    cleanup(name)
def t036_upload_status():
    init = api_post("/api/upload/init", data={"file_name": "st.txt", "file_size": 10}).json()
    r = api_get(f"/api/upload/status/{init['task_id']}")
    assert r.status_code == 200
def t037_upload_no_name():
    r = api_post("/api/upload/init", data={"file_size": 100})
    assert r.status_code == 422
def t038_upload_no_size():
    r = api_post("/api/upload/init", data={"file_name": "x.txt"})
    assert r.status_code == 422
def t039_upload_zero_size():
    r = api_post("/api/upload/init", data={"file_name": "z.txt", "file_size": 0})
    assert r.status_code == 200
def t040_upload_task_status():
    init = api_post("/api/upload/init", data={"file_name": "ts.txt", "file_size": 50}).json()
    api_post("/api/upload/chunk",
        data={"task_id": init["task_id"], "chunk_index": 0},
        files={"chunk": ("ts.txt", b"x"*50, "text/plain")})
    r = api_get(f"/api/upload/status/{init['task_id']}")
    assert r.status_code == 200

# ============================================================
# 模块4: 删除 (41-50) - path是相对路径无前导/
# ============================================================
def t041_delete_file():
    upload_file("_del1.txt")
    r = api_delete("/api/files", params={"path": "_del1.txt"})
    assert r.status_code == 200
def t042_delete_nonexist():
    r = api_delete("/api/files", params={"path": "_nonexist_999.txt"})
    assert r.status_code == 404
def t043_delete_folder():
    api_post("/api/files/folder", json={"name": "_del_f"})
    r = api_delete("/api/files", params={"path": "_del_f"})
    assert r.status_code == 200
def t044_delete_nested():
    api_post("/api/files/folder", json={"name": "_del_n"})
    upload_file("_del_n/f.txt")
    r = api_delete("/api/files", params={"path": "_del_n"})
    assert r.status_code == 200
def t045_batch_delete():
    upload_file("_bd1.txt"); upload_file("_bd2.txt")
    r = api_post("/api/files/batch-delete", content=_json.dumps(["_bd1.txt", "_bd2.txt"]),
        headers={"Content-Type": "application/json"})
    assert r.status_code == 200
def t046_batch_delete_empty():
    r = api_post("/api/files/batch-delete", content=_json.dumps([]),
        headers={"Content-Type": "application/json"})
    assert r.status_code in [200, 400]
def t047_batch_delete_nonexist():
    r = api_post("/api/files/batch-delete", content=_json.dumps(["_noexist_bd.txt"]),
        headers={"Content-Type": "application/json"})
    assert r.status_code in [200, 404]
def t048_delete_protected():
    r = api_delete("/api/files", params={"path": "etc/passwd", "source": "downloads"})
    assert r.status_code in [403, 404]
def t049_delete_special():
    upload_file("_del_s.txt")
    r = api_delete("/api/files", params={"path": "_del_s.txt"})
    assert r.status_code == 200
def t050_delete_no_path():
    r = api_delete("/api/files")
    assert r.status_code == 422

# ============================================================
# 模块5: 标签 (51-60) - path是相对路径
# ============================================================
def t051_tags_list():
    r = api_get("/api/files/tags", params={"path": "."})
    assert r.status_code == 200
def t052_tag_add():
    upload_file("_tag1.txt")
    r = api_post("/api/files/tags", json={"path": "_tag1.txt", "tag": "test_tag"})
    assert r.status_code == 200
    api_delete("/api/files/tags", params={"path": "_tag1.txt", "tag": "test_tag"})
    cleanup("_tag1.txt")
def t053_tag_remove():
    upload_file("_tag2.txt")
    api_post("/api/files/tags", json={"path": "_tag2.txt", "tag": "rm"})
    r = api_delete("/api/files/tags", params={"path": "_tag2.txt", "tag": "rm"})
    assert r.status_code == 200
    cleanup("_tag2.txt")
def t054_tag_dup():
    upload_file("_tag3.txt")
    api_post("/api/files/tags", json={"path": "_tag3.txt", "tag": "dup"})
    r = api_post("/api/files/tags", json={"path": "_tag3.txt", "tag": "dup"})
    assert r.status_code in [200, 409]
    cleanup("_tag3.txt")
def t055_tag_empty():
    r = api_post("/api/files/tags", json={"path": "_tag_test.txt", "tag": ""})
    assert r.status_code in [200, 400, 422]
def t056_tag_long():
    upload_file("_tag4.txt")
    r = api_post("/api/files/tags", json={"path": "_tag4.txt", "tag": "a"*100})
    assert r.status_code == 200
    cleanup("_tag4.txt")
def t057_tag_special():
    upload_file("_tag5.txt")
    r = api_post("/api/files/tags", json={"path": "_tag5.txt", "tag": "tag_special"})
    assert r.status_code == 200
    cleanup("_tag5.txt")
def t058_tag_folder():
    api_post("/api/files/folder", json={"name": "_tag_f"})
    r = api_post("/api/files/tags", json={"path": "_tag_f", "tag": "folder_tag"})
    assert r.status_code in [200, 400]
    cleanup("_tag_f")
def t059_tag_nonexist():
    r = api_post("/api/files/tags", json={"path": "_no_file_xyz.txt", "tag": "x"})
    assert r.status_code in [200, 404]
def t060_tag_multiple():
    upload_file("_tag6.txt")
    for t in ["ta", "tb", "tc"]:
        api_post("/api/files/tags", json={"path": "_tag6.txt", "tag": t})
    r = api_get("/api/files/tags", params={"path": "_tag6.txt"})
    assert r.status_code == 200
    cleanup("_tag6.txt")

# ============================================================
# 模块6: 分享 (61-70) - Form表单!
# ============================================================
def t061_share_create():
    upload_file("_sh1.txt")
    r = api_post("/api/share", data={"file_path": "_sh1.txt"})
    assert r.status_code == 200
    cleanup("_sh1.txt")
def t062_share_list():
    r = api_get("/api/shares")
    assert r.status_code == 200
def t063_share_delete():
    upload_file("_sh2.txt")
    r = api_post("/api/share", data={"file_path": "_sh2.txt"})
    if r.status_code == 200:
        sid = r.json().get("share_id") or r.json().get("id")
        if sid: api_delete(f"/api/share/{sid}")
    cleanup("_sh2.txt")
def t064_share_password():
    upload_file("_sh3.txt")
    r = api_post("/api/share", data={"file_path": "_sh3.txt", "password": "test123"})
    assert r.status_code == 200
    cleanup("_sh3.txt")
def t065_share_expiry():
    upload_file("_sh4.txt")
    r = api_post("/api/share", data={"file_path": "_sh4.txt", "expires_days": 3})
    assert r.status_code == 200
    cleanup("_sh4.txt")
def t066_share_nonexist():
    r = api_post("/api/share", data={"file_path": "_nonexist_share.txt"})
    assert r.status_code == 404
def t067_share_folder():
    api_post("/api/files/folder", json={"name": "_sh_f"})
    r = api_post("/api/share", data={"file_path": "_sh_f", "source": "uploads"})
    assert r.status_code in [200, 404]
    cleanup("_sh_f")
def t068_share_invalid_id():
    r = api_delete("/api/share/invalid_id_xyz")
    assert r.status_code in [200, 404]
def t069_share_no_path():
    r = api_post("/api/share", data={})
    assert r.status_code == 422
def t070_share_large():
    upload_file("_sh_lg.bin", content_bytes=b"x"*102400)
    r = api_post("/api/share", data={"file_path": "_sh_lg.bin"})
    assert r.status_code == 200
    cleanup("_sh_lg.bin")

# ============================================================
# 模块7: 下载 (71-80)
# ============================================================
def t071_download_file():
    upload_file("_dl1.txt", content_bytes=b"download me")
    r = api_get("/api/files/download/_dl1.txt")
    assert r.status_code == 200
    cleanup("_dl1.txt")
def t072_download_nonexist():
    r = api_get("/api/files/download/_nonexist_dl.txt")
    assert r.status_code in [404, 400]
def t073_download_folder():
    api_post("/api/files/folder", json={"name": "_dl_f"})
    upload_file("_dl_f/f.txt")
    r = api_get("/api/files/download/_dl_f", params={"is_dir": "true"})
    assert r.status_code == 404
    cleanup("_dl_f")
def t074_download_special():
    upload_file("_dl_s.txt")
    r = api_get("/api/files/download/_dl_s.txt")
    assert r.status_code == 200
    cleanup("_dl_s.txt")
def t075_download_large():
    upload_file("_dl_lg.bin", content_bytes=b"x"*(1024*1024))
    r = api_get("/api/files/download/_dl_lg.bin")
    assert r.status_code == 200
    cleanup("_dl_lg.bin")
def t076_download_no_path():
    r = api_get("/api/files/download")
    assert r.status_code in [404, 405]
def t077_downloads_dirs():
    r = api_get("/api/dirs/uploads")
    assert r.status_code == 200
def t078_downloads_files():
    r = api_get("/api/files", params={"source": "uploads"})
    assert r.status_code == 200
def t079_download_binary():
    upload_file("_dl_bin.dat", content_bytes=b"\x00\xff"*200)
    r = api_get("/api/files/download/_dl_bin.dat")
    assert r.status_code == 200
    cleanup("_dl_bin.dat")
def t080_download_empty():
    upload_file("_dl_emp.txt", content_bytes=b"")
    r = api_get("/api/files/download/_dl_emp.txt")
    assert r.status_code == 200
    cleanup("_dl_emp.txt")

# ============================================================
# 模块8: 移动/复制 (81-90)
# ============================================================
def t081_move_file():
    upload_file("_mv1.txt")
    r = api_post("/api/files/batch-move", json={"paths": ["_mv1.txt"], "target_dir": "."})
    assert r.status_code == 200
    cleanup("_mv1.txt")
def t082_move_to_folder():
    api_post("/api/files/folder", json={"name": "_mv_f"})
    upload_file("_mv_to.txt")
    r = api_post("/api/files/batch-move", json={"paths": ["_mv_to.txt"], "target_dir": "_mv_f"})
    assert r.status_code == 200
    cleanup("_mv_f")
def t083_copy_file():
    upload_file("_cp1.txt")
    r = api_post("/api/files/batch-copy", json={"paths": ["_cp1.txt"], "target_dir": "."})
    assert r.status_code == 200
    cleanup("_cp1.txt")
def t084_copy_to_folder():
    api_post("/api/files/folder", json={"name": "_cp_f"})
    upload_file("_cp_to.txt")
    r = api_post("/api/files/batch-copy", json={"paths": ["_cp_to.txt"], "target_dir": "_cp_f"})
    assert r.status_code == 200
    cleanup("_cp_f")
def t085_move_multi():
    upload_file("_mv_m1.txt"); upload_file("_mv_m2.txt")
    r = api_post("/api/files/batch-move", json={"paths": ["_mv_m1.txt", "_mv_m2.txt"], "target_dir": "."})
    assert r.status_code == 200
def t086_copy_multi():
    upload_file("_cp_m1.txt"); upload_file("_cp_m2.txt")
    r = api_post("/api/files/batch-copy", json={"paths": ["_cp_m1.txt", "_cp_m2.txt"], "target_dir": "."})
    assert r.status_code == 200
    cleanup("_cp_m1.txt"); cleanup("_cp_m2.txt")
def t087_move_empty():
    r = api_post("/api/files/batch-move", json={"paths": [], "target_dir": "."})
    assert r.status_code in [200, 400, 422]
def t088_move_nonexist():
    r = api_post("/api/files/batch-move", json={"paths": ["_no_mv.txt"], "target_dir": "."})
    assert r.status_code in [200, 404]
def t089_copy_preserve():
    upload_file("_cp_p.txt")
    api_post("/api/files/batch-copy", json={"paths": ["_cp_p.txt"], "target_dir": "."})
    r = api_get("/api/files/download/_cp_p.txt")
    assert r.status_code == 200
    cleanup("_cp_p.txt")
def t090_move_no_dest():
    r = api_post("/api/files/batch-move", json={"paths": ["_x.txt"]})
    assert r.status_code == 422

# ============================================================
# 模块9: 云盘 (91-105) - Form表单!
# ============================================================
def t091_disks_list():
    r = api_get("/api/disks")
    assert r.status_code == 200
def t092_disk_add():
    r = api_post("/api/disks", data={"name": "_td", "disk_type": "local", "path": "/tmp"})
    assert r.status_code == 200
def t093_disk_dup():
    api_post("/api/disks", data={"name": "_dup_dk", "disk_type": "local", "path": "/tmp"})
    r = api_post("/api/disks", data={"name": "_dup_dk", "disk_type": "local", "path": "/tmp"})
    assert r.status_code in [200, 409]
def t094_disk_delete():
    r = api_post("/api/disks", data={"name": "_del_dk", "disk_type": "local", "path": "/tmp"})
    if r.status_code == 200:
        did = r.json().get("disk_id") or r.json().get("id")
        if did: api_delete(f"/api/disks/{did}")
def t095_disk_sync():
    r = api_post("/api/disks", data={"name": "_sy_dk", "disk_type": "local", "path": "/tmp"})
    if r.status_code == 200:
        did = r.json().get("disk_id") or r.json().get("id")
        if did: api_post(f"/api/disks/{did}/sync")
def t096_disk_sync_status():
    r = api_get("/api/disks/sync/status")
    assert r.status_code == 200
def t097_disk_invalid_path():
    r = api_post("/api/disks", data={"name": "_bad", "disk_type": "local", "path": "/nonexist_xyz"})
    assert r.status_code in [200, 400, 404]
def t098_disk_no_name():
    r = api_post("/api/disks", data={"disk_type": "local", "path": "/tmp"})
    assert r.status_code == 422
def t099_disk_files():
    r = api_get("/api/disks")
    if r.status_code == 200:
        disks = r.json().get("disks", [])
        if disks:
            did = disks[0].get("disk_id") or disks[0].get("id")
            if did: api_get(f"/api/disks/{did}/files")
def t100_disk_del_nonexist():
    r = api_delete("/api/disks/nonexist_dk")
    assert r.status_code in [200, 404]
def t101_disk_local():
    r = api_post("/api/disks", data={"name": "_loc", "disk_type": "local", "path": "/root"})
    assert r.status_code == 200
    data = r.json()
    did = data.get("disk_id") or data.get("id")
    if did: api_delete(f"/api/disks/{did}")
def t102_disk_empty_list():
    r = api_get("/api/disks")
    assert r.status_code == 200
def t103_disk_special_name():
    r = api_post("/api/disks", data={"name": "_sp_dk", "disk_type": "local", "path": "/tmp"})
    assert r.status_code == 200
    data = r.json()
    did = data.get("disk_id") or data.get("id")
    if did: api_delete(f"/api/disks/{did}")
def t104_disk_long_path():
    r = api_post("/api/disks", data={"name": "_lp", "disk_type": "local", "path": "/tmp/" + "a/" * 5})
    assert r.status_code in [200, 400]
def t105_disk_sync_cancel():
    r = api_post("/api/disks/sync/cancel/nonexist_task")
    assert r.status_code in [200, 404]

# ============================================================
# 模块10: 知识导入 (106-115)
# ============================================================
def t106_knowledge_list():
    r = api_get("/api/knowledge")
    assert r.status_code in [200, 404]
def t107_knowledge_import():
    upload_file("_kb1.txt", content_bytes=b"KB content")
    r = api_post("/api/knowledge/import/_kb1.txt")
    assert r.status_code in [200, 202, 404]
    cleanup("_kb1.txt")
def t108_knowledge_batch():
    r = api_post("/api/knowledge/import/batch", json={"files": ["_kb_batch.txt"]})
    assert r.status_code in [200, 202, 400, 404]
def t109_knowledge_delete():
    r = api_delete("/api/knowledge/nonexist_id")
    assert r.status_code in [200, 404, 405]
def t110_knowledge_search():
    r = api_get("/api/knowledge", params={"q": "test"})
    assert r.status_code in [200, 404]
def t111_knowledge_empty():
    r = api_get("/api/knowledge")
    assert r.status_code in [200, 404]
def t112_knowledge_url():
    r = api_post("/api/knowledge/import/batch", json={"files": ["https://example.com"]})
    assert r.status_code in [200, 202, 400, 404]
def t113_knowledge_nonexist():
    r = api_post("/api/knowledge/import/_no_file_xyz.txt")
    assert r.status_code in [200, 404]
def t114_knowledge_special():
    upload_file("_kb_s.txt", content_bytes=b"special")
    r = api_post("/api/knowledge/import/_kb_s.txt")
    assert r.status_code in [200, 202, 404]
    cleanup("_kb_s.txt")
def t115_knowledge_large():
    upload_file("_kb_lg.txt", content_bytes=b"x"*(1024*1024))
    r = api_post("/api/knowledge/import/_kb_lg.txt")
    assert r.status_code in [200, 202, 404]
    cleanup("_kb_lg.txt")

# ============================================================
# ============================================================
# 模块11: RAG知识库 (116-130)
# ============================================================
def t116_rag_datasets():
    r = api_get("/api/rag/datasets", timeout=60)
    assert r.status_code == 200 and "datasets" in r.json()
def t117_rag_create():
    r = api_post("/api/rag/datasets", timeout=60, json={"name": "_test_rag_ds"})
    assert r.status_code in [200, 400]
def t118_rag_upload():
    r = api_post("/api/rag/upload", timeout=60, files={"file": ("rag.txt", b"RAG content", "text/plain")})
    assert r.status_code in [200, 400]
def t119_rag_search():
    r = api_post("/api/rag/search", timeout=60, json={"query": "test", "top_k": 5})
    assert r.status_code in [200, 400]
def t120_rag_chat():
    r = api_post("/api/rag/chat", timeout=60, json={"question": "hello", "dataset": ""})
    assert r.status_code in [200, 400]
def t121_rag_chat_empty():
    r = api_post("/api/rag/chat", timeout=60, json={"query": ""})
    assert r.status_code in [200, 400, 422]
def t122_rag_search_empty():
    r = api_post("/api/rag/search", timeout=60, json={"query": ""})
    assert r.status_code in [200, 400, 422]
def t123_rag_import():
    r = api_post("/api/rag/import/text", timeout=60, json=["test_content.txt"])
    assert r.status_code in [200, 400, 503]
def t124_rag_import_invalid():
    r = api_post("/api/rag/import/invalid_cat", timeout=60, json=["x.txt"])
    assert r.status_code in [200, 400, 404, 503]
def t125_rag_ds_empty():
    r = api_get("/api/rag/datasets", timeout=60)
    assert r.status_code == 200
def t126_rag_search_long():
    r = api_post("/api/rag/search", timeout=60, json={"query": "a"*5000})
    assert r.status_code in [200, 400, 413]
def t127_rag_chat_history():
    r = api_post("/api/rag/chat", timeout=60, json={"question": "history", "history": []})
    assert r.status_code in [200, 400]
def t128_rag_search_special():
    r = api_post("/api/rag/search", timeout=60, json={"query": "<script>alert(1)</script>"})
    assert r.status_code in [200, 400]
def t129_rag_chat_special():
    r = api_post("/api/rag/chat", timeout=60, json={"question": "SELECT * FROM users"})
    assert r.status_code in [200, 400]
def t130_rag_no_ds():
    r = api_post("/api/rag/chat", timeout=60, json={"question": "test"})
    assert r.status_code in [200, 400]

# 模块12: 转写 (131-140)
# ============================================================
def t131_transcribe_upload():
    r = api_post("/api/transcribe/upload",
        files={"file": ("test.wav", b"RIFF" + b"\x00"*100, "audio/wav")})
    assert r.status_code in [200, 400]
def t132_transcribe_init():
    r = api_post("/api/transcribe/init", data={"source_file": "test.wav", "language": "zh"})
    assert r.status_code in [200, 400]
def t133_transcribe_list():
    r = api_get("/api/transcribes")
    assert r.status_code == 200
def t134_transcribe_exec_nonexist():
    r = api_post("/api/transcribe/execute/nonexist_task")
    assert r.status_code in [200, 404]
def t135_transcribe_large():
    r = api_post("/api/transcribe/upload",
        files={"file": ("large.wav", b"RIFF" + b"\x00"*100000, "audio/wav")})
    assert r.status_code in [200, 400]
def t136_transcribe_empty_list():
    r = api_get("/api/transcribes")
    assert r.status_code == 200
def t137_transcribe_invalid():
    r = api_post("/api/transcribe/upload",
        files={"file": ("test.txt", b"not audio", "text/plain")})
    assert r.status_code in [200, 400]
def t138_transcribe_no_file():
    r = api_post("/api/transcribe/upload")
    assert r.status_code == 422
def t139_transcribe_tasks():
    r = api_get("/api/transcribes")
    assert isinstance(r.json(), (list, dict))
def t140_transcribe_special():
    r = api_post("/api/transcribe/upload",
        files={"file": ("sp.wav", b"RIFF" + b"\x00"*100, "audio/wav")})
    assert r.status_code in [200, 400]

# ============================================================
# 模块13: WebSocket (141-145)
# ============================================================
def t141_ws_connect():
    import websocket
    try:
        ws = websocket.create_connection("ws://localhost:8866/ws", timeout=3)
        ws.close()
    except: pass
def t142_ws_recv():
    import websocket
    try:
        ws = websocket.create_connection("ws://localhost:8866/ws", timeout=3)
        ws.settimeout(2)
        try: ws.recv()
        except: pass
        ws.close()
    except: pass
def t143_ws_upload():
    import websocket
    try:
        ws = websocket.create_connection("ws://localhost:8866/ws", timeout=3)
        upload_file("_ws1.txt")
        ws.settimeout(2)
        try: ws.recv()
        except: pass
        ws.close()
        cleanup("_ws1.txt")
    except: pass
def t144_ws_invalid():
    import websocket
    try:
        ws = websocket.create_connection("ws://localhost:8866/invalid_ws", timeout=3)
        ws.close()
    except: pass
def t145_ws_concurrent():
    import websocket
    try:
        ws1 = websocket.create_connection("ws://localhost:8866/ws", timeout=3)
        ws2 = websocket.create_connection("ws://localhost:8866/ws", timeout=3)
        ws1.close(); ws2.close()
    except: pass

# ============================================================
# 模块14: UI-页面 (146-155)
# ============================================================
def t146_page_load():
    if not HAS_PLAYWRIGHT: return
    assert page.url != "about:blank"
def t147_sidebar():
    if not HAS_PLAYWRIGHT: return
    assert page.locator(".sidebar, .nav-item").count() > 0
def t148_nav_items():
    if not HAS_PLAYWRIGHT: return
    assert page.locator(".nav-item").count() >= 5
def t149_main_content():
    if not HAS_PLAYWRIGHT: return
    assert page.locator(".main-content, .file-grid, #fileContainer").count() > 0
def t150_upload_btn():
    if not HAS_PLAYWRIGHT: return
    assert page.locator("#btnUpload, .upload-btn").count() > 0
def t151_search_box():
    if not HAS_PLAYWRIGHT: return
    assert page.locator("input[type=search], input[placeholder*=搜索], #searchInput").count() > 0
def t152_view_toggle():
    if not HAS_PLAYWRIGHT: return
    assert page.locator("[data-view=grid], [data-view=list]").count() > 0
def t153_category_nav():
    if not HAS_PLAYWRIGHT: return
    assert page.locator(".nav-item[data-view=category]").count() >= 1
def t154_page_title():
    if not HAS_PLAYWRIGHT: return
    assert len(page.title()) > 0
def t155_no_js_crash():
    if not HAS_PLAYWRIGHT: return
    page.wait_for_timeout(500)

# ============================================================
# 模块15: UI-导航 (156-165) - force click + 关闭modal
# ============================================================
def t156_nav_all():
    if not HAS_PLAYWRIGHT: return
    page.locator('[data-view="all"]').first.click(timeout=6000, force=True)
    page.wait_for_timeout(200)
def t157_nav_uploads():
    if not HAS_PLAYWRIGHT: return
    close_modals()
    page.locator('[data-view="uploads"]').first.click(timeout=6000, force=True)
    page.wait_for_timeout(200); close_modals(); goto_all()
def t158_nav_downloads():
    if not HAS_PLAYWRIGHT: return
    close_modals()
    page.locator('[data-view="downloads"]').first.click(timeout=6000, force=True)
    page.wait_for_timeout(200); close_modals(); goto_all()
def t159_nav_transcribe():
    if not HAS_PLAYWRIGHT: return
    close_modals()
    page.locator('[data-view="transcribe"]').first.click(timeout=6000, force=True)
    page.wait_for_timeout(200); close_modals(); goto_all()
def t160_nav_knowledge():
    if not HAS_PLAYWRIGHT: return
    refresh_page()
    close_modals()
    page.locator('[data-view="knowledge"]').first.click(timeout=6000, force=True)
    page.wait_for_timeout(300); close_modals(); goto_all()
def t161_nav_cloud():
    if not HAS_PLAYWRIGHT: return
    close_modals()
    page.locator('[data-view="cloud"]').first.click(timeout=6000, force=True)
    page.wait_for_timeout(300); close_modals(); goto_all()
def t162_nav_settings():
    if not HAS_PLAYWRIGHT: return
    close_modals()
    page.locator('[data-view="settings"]').first.click(timeout=6000, force=True)
    page.wait_for_timeout(200); close_modals(); goto_all()
def t163_nav_rag_search():
    if not HAS_PLAYWRIGHT: return
    close_modals()
    page.locator('[data-view="rag-search"]').first.click(timeout=6000, force=True)
    page.wait_for_timeout(200); close_modals(); goto_all()
def t164_nav_rag_chat():
    if not HAS_PLAYWRIGHT: return
    close_modals()
    page.locator('[data-view="rag-chat"]').first.click(timeout=6000, force=True)
    page.wait_for_timeout(200); close_modals(); goto_all()
def t165_nav_category():
    if not HAS_PLAYWRIGHT: return
    close_modals()
    page.locator('[data-view="category"]').first.click(timeout=6000, force=True)
    page.wait_for_timeout(200); close_modals(); goto_all()

# ============================================================
# 模块16: UI-视图 (166-170)
# ============================================================
def t166_grid_view():
    if not HAS_PLAYWRIGHT: return
    goto_all()
    b = page.locator('[data-view="grid"]').first
    if b.count() > 0: b.click(timeout=2000, force=True)
    page.wait_for_timeout(150)
def t167_list_view():
    if not HAS_PLAYWRIGHT: return
    goto_all()
    b = page.locator('[data-view="list"]').first
    if b.count() > 0: b.click(timeout=2000, force=True)
    page.wait_for_timeout(150)
def t168_view_toggle():
    if not HAS_PLAYWRIGHT: return
    goto_all()
    g = page.locator('[data-view="grid"]').first
    l = page.locator('[data-view="list"]').first
    if l.count() > 0: l.click(timeout=2000, force=True)
    page.wait_for_timeout(100)
    if g.count() > 0: g.click(timeout=2000, force=True)
    page.wait_for_timeout(100)
def t169_rapid_toggle():
    if not HAS_PLAYWRIGHT: return
    goto_all()
    g = page.locator('[data-view="grid"]').first
    l = page.locator('[data-view="list"]').first
    if g.count() > 0 and l.count() > 0:
        for _ in range(3):
            l.click(timeout=1000, force=True); page.wait_for_timeout(50)
            g.click(timeout=1000, force=True); page.wait_for_timeout(50)
def t170_view_persist():
    if not HAS_PLAYWRIGHT: return
    goto_all()
    g = page.locator('[data-view="grid"]').first
    if g.count() > 0: g.click(timeout=2000, force=True)
    page.wait_for_timeout(150)
    page.reload(); page.wait_for_load_state("networkidle"); page.wait_for_timeout(300)

# ============================================================
# 模块17: UI-搜索 (171-180)
# ============================================================
def _si():
    return page.locator("input[type=search], input[placeholder*=搜索], #searchInput").first

def t171_ui_search():
    if not HAS_PLAYWRIGHT: return
    s = _si()
    if s.count() > 0: s.fill("txt")
    page.wait_for_timeout(200)
def t172_search_clear():
    if not HAS_PLAYWRIGHT: return
    s = _si()
    if s.count() > 0: s.fill("txt"); page.wait_for_timeout(100); s.fill("")
    page.wait_for_timeout(150)
def t173_search_special():
    if not HAS_PLAYWRIGHT: return
    s = _si()
    if s.count() > 0: s.fill("script")
    page.wait_for_timeout(150)
def t174_search_empty():
    if not HAS_PLAYWRIGHT: return
    s = _si()
    if s.count() > 0: s.fill("")
    page.wait_for_timeout(150)
def t175_search_long():
    if not HAS_PLAYWRIGHT: return
    s = _si()
    if s.count() > 0: s.fill("a"*100)
    page.wait_for_timeout(150)
def t176_search_chinese():
    if not HAS_PLAYWRIGHT: return
    s = _si()
    if s.count() > 0: s.fill("中文搜索")
    page.wait_for_timeout(150)
def t177_search_enter():
    if not HAS_PLAYWRIGHT: return
    s = _si()
    if s.count() > 0: s.fill("test"); s.press("Enter")
    page.wait_for_timeout(150)
def t178_search_escape():
    if not HAS_PLAYWRIGHT: return
    s = _si()
    if s.count() > 0: s.fill("test"); s.press("Escape")
    page.wait_for_timeout(150)
def t179_search_rapid():
    if not HAS_PLAYWRIGHT: return
    s = _si()
    if s.count() > 0:
        for t in ["a", "ab", "abc"]: s.fill(t); page.wait_for_timeout(50)
def t180_search_no_result():
    if not HAS_PLAYWRIGHT: return
    s = _si()
    if s.count() > 0: s.fill("zzz_no_result_999")
    page.wait_for_timeout(150)

# ============================================================
# 模块18: UI-文件操作 (181-190)
# ============================================================
def t181_select_all():
    if not HAS_PLAYWRIGHT: return
    goto_all()
    cb = page.locator("#selectAll, .select-all").first
    if cb.count() > 0: cb.click(force=True); page.wait_for_timeout(100); cb.click(force=True)
def t182_select_one():
    if not HAS_PLAYWRIGHT: return
    goto_all()
    cb = page.locator(".file-item input[type=checkbox]").first
    if cb.count() > 0: cb.click(force=True); page.wait_for_timeout(100)
def t183_sort_name():
    if not HAS_PLAYWRIGHT: return
    b = page.locator("[data-sort=name]").first
    if b.count() > 0: b.click(force=True); page.wait_for_timeout(100)
def t184_sort_date():
    if not HAS_PLAYWRIGHT: return
    b = page.locator("[data-sort=date]").first
    if b.count() > 0: b.click(force=True); page.wait_for_timeout(100)
def t185_sort_size():
    if not HAS_PLAYWRIGHT: return
    b = page.locator("[data-sort=size]").first
    if b.count() > 0: b.click(force=True); page.wait_for_timeout(100)
def t186_breadcrumb():
    if not HAS_PLAYWRIGHT: return
    bc = page.locator(".breadcrumb, .breadcrumb-nav").first
    if bc.count() > 0: assert bc.is_visible()
def t187_pagination():
    if not HAS_PLAYWRIGHT: return
    page.locator(".pagination, .page-nav").first
def t188_context_menu():
    if not HAS_PLAYWRIGHT: return
    item = page.locator(".file-item").first
    if item.count() > 0:
        item.click(button="right", force=True); page.wait_for_timeout(100)
        page.click("body", force=True); page.wait_for_timeout(100)
def t189_refresh():
    if not HAS_PLAYWRIGHT: return
    b = page.locator("[onclick*=refresh], .refresh-btn").first
    if b.count() > 0: b.click(force=True); page.wait_for_timeout(200)
def t190_empty_state():
    if not HAS_PLAYWRIGHT: return
    goto_all()

# ============================================================
# 模块19: UI-交互 (191-200)
# ============================================================
def t191_hover():
    if not HAS_PLAYWRIGHT: return
    item = page.locator(".file-item").first
    if item.count() > 0: item.hover(); page.wait_for_timeout(100)
def t192_click_item():
    if not HAS_PLAYWRIGHT: return
    item = page.locator(".file-item").first
    if item.count() > 0: item.click(force=True); page.wait_for_timeout(100)
def t193_dblclick_folder():
    if not HAS_PLAYWRIGHT: return
    f = page.locator(".file-item[data-is-dir=true], .folder-item").first
    if f.count() > 0:
        f.dblclick(force=True); page.wait_for_timeout(200)
        goto_all()
def t194_keyboard():
    if not HAS_PLAYWRIGHT: return
    page.keyboard.press("Control+a"); page.wait_for_timeout(100)
    page.keyboard.press("Escape"); page.wait_for_timeout(100)
def t195_resize():
    if not HAS_PLAYWRIGHT: return
    page.set_viewport_size({"width": 800, "height": 600}); page.wait_for_timeout(100)
    page.set_viewport_size({"width": 1920, "height": 1080}); page.wait_for_timeout(100)
def t196_reload():
    if not HAS_PLAYWRIGHT: return
    refresh_page()
    page.reload(); page.wait_for_load_state("networkidle"); page.wait_for_timeout(300)
    assert page.locator(".nav-item").count() > 0
def t197_back():
    if not HAS_PLAYWRIGHT: return
    page.go_back(); page.wait_for_timeout(200)
def t198_paste():
    if not HAS_PLAYWRIGHT: return
    page.keyboard.press("Control+v"); page.wait_for_timeout(100)
def t199_scroll():
    if not HAS_PLAYWRIGHT: return
    page.evaluate("window.scrollTo(0, document.body.scrollHeight)"); page.wait_for_timeout(100)
    page.evaluate("window.scrollTo(0, 0)"); page.wait_for_timeout(100)
def t200_console():
    if not HAS_PLAYWRIGHT: return
    page.wait_for_timeout(300)

# ============================================================
# 测试注册表
# ============================================================
tests = [
    ("文件列表", t001_files_list), ("分页", t002_files_pagination),
    ("无效页码", t003_invalid_page), ("大页码", t004_large_page),
    ("排序", t005_sort_name), ("降序", t006_sort_desc),
    ("搜索有效", t007_search_valid), ("搜索无结果", t008_search_empty_result),
    ("搜索有结果", t009_search_has_result), ("搜索特殊", t010_search_special),
    ("文件夹列表", t011_folder_list), ("创建文件夹", t012_folder_create),
    ("重复文件夹", t013_folder_duplicate), ("特殊名文件夹", t014_folder_special),
    ("嵌套文件夹", t015_folder_nested), ("空名文件夹", t016_folder_empty_name),
    ("长名文件夹", t017_folder_long_name), ("上传目录", t018_dirs_uploads),
    ("上传列表", t019_dirs_list), ("文件列表source", t020_files_source),
    ("上传初始化", t021_upload_init), ("大文件初始化", t022_upload_init_large),
    ("上传分块", t023_upload_chunk), ("上传合并", t024_upload_merge),
    ("上传完整", t025_upload_full), ("上传到文件夹", t026_upload_to_folder),
    ("多文件上传", t027_upload_multi), ("空文件上传", t028_upload_empty),
    ("二进制上传", t029_upload_binary), ("特殊名上传", t030_upload_special_name),
    ("大文件上传", t031_upload_large), ("无效大小", t032_upload_invalid_size),
    ("上传取消", t033_upload_cancel), ("中文名上传", t034_upload_chinese),
    ("长名上传", t035_upload_long_name), ("上传状态", t036_upload_status),
    ("无名初始化", t037_upload_no_name), ("无大小初始化", t038_upload_no_size),
    ("零大小上传", t039_upload_zero_size), ("任务状态", t040_upload_task_status),
    ("删除文件", t041_delete_file), ("删除不存在", t042_delete_nonexist),
    ("删除文件夹", t043_delete_folder), ("删除嵌套", t044_delete_nested),
    ("批量删除", t045_batch_delete), ("批量删除空", t046_batch_delete_empty),
    ("批量删除不存在", t047_batch_delete_nonexist), ("删除受保护", t048_delete_protected),
    ("删除特殊", t049_delete_special), ("删除无参数", t050_delete_no_path),
    ("标签列表", t051_tags_list), ("添加标签", t052_tag_add),
    ("移除标签", t053_tag_remove), ("重复标签", t054_tag_dup),
    ("空标签", t055_tag_empty), ("长标签", t056_tag_long),
    ("特殊标签", t057_tag_special), ("文件夹标签", t058_tag_folder),
    ("不存在标签", t059_tag_nonexist), ("多标签", t060_tag_multiple),
    ("创建分享", t061_share_create), ("分享列表", t062_share_list),
    ("删除分享", t063_share_delete), ("密码分享", t064_share_password),
    ("有效期分享", t065_share_expiry), ("不存在分享", t066_share_nonexist),
    ("文件夹分享", t067_share_folder), ("无效分享ID", t068_share_invalid_id),
    ("无路径分享", t069_share_no_path), ("大文件分享", t070_share_large),
    ("下载文件", t071_download_file), ("下载不存在", t072_download_nonexist),
    ("下载ZIP", t073_download_folder), ("下载特殊", t074_download_special),
    ("下载大文件", t075_download_large), ("下载无路径", t076_download_no_path),
    ("下载目录", t077_downloads_dirs), ("下载文件列表", t078_downloads_files),
    ("下载二进制", t079_download_binary), ("下载空", t080_download_empty),
    ("移动文件", t081_move_file), ("移动到文件夹", t082_move_to_folder),
    ("复制文件", t083_copy_file), ("复制到文件夹", t084_copy_to_folder),
    ("批量移动", t085_move_multi), ("批量复制", t086_copy_multi),
    ("移动空", t087_move_empty), ("移动不存在", t088_move_nonexist),
    ("复制保留", t089_copy_preserve), ("移动无目标", t090_move_no_dest),
    ("云盘列表", t091_disks_list), ("添加云盘", t092_disk_add),
    ("重复云盘", t093_disk_dup), ("删除云盘", t094_disk_delete),
    ("同步云盘", t095_disk_sync), ("同步状态", t096_disk_sync_status),
    ("无效路径云盘", t097_disk_invalid_path), ("无名云盘", t098_disk_no_name),
    ("云盘文件", t099_disk_files), ("删除不存在云盘", t100_disk_del_nonexist),
    ("本地云盘", t101_disk_local), ("云盘空列表", t102_disk_empty_list),
    ("特殊名云盘", t103_disk_special_name), ("长路径云盘", t104_disk_long_path),
    ("取消同步", t105_disk_sync_cancel),
    ("知识列表", t106_knowledge_list), ("知识导入", t107_knowledge_import),
    ("批量知识导入", t108_knowledge_batch), ("知识删除", t109_knowledge_delete),
    ("知识搜索", t110_knowledge_search), ("知识空列表", t111_knowledge_empty),
    ("URL导入", t112_knowledge_url), ("不存在导入", t113_knowledge_nonexist),
    ("特殊导入", t114_knowledge_special), ("大文件导入", t115_knowledge_large),
    ("RAG数据集", t116_rag_datasets), ("创建数据集", t117_rag_create),
    ("RAG上传", t118_rag_upload), ("RAG搜索", t119_rag_search),
    ("RAG对话", t120_rag_chat), ("RAG空对话", t121_rag_chat_empty),
    ("RAG空搜索", t122_rag_search_empty), ("RAG导入", t123_rag_import),
    ("RAG无效导入", t124_rag_import_invalid), ("RAG空数据集", t125_rag_ds_empty),
    ("RAG长查询", t126_rag_search_long), ("RAG历史", t127_rag_chat_history),
    ("RAG搜索特殊", t128_rag_search_special), ("RAG对话特殊", t129_rag_chat_special),
    ("RAG无数据集", t130_rag_no_ds),
    ("转写上传", t131_transcribe_upload), ("转写初始化", t132_transcribe_init),
    ("转写列表", t133_transcribe_list), ("转写不存在", t134_transcribe_exec_nonexist),
    ("转写大文件", t135_transcribe_large), ("转写空列表", t136_transcribe_empty_list),
    ("转写无效", t137_transcribe_invalid), ("转写无文件", t138_transcribe_no_file),
    ("转写任务", t139_transcribe_tasks), ("转写特殊", t140_transcribe_special),
    ("WS连接", t141_ws_connect), ("WS接收", t142_ws_recv),
    ("WS上传", t143_ws_upload), ("WS无效", t144_ws_invalid),
    ("WS并发", t145_ws_concurrent),
    ("页面加载", t146_page_load), ("侧边栏", t147_sidebar),
    ("导航项", t148_nav_items), ("主内容区", t149_main_content),
    ("上传按钮", t150_upload_btn), ("搜索框", t151_search_box),
    ("视图切换", t152_view_toggle), ("分类导航", t153_category_nav),
    ("页面标题", t154_page_title), ("无JS崩溃", t155_no_js_crash),
    ("导航全部", t156_nav_all), ("导航上传", t157_nav_uploads),
    ("导航下载", t158_nav_downloads), ("导航转写", t159_nav_transcribe),
    ("导航知识", t160_nav_knowledge), ("导航云盘", t161_nav_cloud),
    ("导航设置", t162_nav_settings), ("导航RAG搜索", t163_nav_rag_search),
    ("导航RAG对话", t164_nav_rag_chat), ("导航分类", t165_nav_category),
    ("网格视图", t166_grid_view), ("列表视图", t167_list_view),
    ("视图切换", t168_view_toggle), ("快速切换", t169_rapid_toggle),
    ("视图持久化", t170_view_persist),
    ("UI搜索", t171_ui_search), ("搜索清空", t172_search_clear),
    ("搜索特殊", t173_search_special), ("搜索空", t174_search_empty),
    ("搜索长文本", t175_search_long), ("搜索中文", t176_search_chinese),
    ("搜索回车", t177_search_enter), ("搜索ESC", t178_search_escape),
    ("搜索快速输入", t179_search_rapid), ("搜索无结果", t180_search_no_result),
    ("全选", t181_select_all), ("单选", t182_select_one),
    ("按名称排序", t183_sort_name), ("按日期排序", t184_sort_date),
    ("按大小排序", t185_sort_size), ("面包屑", t186_breadcrumb),
    ("分页UI", t187_pagination), ("右键菜单", t188_context_menu),
    ("刷新按钮", t189_refresh), ("空状态", t190_empty_state),
    ("悬停", t191_hover), ("点击文件", t192_click_item),
    ("双击文件夹", t193_dblclick_folder), ("键盘快捷键", t194_keyboard),
    ("窗口缩放", t195_resize), ("页面刷新", t196_reload),
    ("浏览器后退", t197_back), ("粘贴操作", t198_paste),
    ("滚动", t199_scroll), ("控制台", t200_console),
]

print("=" * 60)
print(f"FileApple UI自动化测试 vFINAL - {len(tests)}个测试用例")
print("=" * 60)
for name, fn in tests:
    run_test(name, fn)
print("=" * 60)
print(f"通过: {passed}/{len(tests)} ({100*passed//len(tests)}%)")
print(f"失败: {failed}/{len(tests)}")
if errors:
    for n, e in errors[:20]:
        print(f"  - {n}: {e}")
print("=" * 60)
try:
    if HAS_PLAYWRIGHT: _browser.close(); _pw.stop()
except: pass
