#!/usr/bin/env python3
"""独立测试运行器"""
import subprocess
import sys

result = subprocess.run([sys.executable, "tests/test_ui.py"], cwd="/root/lvhuamin/fileapple")
sys.exit(result.returncode)
