#!/bin/bash
# 学习目录启动脚本

cd "$(dirname "$0")"

echo "=========================================="
echo "  学习目录服务启动"
echo "=========================================="

# 检查依赖
if ! pip3 show fastapi >/dev/null 2>&1; then
    echo "📦 安装依赖..."
    pip3 install -r requirements.txt -q
fi

# 启动服务
echo "🚀 启动后端服务 (端口 8866)..."
cd backend
python3 main.py
