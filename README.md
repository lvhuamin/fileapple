# 学习目录 - FileApple

> 分片上传 + 断点续传 + 文件夹上传 + 音频转文字

## 项目结构

```
/root/lvhuamin/fileapple/
├── backend/
│   ├── main.py           # FastAPI 主程序 (8866端口)
│   ├── alist_client.py   # Alist API 客户端 (预留)
│   ├── converter.py      # 音视频→文字转换 (Whisper)
│   ├── database.py       # SQLite 数据库
│   └── uploader.py       # 上传处理模块
├── frontend/
│   ├── index.html        # Apple 风格界面
│   ├── style.css         # 极简深色设计
│   └── app.js            # 前端交互逻辑
├── requirements.txt     # Python 依赖
├── start.sh              # 启动脚本
├── README.md             # 项目说明
└── CLAUDE.md             # 开发规范
```

## 功能特性

- ✅ **分片上传**: 大文件分割为 5MB 分片上传
- ✅ **断点续传**: 中断后自动跳过已上传分片
- ✅ **文件夹上传**: 批量上传整个文件夹
- ✅ **实时进度**: WebSocket 推送上传/转写进度
- ✅ **音频转写**: Whisper 模型音视频转文字
- ✅ **SQLite 数据库**: 上传/转写任务持久化
- ✅ **自启动服务**: systemd 管理常驻进程

## 访问地址

| 服务 | 地址 |
|------|------|
| Web UI | http://localhost:8866 |
| API 文档 | http://localhost:8866/docs |
| WebSocket | ws://localhost:8866/ws |

## API 端点

### 文件上传
| 方法 | 端点 | 说明 |
|------|------|------|
| POST | `/api/upload/init` | 初始化上传 |
| POST | `/api/upload/chunk` | 上传分片 |
| POST | `/api/upload/merge` | 合并分片 |
| GET | `/api/upload/status/{id}` | 上传状态 |
| GET | `/api/uploads` | 列出所有上传 |
| DELETE | `/api/upload/{id}` | 删除上传 |

### 文件夹上传
| 方法 | 端点 | 说明 |
|------|------|------|
| POST | `/api/folder/init` | 初始化文件夹上传 |
| POST | `/api/folder/progress` | 更新进度 |

### 音频转写
| 方法 | 端点 | 说明 |
|------|------|------|
| POST | `/api/transcribe/init` | 初始化转写 |
| POST | `/api/transcribe/execute/{id}` | 执行转写 |
| GET | `/api/transcribe/status/{id}` | 转写状态 |
| GET | `/api/transcribes` | 列出所有转写 |

### 其他
| 方法 | 端点 | 说明 |
|------|------|------|
| GET | `/api/status` | 总状态 |

## 服务管理

```bash
# 查看状态
systemctl status fileapple

# 重启服务
systemctl restart fileapple

# 查看日志
journalctl -u fileapple -f
```

## 启动（手动）

```bash
cd /root/lvhuamin/fileapple
bash start.sh
```

## 数据目录

| 目录 | 说明 |
|------|------|
| `/root/.openclaw/workspace/learning/uploads/` | 上传文件 |
| `/root/.openclaw/workspace/learning/chunks/` | 分片缓存 |
| `/root/.openclaw/workspace/learning/transcripts/` | 转写结果 |
| `/root/.openclaw/workspace/learning/learning.db` | SQLite 数据库 |
