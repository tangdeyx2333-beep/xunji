# DESIGN_REPORT

## Modification Summary

- 重写根目录 README.md：补充项目定位、功能特性、技术栈、目录结构、快速开始与环境变量摘要
- README 补充“聊天树（Conversation Tree）”能力说明与相关接口/实现位置索引
- 新增环境变量模板：
  - xunji-backup/.env.example
  - xunji-frontend/.env.example
- 前端支持通过环境变量配置后端地址：
  - Axios `baseURL` 读取 `VITE_API_BASE_URL`
  - 流式聊天 fetch 读取 `VITE_API_BASE_URL`
- 修复后端文件上传端点的语法错误，并对 `SPLIT_FILENAME_ID` 做必填校验
- 修复前端构建错误：移除重复图标导入与未安装依赖 `vue-clipboard3` 的无效引用，并验证可成功 build
- 修复前端运行时报错：补充 `useRouter` 的缺失导入，避免页面初始化失败
- 修复后端聊天服务：恢复树状历史 `get_history_from_tree`，修复 Search/RAG 分支逻辑并保证可导入运行
- 修复后端依赖兼容性：RAG 服务改为延迟初始化 Chroma，并提供重建开关避免数据库版本不兼容阻塞服务
- 前端附件体验优化：粘贴/选择附件后提示“已添加附件”，并对超过 5MB 的文件提示将触发检索模式
- 新增聊天附件持久化：即时聊天附件上传到对象存储（默认阿里 OSS）并落库；历史/树路径接口返回附件元信息，前端按需获取带过期时间的 signed URL 并渲染

## Design Process

### README 结构设计

根目录 README 以“先能跑起来”为第一目标，按以下顺序组织信息：

- 一句话定位与核心能力：让首次阅读者快速判断项目用途
- 功能特性与技术栈：帮助评估选型与扩展成本
- 仓库结构：明确前后端边界与目录入口
- 快速开始：提供可复制的启动步骤，减少踩坑
- 环境变量摘要：把运行所需的关键配置集中说明，避免“到处找变量名”
- 聊天树：解释树状对话分叉的模型（TreeNode + parent_id）与前后端交互要点

### 配置与解耦

前端将后端地址从硬编码改为环境变量 `VITE_API_BASE_URL`，使得同一套前端构建产物可以在不同环境（本地/测试/生产）通过环境注入切换 API 地址，减少改代码与重复打包。

后端侧已使用 `python-dotenv` 加载 `.env`，因此通过补齐 `.env.example` 即可让配置可见、可复用，并避免把真实密钥写入仓库。

### 后端可运行性保障

RAG 服务（Chroma/Embeddings）采用延迟初始化策略：仅在启用知识库检索或触发大文件检索时才初始化向量库，从而避免向量库依赖问题阻塞基础聊天功能。

### 聊天附件存储

即时聊天附件与知识库上传分离：`/api/upload` 用于知识库文件（向量化）；聊天输入框附件随 `/api/chat` 发送，后端在 AI 回复结束后将附件上传到对象存储，并将 `storage_provider/storage_key/filename` 写入 `message_attachments`。历史回显阶段不直接返回永久 URL，而是由前端调用 `GET /api/attachments/{attachment_id}/signed-url` 获取带过期时间的临时访问链接。

### 安全与可维护性

- `.env.example` 仅提供变量名与示例值，不包含真实密钥
- 对后端 `SPLIT_FILENAME_ID` 做必填校验，避免在运行时产生不可控的文件命名行为

## Setup Guide

### 后端（xunji-backup）

1) 安装依赖

```bash
pip install -r xunji-backup/requirements.txt
```

2) 配置环境变量

- 复制 `xunji-backup/.env.example` 为 `xunji-backup/.env`
- 按你的模型选择填写对应的 API Key（例如 DashScope/Gemini/DeepSeek/Moonshot/Ollama 等）
- 如遇到 Chroma 数据目录兼容问题，可设置 `RAG_RESET_ON_SCHEMA_ERROR=true` 自动重建向量库（会清空旧数据）
- 如需启用聊天附件上传对象存储：设置 `OBJECT_STORAGE_PROVIDER=aliyun` 并配置阿里 OSS 环境变量（详见 `.env.example`），签名链接有效期由 `SIGNED_URL_EXPIRES_SECONDS_DEFAULT/MAX` 控制
- 说明：`.env.example` 中已用注释标明每个变量是 REQUIRED / OPTIONAL，以及“启用某功能时才需要”的条件

3) 启动服务（在 `xunji-backup` 目录执行）

```bash
uvicorn app.main:app --host 127.0.0.1 --port 8080
```

### 前端（xunji-frontend）

1) 安装依赖

```bash
npm -C xunji-frontend install
```

2) 配置 API 地址

- 推荐：复制 `xunji-frontend/.env.example` 为 `xunji-frontend/.env.local` 或 `xunji-frontend/.env`
- 设置 `VITE_API_BASE_URL`（例如 `http://127.0.0.1:8080`），修改后需要重启前端 dev server 才会生效

3) 启动开发服务

```bash
npm -C xunji-frontend run dev
```

4) 构建生产包

```bash
npm -C xunji-frontend run build
```
