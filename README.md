# Github Auto Commit

<p align="center">
  <strong>7×24 小时在线挂机系统 — 自动、持续地向 GitHub 仓库生成真实感提交记录</strong>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/python-3.10+-blue" alt="Python">
  <img src="https://img.shields.io/badge/platform-Windows%20%7C%20macOS%20%7C%20Linux-lightgrey" alt="Platform">
  <img src="https://img.shields.io/badge/license-MIT-green" alt="License">
  <img src="https://img.shields.io/badge/docker-supported-2496ED?logo=docker" alt="Docker">
</p>

---

## 目录

- [1. 项目介绍](#1-项目介绍)
  - [1.1 背景](#11-背景)
  - [1.2 设计理念](#12-设计理念)
- [2. 功能说明](#2-功能说明)
  - [2.1 核心功能](#21-核心功能)
  - [2.2 运行模式](#22-运行模式)
  - [2.3 内容生成策略](#23-内容生成策略)
  - [2.4 安全保护机制](#24-安全保护机制)
- [3. 项目结构](#3-项目结构)
- [4. 代码架构说明](#4-代码架构说明)
  - [4.1 模块职责](#41-模块职责)
  - [4.2 数据流](#42-数据流)
  - [4.3 关键技术决策](#43-关键技术决策)
- [5. 安装与配置](#5-安装与配置)
  - [5.1 环境要求](#51-环境要求)
  - [5.2 代码下载](#52-代码下载)
  - [5.3 安装依赖](#53-安装依赖)
  - [5.4 GitHub Token 配置](#54-github-token-配置)
  - [5.5 配置文件修改](#55-配置文件修改)
- [6. 使用说明](#6-使用说明)
  - [6.1 命令行参数](#61-命令行参数)
  - [6.2 单次执行模式](#62-单次执行模式)
  - [6.3 守护进程模式](#63-守护进程模式)
  - [6.4 日志说明](#64-日志说明)
- [7. 多操作系统部署指南](#7-多操作系统部署指南)
  - [7.1 Linux](#71-linux)
  - [7.2 macOS](#72-macos)
  - [7.3 Windows](#73-windows)
  - [7.4 Docker（全平台通用）](#74-docker全平台通用)
  - [7.5 GitHub Actions（推荐，免服务器）](#75-github-actions推荐免服务器)
      - [7.5.1 工作原理](#751-工作原理)
      - [7.5.2 部署方式选择](#752-部署方式选择)
      - [7.5.3 方式一：全部放入目标仓库（最简单）](#753-方式一全部放入目标仓库最简单)
      - [7.5.4 方式二：独立编排仓库（更干净）](#754-方式二独立编排仓库更干净)
      - [7.5.5 验证与排错](#755-验证与排错)
      - [7.5.6 自定义触发频率](#756-自定义触发频率)
      - [7.5.7 注意事项与限制](#757-注意事项与限制)
- [8. 中国大陆网络解决方案](#8-中国大陆网络解决方案)
  - [8.1 问题说明](#81-问题说明)
  - [8.2 Linux / macOS 方案](#82-linux--macos-方案)
  - [8.3 Windows 方案](#83-windows-方案)
  - [8.4 Docker 方案](#84-docker-方案)
  - [8.5 GitHub Actions 说明](#85-github-actions-说明)
- [9. 常见问题](#9-常见问题)
- [10. 安全说明](#10-安全说明)
- [11. 项目信息](#11-项目信息)

---

## 1. 项目介绍

### 1.1 背景

**Github Auto Commit** 是一个 7×24 小时在线自动提交系统。它可以按照配置的时间窗口和频率，自动向指定的 GitHub 仓库生成提交记录，模拟出真实、活跃的开发历史。

本项目借鉴了两个 9 年前的老旧项目（[tywei90/git-auto-commit](https://github.com/tywei90/git-auto-commit) 和 [linux4cn/git-and-python](https://github.com/linux4cn/git-and-python)）的核心思路——通过脚本定时修改仓库中的某个文件，然后自动 `commit` 并 `push`。在此基础上，进行了全面的现代化重构：

| 对比维度 | 旧项目 | 本项目 |
|----------|--------|--------|
| 配置方式 | 硬编码在脚本中 | YAML 配置文件驱动，修改无需改代码 |
| 认证方式 | Token 明文写入脚本 | `.env` 环境变量隔离，永不提交到仓库 |
| 提交内容 | 固定文本 / 时间戳 | 多策略随机化：24 种日志短语 + 4 种 Markdown 模板 + 20 种 Emoji |
| 提交时间 | 固定频率 | 每日次数随机、间隔随机、±15% 抖动 |
| 部署方式 | 仅本地 crontab | 守护进程 / cron / systemd / 任务计划程序 / Docker / GitHub Actions |
| 安全性 | 无校验 | 路径穿越防护、敏感文件黑名单、远程仓库校验、锁文件清理 |
| 容错性 | 失败即退出 | 指数退避重试、Push 冲突自动 rebase、连续失败熔断 |

### 1.2 设计理念

- **安全第一**：Token 不经手配置文件、不进入命令行日志、不进 Docker 镜像层、不进版本控制。
- **高度可配**：所有行为参数均可通过 `config.yaml` 调整，无需阅读或修改任何代码。
- **模拟真实**：提交时间、消息、文件内容均引入多层随机化，避免产生"机器人感"的规律模式。
- **跨平台**：同一套代码，在 Windows、macOS、Linux 上均可运行。
- **生产可用**：内置重试、熔断、信号处理、健康检查，可长期无人值守运行。

---

## 2. 功能说明

### 2.1 核心功能

| 功能 | 说明 |
|------|------|
| **自动提交** | 按配置的时间窗口和频率，自动修改文件并 `git commit` + `git push` |
| **随机化策略** | 每日提交次数随机、间隔时间随机（±15% 抖动）、提交消息随机选取 |
| **多文件支持** | 可配置多个目标文件，每次随机选取一个修改 |
| **智能内容生成** | 按文件类型自动选择策略：`.log` 追加时间戳日志行、`.md` 更新页脚、其他文件追加 Emoji 短语 |
| **活动时间窗口** | 可设置在每天的 8:00–23:00（或任意区间）内活动，其他时间自动休眠 |
| **周末跳过** | 可选周六日不生成提交 |
| **守护进程模式** | 长期运行，每日自动计算当天目标次数，次日零点自动重置 |
| **单次模式** | 执行一次提交后退出，适配 cron / systemd timer / 任务计划程序 / GitHub Actions |
| **重试与熔断** | 网络异常自动重试（3 次指数退避），连续 5 次失败自动熔断当天循环 |
| **Push 冲突处理** | Push 被拒绝时自动执行 `git pull --rebase` 后重试 |
| **陈旧锁清理** | git 非正常退出后残留的 `.git/index.lock` 等锁文件自动清理（>5 分钟） |
| **跨平台信号处理** | Windows 下自动跳过 SIGTERM 注册（该信号在 Windows 上不存在） |

### 2.2 运行模式

#### 守护进程模式（`--daemon`，默认）

```
启动 → 等待活动窗口 → 计算当天目标次数 → 随机间隔 → 修改文件 → 提交推送
                                                                    ↓
                                                              达到目标次数？
                                                              ↓ 是
                                                         休眠至次日窗口
```

- 适合长期运行（服务器、NAS、树莓派、Docker 容器）
- 每天自动随机 0~N 次提交（N 由 `max_daily` 控制）
- `Ctrl+C` 或 `SIGTERM` 优雅退出

#### 单次模式（`--once`）

```
启动 → 克隆/拉取仓库 → 修改文件 → 提交推送 → 退出
```

- 适合定时触发（crontab、systemd timer、Windows 任务计划程序、GitHub Actions）
- 每次执行只产生一个提交

### 2.3 内容生成策略

| 文件类型 | 策略 | 示例 |
|----------|------|------|
| `activity.log` / `*.log` | 追加时间戳 + 随机日志行 | `[2026-06-24 14:32:07 UTC] cache refresh completed` |
| `README.md` / `*.md` | 替换或追加页脚行 | `> ⚡ Auto-synced at 2026-06-24 14:32:07 UTC` |
| `*.txt` | 追加时间戳 + 随机日志行 | 同上 `.log` |
| 其他扩展名 | 追加随机 Emoji + 短语 | `🚀 job queue drained — 0 pending tasks` |

内容池包含 **24 种**日志短语、**4 种** Markdown 页脚模板、**20 种** Emoji 组合。Markdown 页脚的检测使用**逐行前缀精确匹配**，不会误匹配代码块内的文字。

### 2.4 安全保护机制

| 层级 | 防护措施 |
|------|----------|
| **Token 安全** | 仅存 `.env`（已加入 `.gitignore` 和 `.dockerignore`）；运行时注入 HTTPS URL；日志中自动脱敏为 `<token>` |
| **路径穿越** | 拒绝 `..`、`/` 开头的绝对路径、空文件名 |
| **敏感文件** | 拒绝修改 `.gitignore`、`.env`、`Dockerfile`、`config.yaml` 等 10 种保留文件名 |
| **仓库校验** | 若 `working_dir` 已存在但 remote URL 不匹配 → **直接退出**，绝不碰其他项目 |
| **Shell 注入** | 全程使用 `subprocess.run(list, shell=False)`，commit message 经 list 参数传递 |
| **最小权限** | Token 仅需 `Contents: Read & Write`（fine-grained）或 `public_repo`（classic） |

---

## 3. 项目结构

```
git-auto-commit/
├── src/                                # 应用源代码
│   ├── __init__.py                     # 包元数据（版本号）
│   ├── main.py                         # CLI 入口 + 守护进程主循环
│   ├── config.py                       # 配置加载器、校验器、Token 管理
│   ├── content_gen.py                  # 文件内容生成策略（日志/Markdown/Emoji）
│   └── git_ops.py                      # Git 操作封装（克隆/提交/推送/重试/安全校验）
│
├── .github/workflows/
│   └── schedule.yml                    # GitHub Actions 定时工作流
│
├── config.yaml                         # 用户配置文件（YAML）
├── .env.example                        # 环境变量模板（复制为 .env 后填入 Token）
├── .gitignore                          # Git 忽略规则
├── .dockerignore                       # Docker 构建忽略规则
├── requirements.txt                    # Python 依赖（pyyaml + python-dotenv）
├── Dockerfile                          # Docker 镜像定义（多阶段构建 + 非 root 用户）
├── docker-compose.yml                  # Docker Compose 一键部署
├── DEVELOPMENT_MANUAL.md               # 开发手册（架构详解、Mermaid 流程图、部署指南）
└── README.md                           # 本文件
```

---

## 4. 代码架构说明

### 4.1 模块职责

```
src/
├── main.py          调度层    —— CLI、信号处理、守护进程循环、每日提交编排
├── config.py        配置层    —— YAML 解析、.env 加载、参数校验、Token 管理
├── content_gen.py   内容层    —— 按文件类型生成随机化修改内容
└── git_ops.py       操作层    —— Git 命令封装、重试、远程仓库安全校验、锁清理
```

### 4.2 数据流

```
config.yaml ──▶ config.load_config() ──▶ AppConfig (dataclass)
                                            │
.env ──▶ config.get_token() ──▶ token ──────┤
                                            │
                                            ▼
                              main.run_once() / main.run_daemon()
                                            │
                    ┌───────────────────────┼───────────────────────┐
                    ▼                       ▼                       ▼
            clone_or_pull()         generate_content()      commit_and_push()
            (git_ops.py)            (content_gen.py)        (git_ops.py)
                    │                       │                       │
                    ▼                       ▼                       ▼
              GitHub API            本地文件 I/O              git push origin
```

### 4.3 关键技术决策

| 决策 | 选择 | 原因 |
|------|------|------|
| 语言 | Python 3.10+ | 跨平台、文本处理强、GitHub Actions 预装 |
| Git 操作 | `subprocess` + git CLI | 最可靠，无需额外依赖（如 GitPython） |
| 配置格式 | YAML | 支持注释、层次结构清晰、广泛使用 |
| 无 `shell=True` | 全程 `subprocess.run(list)` | 杜绝命令注入 |
| 日志 | 根 Logger + 自定义格式 | 所有模块日志统一输出，不丢失子模块日志 |
| 守护进程 | 纯 Python 循环 + `time.sleep` | 无第三方调度库依赖，跨平台最简单 |

---

## 5. 安装与配置

### 5.1 环境要求

| 组件 | 最低版本 | 说明 |
|------|----------|------|
| Python | 3.10+ | 建议 3.11+ |
| Git | 2.30+ | 任意较新版本即可 |
| pip | 随 Python 安装 | 用于安装依赖 |
| 操作系统 | Windows / macOS / Linux | 均完整支持 |

### 5.2 代码下载

```bash
# 方式一：Git 克隆
git clone https://github.com/你的用户名/git-auto-commit.git
cd git-auto-commit

# 方式二：直接下载 ZIP
# 在 GitHub 仓库页面点击 "Code" → "Download ZIP"，解压后进入目录
```

### 5.3 安装依赖

```bash
# Linux / macOS
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Windows (PowerShell)
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

依赖项仅两个（均为纯 Python，无编译步骤）：

| 包 | 用途 |
|----|------|
| `pyyaml` | 解析 `config.yaml` 配置文件 |
| `python-dotenv` | 从 `.env` 文件加载环境变量 |

### 5.4 GitHub Token 配置

#### Step 1：生成 Token

1. 登录 GitHub → **Settings** → **Developer settings** → **Personal access tokens**
2. 选择 **Fine-grained tokens**（推荐）或 **Tokens (classic)**
3. 权限设置：

   | Token 类型 | 所需权限 |
   |------------|----------|
   | Fine-grained | Repository access: **Only select repositories** → 选择目标仓库；Permissions: **Contents** → Read **and** Write |
   | Classic | Scope: `public_repo`（公开仓库）或 `repo`（私有仓库） |

4. 生成后**立即复制** Token（只显示一次）。

#### Step 2：配置 .env 文件

```bash
# 复制模板
cp .env.example .env

# 编辑 .env，将 Token 粘贴进去
# Linux / macOS
nano .env

# Windows (Notepad)
notepad .env
```

`.env` 文件内容：

```ini
GIT_AUTO_COMMIT_TOKEN=ghp_xxxxxxxxxxxxxxxxxxxx
```

> ⚠️ `.env` 已加入 `.gitignore` 和 `.dockerignore`，**不会被提交到仓库或打包进 Docker 镜像**。切勿将 Token 写入 `config.yaml`。

### 5.5 配置文件修改

编辑 `config.yaml`，至少需要修改 `git.repo_url`：

```yaml
git:
  repo_url: "https://github.com/你的用户名/目标仓库.git"  # ← 必改
  branch: "main"                                          # ← 按实际情况修改

commit:
  min_daily: 1          # 每天最少 1 次提交
  max_daily: 5          # 每天最多 5 次提交（实际次数在 1~5 之间随机）
  min_interval_minutes: 60    # 提交间隔最少 60 分钟
  max_interval_minutes: 240   # 提交间隔最多 240 分钟（4 小时）
  messages:              # 自定义提交消息列表（可选，不配置则使用内置默认值）
    - "📝 update activity log"
    - "🔧 daily maintenance"
  files:                 # 目标文件列表（至少一个，文件需在目标仓库中存在）
    - "activity.log"
    - "README.md"

active_hours: [9, 22]   # 仅在 9:00 ~ 21:59 之间提交
skip_weekends: true      # 周六日不提交
```

详细配置项说明请参考 [`DEVELOPMENT_MANUAL.md` §6](./DEVELOPMENT_MANUAL.md#6-configuration-file-reference) 或 `config.yaml` 文件中的注释。

---

## 6. 使用说明

### 6.1 命令行参数

```bash
python -m src.main --help
```

```
usage: main.py [-h] [--once] [--daemon] [--config CONFIG]

options:
  -h, --help       显示帮助信息
  --once           单次提交模式：执行一次提交后退出（用于 cron / GitHub Actions）
  --daemon         守护进程模式：长期运行（默认模式）
  --config CONFIG  配置文件路径（默认：config.yaml）
```

### 6.2 单次执行模式

```bash
# 确保 .env 和 config.yaml 已正确配置后：
python -m src.main --once
```

预期输出：

```
2026-06-24 14:32:00  INFO     🎯 One-shot mode
2026-06-24 14:32:01  INFO     📥 Cloning repository …
2026-06-24 14:32:05  INFO     ✅ Repository cloned to /path/to/repo
2026-06-24 14:32:05  INFO     ✏️  Modified: activity.log
2026-06-24 14:32:07  INFO     🚀 Pushed: 📝 update activity log
2026-06-24 14:32:07  INFO     ✅ Commit cycle complete
```

### 6.3 守护进程模式

```bash
# 前台运行（直接看日志）
python -m src.main --daemon

# 或直接（无参数默认即为守护进程模式）
python -m src.main
```

预期输出：

```
2026-06-24 14:32:00  INFO     🚀 Daemon started — press Ctrl+C to stop
2026-06-24 14:32:01  INFO     📋 Today's commit target: 3
2026-06-24 14:32:05  INFO     ✏️  Modified: README.md
2026-06-24 14:32:07  INFO     🚀 Pushed: 🔧 minor tweaks and improvements
2026-06-24 15:45:12  INFO     ✏️  Modified: activity.log
2026-06-24 15:45:14  INFO     🚀 Pushed: 📊 refresh analytics data
2026-06-24 18:12:33  INFO     ✏️  Modified: README.md
2026-06-24 18:12:35  INFO     🚀 Pushed: ✅ complete daily checkpoint
2026-06-24 18:12:35  INFO     🏁 Daily run complete — 3 commits made
2026-06-24 18:12:35  INFO     💤 Sleeping 13:47:25 until next active window
```

停止守护进程：按 `Ctrl+C`，程序会在完成当前提交后优雅退出。

### 6.4 日志说明

日志格式：`时间  级别  消息`

| 级别 | 含义 | 示例 |
|------|------|------|
| `INFO` | 正常操作流程 | 提交成功、进入休眠 |
| `WARNING` | 可恢复的异常 | 网络超时重试、锁文件清理 |
| `ERROR` | 需关注的错误 | Push 失败、文件不可写 |
| `DEBUG` | 调试详情（需设置 `log_level: DEBUG`） | Git 命令执行、文件变更内容 |

---

## 7. 多操作系统部署指南

### 7.1 Linux

#### 方案 A：systemd 守护进程（推荐）

创建 systemd 服务文件：

```bash
sudo nano /etc/systemd/system/git-auto-commit.service
```

```ini
[Unit]
Description=Git Auto Commit Daemon
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=你的用户名
WorkingDirectory=/home/你的用户名/git-auto-commit
EnvironmentFile=/home/你的用户名/git-auto-commit/.env
ExecStart=/home/你的用户名/git-auto-commit/.venv/bin/python -m src.main --daemon
Restart=on-failure
RestartSec=30
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
```

启动并设置开机自启：

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now git-auto-commit.service

# 查看状态
sudo systemctl status git-auto-commit

# 查看日志
sudo journalctl -u git-auto-commit -f
```

#### 方案 B：crontab 定时触发

```bash
crontab -e
```

```cron
# 每天 9:00 到 21:00 之间，每 30~90 分钟随机触发一次
# 使用 --once 模式，每次执行产生一个提交
*/30 9-21 * * 1-5 cd /path/to/git-auto-commit && .venv/bin/python -m src.main --once >> /var/log/git-auto-commit.log 2>&1
```

> **注意：** crontab 方式每次触发都是独立的 `--once` 调用，提交次数的随机化仅在守护进程模式（`--daemon`）中生效。若希望每日提交次数随机，建议使用 systemd 方案。

### 7.2 macOS

#### 方案 A：launchd 守护进程（推荐）

创建 launchd plist 文件：

```bash
nano ~/Library/LaunchAgents/com.git-auto-commit.plist
```

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
  "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.git-auto-commit</string>
    <key>ProgramArguments</key>
    <array>
        <string>/Users/你的用户名/git-auto-commit/.venv/bin/python</string>
        <string>-m</string>
        <string>src.main</string>
        <string>--daemon</string>
    </array>
    <key>WorkingDirectory</key>
    <string>/Users/你的用户名/git-auto-commit</string>
    <key>EnvironmentVariables</key>
    <dict>
        <key>GIT_AUTO_COMMIT_TOKEN</key>
        <string>ghp_你的Token</string>
    </dict>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <true/>
    <key>StandardOutPath</key>
    <string>/Users/你的用户名/Library/Logs/git-auto-commit.log</string>
    <key>StandardErrorPath</key>
    <string>/Users/你的用户名/Library/Logs/git-auto-commit.err</string>
</dict>
</plist>
```

加载并启动：

```bash
launchctl load ~/Library/LaunchAgents/com.git-auto-commit.plist

# 查看状态
launchctl list | grep git-auto-commit

# 停止
launchctl unload ~/Library/LaunchAgents/com.git-auto-commit.plist
```

#### 方案 B：crontab

与 Linux 完全相同，参见 [7.1 方案 B](#方案-bcrontab-定时触发)。

### 7.3 Windows

#### 方案 A：任务计划程序 + 守护进程（推荐）

**Step 1：创建启动脚本**

新建 `start_daemon.bat`（放在项目目录下）：

```batch
@echo off
cd /d C:\path\to\git-auto-commit
call .venv\Scripts\activate
python -m src.main --daemon >> logs\daemon.log 2>&1
```

**Step 2：创建计划任务**

打开 **任务计划程序** → **创建任务**：

| 选项卡 | 设置 |
|--------|------|
| **常规** | 名称：`Git Auto Commit`；勾选「不管用户是否登录都要运行」 |
| **触发器** | 新建 → 「在系统启动时」 |
| **操作** | 新建 → 操作：「启动程序」；程序：`C:\path\to\git-auto-commit\start_daemon.bat` |
| **条件** | 取消勾选「只有在计算机使用交流电源时才启动」 |
| **设置** | 勾选「如果任务失败，每隔 1 分钟重新启动一次」 |

#### 方案 B：PowerShell 循环脚本

新建 `loop_once.ps1`：

```powershell
$ScriptDir = "C:\path\to\git-auto-commit"
Set-Location $ScriptDir

while ($true) {
    & .venv\Scripts\python.exe -m src.main --once
    # 等待 30~90 分钟（随机）
    $WaitMinutes = Get-Random -Minimum 30 -Maximum 90
    Start-Sleep -Seconds ($WaitMinutes * 60)
}
```

在任务计划程序中设置此脚本在系统启动时执行（程序：`powershell.exe`，参数：`-ExecutionPolicy Bypass -File C:\path\to\git-auto-commit\loop_once.ps1`）。

### 7.4 Docker（全平台通用）

```bash
# 1. 准备 .env 和 config.yaml
cp .env.example .env
# 编辑 .env 和 config.yaml

# 2. 构建并启动
docker compose up -d

# 3. 查看日志
docker compose logs -f

# 4. 停止
docker compose down
```

**特性：**
- 非 root 用户运行（`app` 用户）
- 容器健康检查（每 5 分钟检测进程存活）
- Volume 持久化克隆的仓库（重启不丢失）
- `restart: unless-stopped` 自动故障恢复

### 7.5 GitHub Actions（推荐，免服务器）

**适用场景：** 不想维护任何服务器、NAS、树莓派，利用 GitHub 提供的免费 CI 分钟数，零成本实现 7×24 挂机。

**每月免费额度（截至 2026）：**

| 账户类型 | 免费分钟数 / 月 | 是否够用 |
|----------|-----------------|----------|
| 个人免费账户 | 2,000 分钟 | ✅ 绰绰有余（每次运行 < 1 分钟） |
| GitHub Pro | 3,000 分钟 | ✅ |
| 组织 / 企业 | 视套餐而定 | ✅ |

> 本工具每次 `--once` 执行通常在 10~30 秒内完成。即便每天触发 48 次（每 30 分钟），一个月也只需不到 750 分钟，远低于免费额度。

---

#### 7.5.1 工作原理

与其他部署方式不同，GitHub Actions 使用的是 **`--once` 单次模式**：

```
GitHub 定时器（cron）触发
       │
       ▼
  Actions Runner 启动
       │
       ├─ 安装 Python + 依赖
       ├─ 读取 config.yaml + ${{ secrets.TOKEN }}
       ├─ python -m src.main --once    ← 单次提交
       └─ Runner 销毁
       │
       ▼
  等待下一次 cron 触发（如 30 分钟后）
```

关键点：
- 每次触发是**独立的干净环境**（无状态），Runner 启动 → 执行 → 销毁
- 每次运行都会重新 `git clone` 目标仓库（或 pull 已有的）
- 提交的随机化由脚本内部决策（随机选择文件、随机选择消息），并非每次触发都一定产生提交

---

#### 7.5.2 部署方式选择

有两种方式将项目放入 GitHub，根据你的需求选择：

| 方式 | 说明 | 适合场景 |
|------|------|----------|
| **方式一：全部放入目标仓库** | 项目文件直接放在你要刷提交记录的仓库中 | 新手、个人项目、仓库简单 |
| **方式二：独立编排仓库** | 项目文件放在一个单独的"编排仓库"中，通过 `config.yaml` 指向目标仓库 | 目标仓库需要保持干净、多个目标仓库共用一套代码 |

> 💡 **推荐新手使用方式一**，步骤最简单，出问题最容易排查。

---

#### 7.5.3 方式一：全部放入目标仓库（最简单）

**你将得到的效果：** 目标仓库的 GitHub Actions 定时运行，自动向**该仓库本身**生成提交。

##### Step 1：将项目文件放入目标仓库

假设你的目标仓库是 `https://github.com/你的用户名/my-project`（即你希望这个仓库有持续的提交记录）。

你需要将该仓库克隆到本地，然后把本项目（git-auto-commit）的文件放进去：

```bash
# 克隆目标仓库
git clone https://github.com/你的用户名/my-project.git
cd my-project

# 将本项目的文件复制进来（注意不要覆盖已有的 README.md 等）
# 假设 git-auto-commit 项目在 ~/Desktop/git-auto-commit
cp ~/Desktop/git-auto-commit/src ./src -r
cp ~/Desktop/git-auto-commit/requirements.txt .
cp ~/Desktop/git-auto-commit/config.yaml .
cp ~/Desktop/git-auto-commit/.github/workflows/schedule.yml .github/workflows/ -r
```

最终目标仓库的目录结构应类似：

```
my-project/                         ← 你的目标仓库
├── src/                            ← 从本项目复制
│   ├── __init__.py
│   ├── main.py
│   ├── config.py
│   ├── content_gen.py
│   └── git_ops.py
├── .github/workflows/
│   └── schedule.yml                ← 从本项目复制
├── requirements.txt                ← 从本项目复制
├── config.yaml                     ← 从本项目复制（需要修改！）
├── activity.log                    ← 这个文件会被自动修改
├── README.md                       ← 你原来的 README
└── ... (你项目的其他文件)
```

##### Step 2：修改 config.yaml

```yaml
git:
  # 目标仓库就是当前仓库本身
  repo_url: "https://github.com/你的用户名/my-project.git"
  branch: "main"

commit:
  min_daily: 1
  max_daily: 5
  min_interval_minutes: 30
  max_interval_minutes: 180
  files:
    - "activity.log"      # 确保这个文件存在（可以是空文件）
    - "README.md"         # 如果有 README

active_hours: [8, 23]
skip_weekends: true
```

> ⚠️ **重要：** `files` 列表中列出的文件必须在仓库中**真实存在**。至少创建一个空文件：
> ```bash
> touch activity.log
> git add activity.log && git commit -m "Add activity log" && git push
> ```

##### Step 3：创建 activity.log（如果还没有）

```bash
# 在目标仓库根目录创建一个空文件
echo "" > activity.log
```

##### Step 4：配置 Secret

在 GitHub 网页上操作：

1. 打开目标仓库页面（`https://github.com/你的用户名/my-project`）
2. 点击顶部导航栏的 **Settings**（不是个人设置，是仓库设置）
3. 在左侧菜单找到 **Secrets and variables** → 点击 **Actions**
4. 点击绿色按钮 **New repository secret**
5. 在弹窗中填入：
   - **Name**：`GIT_AUTO_COMMIT_TOKEN`（必须与 schedule.yml 中的变量名一致）
   - **Secret**：你的 GitHub Personal Access Token（参见 [§5.4](#54-github-token-配置) 获取）
6. 点击 **Add secret**

> ⚠️ **Token 权限要求：** 即便是向同一个仓库提交，GitHub Actions 的默认 `GITHUB_TOKEN` 也不能触发新的 Actions 运行（防止递归）。因此必须使用 **Personal Access Token**，不能使用 Actions 自带的 `secrets.GITHUB_TOKEN`。

##### Step 5：提交并推送

```bash
# 确保在目标仓库目录中
git add .
git commit -m "Add git-auto-commit workflow"
git push origin main
```

##### Step 6：验证工作流是否生效

1. 打开 GitHub 仓库页面，点击顶部 **Actions** 标签
2. 左侧列表应出现 **"Git Auto Commit"** 工作流
3. 点击它，然后点击右侧 **"Run workflow"** 按钮 → 选择 Branch → 点击绿色的 **"Run workflow"**（手动触发一次）
4. 等待约 30 秒，刷新页面，应看到一个新的 workflow run
5. 点击进入查看详情 → 点击 **"Run auto-commit (one-shot)"** 步骤 → 展开查看日志

成功的日志应包含类似内容：

```
🎯 One-shot mode
📥 Cloning repository …
✅ Repository cloned to /home/runner/work/my-project/my-project/repo
✏️  Modified: activity.log
🚀 Pushed: 📝 update activity log
✅ Commit cycle complete
```

至此，GitHub Actions 部署完成！工作流将按照 `schedule.yml` 中的 cron 表达式自动定时运行。

---

#### 7.5.4 方式二：独立编排仓库（更干净）

**你将得到的效果：** 创建一个专门的"编排仓库"存放本项目代码，它定时向**另一个**目标仓库提交。

**适用场景：**
- 目标仓库是你精心维护的项目，不想混入自动化脚本
- 一个编排仓库管理多个目标仓库（通过多个 `config-xxx.yaml`）

##### Step 1：创建编排仓库

1. 在 GitHub 上新建一个**私有仓库**（建议命名为 `git-auto-commit-runner`）
2. Clone 到本地，将本项目所有文件放入其中
3. 编辑 `config.yaml` 指向你的目标仓库：

```yaml
git:
  # ⚠️ 指向另一个仓库（目标仓库）
  repo_url: "https://github.com/你的用户名/target-project.git"
  branch: "main"
  # ... 其余配置
```

##### Step 2：在编排仓库配置 Secret

与方式一的 Step 4 完全相同 —— 在**编排仓库**（`git-auto-commit-runner`）的 Settings → Secrets → Actions 中添加 `GIT_AUTO_COMMIT_TOKEN`。

> Token 需要有**目标仓库**的 `Contents: Read & Write` 权限。如果是同一个 GitHub 账号下的仓库，一份 Fine-grained Token 可以授权多个仓库。

##### Step 3：确保目标仓库有目标文件

在**目标仓库**中，确保 `config.yaml` 中 `commit.files` 列出的文件存在（如 `activity.log`）：

```bash
# 在目标仓库中
git clone https://github.com/你的用户名/target-project.git
cd target-project
echo "" > activity.log
git add activity.log && git commit -m "Add activity log" && git push
```

##### Step 4：提交编排仓库并手动触发验证

```bash
cd git-auto-commit-runner
git add . && git commit -m "Setup git-auto-commit runner" && git push
```

然后在 GitHub Actions 页面手动触发一次（**Run workflow**），验证日志输出中 `Pushed` 的目标是 `target-project`。

---

#### 7.5.5 验证与排错

##### 检查工作流运行状态

1. 进入仓库 → **Actions** 标签
2. 查看最近的 workflow run 状态：
   - ✅ 绿色勾：运行成功
   - 🔴 红色叉：运行失败，点击查看日志
   - 🟡 黄色圆：正在运行中
   - ⚪ 灰色：队列中等待

##### 常见失败原因及解决

| 日志中的错误 | 原因 | 解决 |
|-------------|------|------|
| `Environment variable 'GIT_AUTO_COMMIT_TOKEN' is not set` | Secret 未配置或名称不一致 | 检查 Settings → Secrets → Actions 中 Name 是否为 `GIT_AUTO_COMMIT_TOKEN`（区分大小写） |
| `403 Forbidden` 或 `Authentication failed` | Token 权限不足或过期 | 重新生成 Token，确认有 `Contents: Read & Write` 权限 |
| `fatal: couldn't find remote ref` | `config.yaml` 中的 `branch` 不正确 | 检查目标仓库的分支名（GitHub 新建仓库默认是 `main`，旧仓库可能是 `master`） |
| `config.yaml not found` | 项目文件未正确放置 | 确认 `src/`、`config.yaml`、`requirements.txt` 都在仓库根目录 |
| `ModuleNotFoundError: No module named 'src'` | 未安装依赖或 Python 路径问题 | 确认 workflow 中有 `pip install -r requirements.txt` 步骤 |
| 工作流完全没有触发 | cron 未到时间或 workflow 文件路径错误 | 确认文件在 `.github/workflows/` 下，且扩展名为 `.yml`（不是 `.yaml`）。手动点 "Run workflow" 测试 |

##### 查看 Git Auto Commit 产生的提交

在目标仓库页面点击提交历史（时钟图标），可以看到由 `auto-commit-bot` 生成的提交记录。

---

#### 7.5.6 自定义触发频率

编辑 `.github/workflows/schedule.yml` 中的 `cron` 字段：

```yaml
on:
  schedule:
    # ┌──────────── 分钟 (0–59)
    # │ ┌─────────── 小时 (0–23) ← UTC 时间！
    # │ │ ┌────────── 日 (1–31)
    # │ │ │ ┌───────── 月 (1–12)
    # │ │ │ │ ┌──────── 星期 (0–6, 0=周日)
    # │ │ │ │ │
    - cron: "7,37 * * * *"    # 每小时的 07 分和 37 分各触发一次
```

**常用 cron 示例（注意均为 UTC 时间）：**

| cron 表达式 | 触发频率 | 适用场景 |
|-------------|----------|----------|
| `"7,37 * * * *"` | 每小时 2 次（07分 + 37分） | 均衡，默认推荐 |
| `"7 * * * *"` | 每小时 1 次 | 低频率，节省 CI 分钟 |
| `"*/15 * * * *"` | 每 15 分钟 | 高频率（注意仍受 `min_interval_minutes` 约束） |
| `"7 1-14 * * *"` | UTC 01:00~14:59 每小时 | 配合北京时间 `active_hours: [9, 23]`（UTC+8 = 北京时间 9:00~22:59） |
| `"7 * * * 1-5"` | 工作日每小时 | 工作日高频，周末休息 |

> ⚠️ **UTC 时间与北京时间的换算：** 北京时间 = UTC + 8。例如 `active_hours: [9, 23]` 表示北京时间 9:00~22:59，对应的 UTC 时间是 1:00~14:59。建议 cron 覆盖整个 `active_hours` 范围，由脚本内部判断是否在窗口内。

#### 7.5.7 注意事项与限制

| 注意点 | 说明 |
|--------|------|
| **不能使用 `secrets.GITHUB_TOKEN`** | GitHub 自带的 Token 提交不会触发新的 Actions，必须使用 PAT |
| **Token 安全** | Secret 是加密存储的，Actions 日志中 Token 会自动隐藏为 `***` |
| **调度延迟** | GitHub 可能在高峰期延迟触发（15~30 分钟），实测大多数情况准时 |
| **仓库休眠** | 免费账户的私有仓库若 60 天无活动，Actions 可能暂停。本工具本身会产生活动，所以不会休眠 |
| **不要滥用** | 过多的提交（如每分钟一次）会导致 Actions 分钟数快速耗尽，且对仓库没有实际价值。建议维持自然频率（每天 0~8 次） |
| **并发限制** | 免费账户同时只能运行 1 个 job。如果同一仓库有多个 workflow，它们会排队 |
| **workflow_dispatch 随时可用** | 除了定时触发，你可以随时在 Actions 页面手动点 "Run workflow" |

---

## 8. 中国大陆网络解决方案

### 8.1 问题说明

GitHub 在中国大陆的访问存在以下典型问题：

| 问题 | 表现 |
|------|------|
| DNS 污染 | `github.com` 解析到错误 IP |
| HTTPS 阻断 | `git clone` / `git push` 超时或连接重置（RST） |
| 速度缓慢 | 未阻断但带宽极低（几十 KB/s） |

以下方案按推荐程度排序。

### 8.2 Linux / macOS 方案

#### 方案 A：配置 Git 全局代理（最推荐）

前提：已有可用的 HTTP/HTTPS 或 SOCKS5 代理。

```bash
# HTTP/HTTPS 代理（Clash、V2Ray 等）
git config --global http.proxy http://127.0.0.1:7890
git config --global https.proxy http://127.0.0.1:7890

# SOCKS5 代理
git config --global http.proxy socks5://127.0.0.1:1080
git config --global https.proxy socks5://127.0.0.1:1080

# 取消代理
git config --global --unset http.proxy
git config --global --unset https.proxy
```

#### 方案 B：使用 ghproxy 加速

对于 `git clone` 操作，使用 [ghproxy.com](https://ghproxy.com) 镜像加速：

修改 `config.yaml` 中的 `repo_url`：

```yaml
git:
  # 原地址：https://github.com/user/repo.git
  # 加速地址：
  repo_url: "https://ghproxy.com/https://github.com/user/repo.git"
```

> **注意：** ghproxy 仅加速下载（clone/fetch），`git push` 仍需直接访问 GitHub。建议配合代理使用。

#### 方案 C：修改 hosts 文件

```bash
sudo nano /etc/hosts
```

添加以下内容（IP 地址可从 [github.com.ipaddress.com](https://github.com.ipaddress.com) 获取最新值）：

```
140.82.112.3    github.com
140.82.113.5    api.github.com
185.199.108.133 raw.githubusercontent.com
```

> ⚠️ GitHub IP 地址会变动，此方案需要定期更新。

#### 方案 D：镜像站点

使用 Gitee 等国内 Git 托管平台作为中转：

```bash
# 1. 在 Gitee 上创建仓库，设置为从 GitHub 仓库同步
# 2. 将 config.yaml 的 repo_url 指向 Gitee 仓库
# 3. Gitee 仓库会自动同步到 GitHub
```

### 8.3 Windows 方案

#### 方案 A：Git 全局代理

```powershell
# PowerShell / CMD
git config --global http.proxy http://127.0.0.1:7890
git config --global https.proxy http://127.0.0.1:7890
```

如果使用 Clash for Windows：

1. 确保 Clash 已开启「系统代理」或「TUN 模式」
2. Git 代理通常会自动生效
3. 若不生效，手动设置上述 Git 代理命令

#### 方案 B：TUN 模式（最省心）

使用 Clash Verge / Clash for Windows / sing-box 等工具开启 **TUN 模式**（虚拟网卡），所有流量（包括 Git）自动走代理，无需逐一配置。

#### 方案 C：Watt Toolkit（ Steam++ ）

[Watt Toolkit](https://steampp.net/) 提供 GitHub 加速功能，一键开启即可。

### 8.4 Docker 方案

在 Docker 容器中使用代理：

```yaml
# docker-compose.yml
services:
  git-auto-commit:
    build: .
    env_file:
      - .env
    environment:
      - TZ=Asia/Shanghai
      - http_proxy=http://host.docker.internal:7890   # 宿主机代理地址
      - https_proxy=http://host.docker.internal:7890
      - no_proxy=localhost,127.0.0.1
    volumes:
      - ./config.yaml:/app/config.yaml:ro
      - repo-data:/app/repo
    restart: unless-stopped
```

> `host.docker.internal` 在 Docker Desktop（Windows/macOS）上自动可用；Linux 需添加 `--add-host=host.docker.internal:host-gateway`。

### 8.5 GitHub Actions 说明

GitHub Actions 的 Runner 运行在 GitHub 的服务器上（境外），**天然不受中国网络限制**。这是中国大陆用户最省心的方案——使用 [7.5 节](#75-github-actions推荐免服务器) 的 GitHub Actions 部署，完全无需考虑网络问题。

---

## 9. 常见问题

<details>
<summary><strong>Q: 提示 "❌ Environment variable 'GIT_AUTO_COMMIT_TOKEN' is not set."</strong></summary>

**A:** 未创建或未正确配置 `.env` 文件。

```bash
cp .env.example .env
# 编辑 .env，将 Token 粘贴进去
```
</details>

<details>
<summary><strong>Q: Push 失败 "403 Forbidden" 或 "Authentication failed"</strong></summary>

**A:** Token 问题：
1. Token 已过期 → 生成新 Token
2. Token 权限不足 → Classic 需要 `repo` 或 `public_repo`；Fine-grained 需要 `Contents: Read & Write`
3. 目标仓库属于组织 → 组织可能禁用了 PAT 访问
</details>

<details>
<summary><strong>Q: 提示 "❌ SAFETY CHECK FAILED" 然后退出</strong></summary>

**A:** `working_dir` 目录已存在，但其中的 Git 远程地址与 `config.yaml` 配置不匹配。解决方法：
1. 删除该目录：`rm -rf ./repo`（或 Windows：`rmdir /s repo`）
2. 或将 `config.yaml` 中的 `working_dir` 改为其他路径
</details>

<details>
<summary><strong>Q: 生成的提交看起来太规律、像机器人</strong></summary>

**A:** 调整配置增强随机性：
- 扩大 `max_daily` 范围（如 `[1, 8]`）
- 扩大量间隔范围（如 `[30, 240]`）
- 添加更多自定义 `messages`
- 开启 `skip_weekends: true`
- 缩小 `active_hours` 范围（如 `[9, 18]`）
</details>

<details>
<summary><strong>Q: 守护进程在 Docker 中时区不对（UTC 而非北京时间）</strong></summary>

**A:** 在 `docker-compose.yml` 中设置时区：

```yaml
environment:
  - TZ=Asia/Shanghai
```

或在 `docker run` 时添加 `-e TZ=Asia/Shanghai`。
</details>

<details>
<summary><strong>Q: 如何同时向多个仓库提交？</strong></summary>

**A:** 运行多个实例，使用不同的配置文件：

```bash
python -m src.main --config config-repo-a.yaml &
python -m src.main --config config-repo-b.yaml &
```
</details>

<details>
<summary><strong>Q: GitHub 会封号吗？</strong></summary>

**A:** 本工具设计为**个人、适度使用**（每天 0~8 次提交）。此频率与正常开发者无异，不会被 GitHub 标记。如果配置为每天数百次提交，则可能违反 GitHub 的可接受使用政策。
</details>

---

## 10. 安全说明

| 关注点 | 状态 |
|--------|------|
| Token 存储 | ✅ `.env` 文件，已在 `.gitignore` 和 `.dockerignore` 中排除 |
| Token 日志泄露 | ✅ 日志中自动脱敏显示为 `<token>` |
| Token 命令行泄露 | ⚠️ 传递至 `git clone` 时在进程列表中可见（单用户机器可接受） |
| 命令注入 | ✅ 全程 `shell=False` + list 参数传递 |
| 路径穿越 | ✅ 拒绝 `..` 和绝对路径 |
| 敏感文件覆盖 | ✅ 拒绝 10 种保留文件名 |
| 误伤其他项目 | ✅ 远程仓库 URL 校验 |
| Docker 安全 | ✅ 非 root 用户运行 + 健康检查 |

详细安全说明请参见 [`DEVELOPMENT_MANUAL.md` §8](./DEVELOPMENT_MANUAL.md#8-security-best-practices)。

---

## 11. 项目信息

| 项目 | 信息 |
|------|------|
| **项目名称** | Github Auto Commit |
| **版本** | 1.0.0 |
| **语言** | Python 3.10+ |
| **许可证** | MIT |
| **作者** | 刘大硕（BI1IHA） |
| **GitHub** | [https://github.com/BI1IHA/git-auto-commit](https://github.com/BI1IHA/git-auto-commit) |

---

<p align="center">
  <sub>Made with ❤️ by 刘大硕 (BI1IHA) — 2026</sub>
</p>

> ✅ System operational as of 2026-07-15 12:55:49 UTC
