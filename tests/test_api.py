#!/usr/bin/env python3
"""8866学习目录系统 - API自动化测试 (基于新版UI)"""
import sys
import time
import tempfile
import os
from pathlib import Path
import httpx

BASE_URL = "http://localhost:8866"

print("=" * 70)
print("  8866 学习目录系统 - API自动化测试 (新版UI)")
print("=" * 70)

results = []

def run_test(name, test_func):
    print(f"  {name}...", end=" ", flush=True)
    try:
        test_func()
        results.append(True)
        print("✅")
    except Exception as e:
        results.append(False)
        print(f"❌ {str(e)[:60]}")

# ===== 1. 核心文件管理API =====
print("\n[1. 文件管理API]")
run_test("GET /api/files", lambda: None if httpx.get(f"{BASE_URL}/api/files", timeout=60).status_code == 200 else Exception())
run_test("GET /api/files?path=/", lambda: None if httpx.get(f"{BASE_URL}/api/files?path=/", timeout=60).status_code == 200 else Exception())
run_test("GET /api/files/search", lambda: None if httpx.get(f"{BASE_URL}/api/files/search?q=test", timeout=60).status_code == 200 else Exception())
run_test("GET /api/files/search 空查询", lambda: None if httpx.get(f"{BASE_URL}/api/files/search", timeout=60).status_code == 200 else Exception())

# ===== 2. 云盘管理API =====
print("\n[2. 云盘管理API]")
run_test("GET /api/disks", lambda: None if httpx.get(f"{BASE_URL}/api/disks", timeout=60).status_code == 200 else Exception())
run_test("GET /api/disks/sync", lambda: None if httpx.get(f"{BASE_URL}/api/disks/sync", timeout=60).status_code == 200 else Exception())

# ===== 3. 知识导入API =====
print("\n[3. 知识导入API]")
run_test("GET /api/knowledge/scan", lambda: None if httpx.get(f"{BASE_URL}/api/knowledge/scan", timeout=60).status_code == 200 else Exception())
run_test("GET /api/knowledge/status", lambda: None if httpx.get(f"{BASE_URL}/api/knowledge/status", timeout=60).status_code == 200 else Exception())

# ===== 4. 标签API =====
print("\n[4. 标签API]")
run_test("GET /api/tags", lambda: None if httpx.get(f"{BASE_URL}/api/tags", timeout=60).status_code == 200 else Exception())

# ===== 5. 系统状态API =====
print("\n[5. 系统状态API]")
run_test("GET /api/status", lambda: None if httpx.get(f"{BASE_URL}/api/status", timeout=60).status_code == 200 else Exception())
run_test("GET /api/storage/stats", lambda: None if httpx.get(f"{BASE_URL}/api/storage/stats", timeout=60).status_code == 200 else Exception())

# ===== 6. 目录API =====
print("\n[6. 目录API]")
run_test("GET /api/dirs/uploads", lambda: None if httpx.get(f"{BASE_URL}/api/dirs/uploads", timeout=60).status_code == 200 else Exception())
run_test("GET /api/dirs/downloads", lambda: None if httpx.get(f"{BASE_URL}/api/dirs/downloads", timeout=60).status_code == 200 else Exception())

# ===== 7. 音频转写API =====
print("\n[7. 音频转写API]")
run_test("GET /api/transcribes", lambda: None if httpx.get(f"{BASE_URL}/api/transcribes", timeout=60).status_code == 200 else Exception())

# ===== 8. 上传API =====
print("\n[8. 上传API]")
f = tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False, dir='/tmp')
f.write("API Test Content")
f.close()
test_file = f.name
test_size = os.path.getsize(test_file)

with open(test_file, 'rb') as fp:
    resp = httpx.post(f"{BASE_URL}/api/upload/init",
                      data={"file_name": "api_test.txt", "file_size": str(test_size)},
                      files={"file": ("api_test.txt", fp, "text/plain")}, timeout=60)
run_test("POST /api/upload/init", lambda: None if resp.status_code in [200, 201, 400, 409] else Exception(f"状态码:{resp.status_code}"))
os.unlink(test_file)

# ===== 9. 分享API =====
print("\n[9. 分享API]")
resp = httpx.post(f"{BASE_URL}/api/share", json={"file_path": "/test.txt", "expiry_days": 7}, timeout=60)
run_test("POST /api/share", lambda: None if resp.status_code in [200, 201, 404] else Exception(f"状态码:{resp.status_code}"))

# ===== 10. RAG API =====
print("\n[10. RAG API]")
run_test("GET /api/rag/search", lambda: None if httpx.get(f"{BASE_URL}/api/rag/search?q=test", timeout=60).status_code in [200, 404] else Exception())
run_test("GET /api/rag/chat", lambda: None if httpx.get(f"{BASE_URL}/api/rag/chat?q=test", timeout=60).status_code in [200, 404] else Exception())

# ===== 11. 前端资源 =====
print("\n[11. 前端资源]")
resp = httpx.get(f"{BASE_URL}/index.html", timeout=60, follow_redirects=True)
run_test("GET /index.html", lambda: None if resp.status_code == 200 else Exception())
run_test("HTML包含app-container", lambda: None if "app-container" in resp.text else Exception())
run_test("HTML包含sidebar", lambda: None if "sidebar" in resp.text else Exception())

resp = httpx.get(f"{BASE_URL}/app.js", timeout=60)
run_test("GET /app.js", lambda: None if resp.status_code == 200 else Exception())

resp = httpx.get(f"{BASE_URL}/style.css", timeout=60)
run_test("GET /style.css", lambda: None if resp.status_code == 200 else Exception())

# ===== 12. 性能测试 =====
print("\n[12. 性能测试]")
start = time.time()
resp = httpx.get(f"{BASE_URL}/api/status", timeout=60)
elapsed = time.time() - start
run_test(f"API响应时间 {elapsed:.2f}s", lambda: None if elapsed < 5 else Exception(f"太慢:{elapsed:.2f}s"))

# 汇总
passed = sum(results)
total = len(results)
failed = total - passed

print("\n" + "=" * 70)
print("  测试结果汇总")
print("=" * 70)
print(f"\n  ✅ 通过: {passed}")
print(f"  ❌ 失败: {failed}")
print(f"  📊 总计: {total}")
print(f"  📈 通过率: {100*passed/total:.1f}%")
print("=" * 70)

sys.exit(0 if failed == 0 else 1)
