# FileApple 项目开发规范

## 项目概述

- **项目名称**: FileApple / 学习目录
- **项目路径**: `/root/lvhuamin/fileapple`
- **服务端口**: 8866
- **功能定位**: 分片上传 + 断点续传 + 音频/视频转文字 + 文件管理 + 批量转写

## 技术栈

- **后端框架**: FastAPI + uvicorn
- **AI 模型**: Whisper (音频转文字) - 远程31服务器 + 本地faster-whisper备用
- **数据库**: SQLite
- **实时通信**: WebSocket
- **存储**: 本地文件系统
- **定时任务**: APScheduler (自动扫描+转写)

## 目录结构

```
/root/lvhuamin/fileapple/
├── backend/
│   ├── main.py                # FastAPI 主程序 (API入口 + 定时任务)
│   ├── database.py            # 数据库模块 (SQLite封装)
│   ├── knowledge/
│   │   ├── transcriber.py     # 音视频转写 (远程31服务器 + 本地备用)
│   │   ├── extractor.py       # 文档文本提取
│   │   ├── openviking_writer.py # OpenViking写入
│   │   └── config.yaml        # 知识线配置
│   └── uploads/               # 上传文件目录 (已在config中配置)
├── frontend/
│   ├── index.html             # Web UI
│   ├── style.css              # 样式
│   └── app.js                 # 前端逻辑 (含IndexedDB上传队列)
├── requirements.txt           # Python 依赖
├── start.sh                   # 启动脚本
├── README.md                  # 项目说明
└── CLAUDE.md                  # 本文件
```

## 数据目录

| 目录 | 路径 | 说明 |
|------|------|------|
| 上传文件 | `/root/lvhuamin/fileapple/uploads/` | 用户上传的文件 (支持子目录) |
| 下载目录 | `/root/.openclaw/workspace/learning/downloads/` | 下载缓存 |
| 分片缓存 | `/root/.openclaw/workspace/learning/chunks/` | 上传分片临时存储 |
| 转写结果 | `/root/.openclaw/workspace/learning/transcripts/` | Whisper 转写输出 |
| 断点记录 | `/root/.openclaw/workspace/learning/checkpoints/` | 断点续传状态 |
| 数据库 | `/root/.openclaw/workspace/learning/learning.db` | SQLite 数据库 |

## 数据库表

1. **upload_tasks** - 上传任务
2. **chunks** - 分片记录
3. **transcribe_tasks** - 转写任务
4. **folder_uploads** - 文件夹上传
5. **share_links** - 分享链接
6. **extract_tasks** - 文本提取任务 (含 folder_batch_id, sort_order)
7. **folder_batch** - 文件夹批量转写任务 (含 merged_text, merged_char_count)
8. **files** - 文件记录
9. **knowledge_files** - 知识库文件

## 核心 API

### 上传
- `POST /api/upload/init` - 初始化上传
- `POST /api/upload/chunk` - 上传分片
- `POST /api/upload/merge` - 合并文件 (自动处理文件名冲突)
- `GET /api/upload/status/{id}` - 状态查询
- `DELETE /api/upload/{id}` - 删除任务

### 文本提取
- `POST /api/extract/upload` - 上传并提取文本
- `POST /api/extract/process/{task_id}` - 手动触发提取
- `GET /api/extract/tasks` - 列出提取任务
- `POST /api/extract/folder` - 批量转写整个文件夹
- `GET /api/extract/folder/{batch_id}` - 批量任务状态
- `GET /api/extract/folders` - 列出所有批量任务

### 文件管理
- `GET /api/files` - 文件列表
- `GET /api/files/search` - 搜索文件
- `GET /api/files/preview/{path}` - 预览
- `DELETE /api/files` - 删除文件

### 分享
- `POST /api/share` - 创建分享
- `GET /api/share/{id}` - 分享信息
- `GET /s/{share_id}` - 访问分享

### 实时
- `WS /ws` - WebSocket (进度推送/心跳)

## 自动化流程

### 定时任务 (APScheduler)
- **文本提取**: 每4小时自动扫描上传目录，处理新文件
- **知识扫描**: 每24小时扫描知识库目录

### 文件夹批量转写流程
1. 用户上传文件夹到 `/root/lvhuamin/fileapple/uploads/`
2. 系统自动检测 (≥2个媒体文件的文件夹)
3. 创建批量转写任务
4. 按文件名排序，逐个调用31服务器转写
5. 用 `asyncio.to_thread` 异步处理，不阻塞事件循环
6. 整合所有转写结果，生成完整文档
7. 保存为 `{文件夹名}_完整转写.txt`

## 远程服务

### 31服务器 (192.168.0.31)
- **Whisper API**: http://192.168.0.31:8089
- **SSH**: `sshpass -p 'Thetang@2307' ssh root@192.168.0.31`
- **模型**: faster-whisper (small, CPU int8)
- **超时**: 1小时 (大文件)

## 开发规范

### 事实依据原则（最高优先级）
处理问题时**必须提供客观证据**，严禁主观结论。

**证据类型：**
1. 终端输出（curl返回、命令结果）
2. JSON/日志文件（带文件路径）
3. HTTP status 码

**禁止用语：** "测试正常"、"看起来没问题"、"应该可以"

### 代码风格
- 使用类型注解 (typing.Optional, typing.List 等)
- 异步函数使用 async/await
- 错误处理返回 HTTPException
- 同步阻塞调用用 `asyncio.to_thread` 包装

### 安全限制
- 仅允许访问 uploads/downloads 目录
- 使用 ALLOWED_DIRS 白名单检查
- 分享链接支持密码保护和过期时间

### 配置常量
```python
CHUNK_SIZE = 5 * 1024 * 1024  # 5MB
API_PORT = 8866
BASE_DIR = Path("/root/.openclaw/workspace/learning")
UPLOADS_DIR = Path("/root/lvhuamin/fileapple/uploads")
```

## 服务管理

```bash
# 查看进程
ps aux | grep "python.*main.py"

# 重启服务
lsof -ti:8866 | xargs kill -9 && cd /root/lvhuamin/fileapple/backend && nohup python3 main.py > /tmp/fileapple.log 2>&1 &

# 查看日志
tail -f /tmp/fileapple.log
tail -f /tmp/fileapple_error.log

# 查看数据库
sqlite3 /root/.openclaw/workspace/learning/learning.db ".tables"
sqlite3 /root/.openclaw/workspace/learning/learning.db "SELECT * FROM folder_batch;"
```

## 注意事项

1. **路径迁移**: 2026-06-11 从 `/root/lvhuamin/temp/下载/fileapple` 迁移至此
2. **上传目录**: 2026-06-20 从隐藏目录迁移至 `/root/lvhuamin/fileapple/uploads/`
3. **Whisper 模型**: 首次转写时自动下载，约 140MB
4. **分片大小**: 5MB，适合大多数网络环境
5. **断点续传**: 基于分片哈希实现，中断后可继续
6. **文件名冲突**: 自动添加后缀 (1), (2), ...
7. **异步处理**: 使用 `asyncio.to_thread` 避免阻塞事件循环
8. **大文件转写**: 2小时音频约需15-30分钟，使用远程31服务器
