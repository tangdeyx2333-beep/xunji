# OpenClaw 多连接 API 文档

本文档描述了用于管理和使用多个 OpenClaw 连接配置的 API。

## 1. 配置管理 (CRUD)

### 1.1 获取所有配置

- **Endpoint**: `GET /api/openclaw/configs`
- **说明**: 获取指定用户的所有 OpenClaw 连接配置。
- **Query 参数**:
  - `user_id` (string, required): 用户的唯一标识。
- **响应**: `200 OK`
  - **Body**: `Array<OpenClawConfig>`

#### `OpenClawConfig` 响应模型

| 字段名 | 类型 | 说明 |
| :--- | :--- | :--- |
| `id` | string | 配置的唯一 ID |
| `user_id` | string | 所属用户的 ID |
| `display_name` | string | 配置的显示名称 |
| `gateway_url` | string | OpenClaw 网关 WebSocket 地址 |
| `session_key` | string | 会话 Key |
| `gateway_token` | string (nullable) | 网关鉴权 Token |
| `use_ssh` | boolean | 是否启用 SSH 隧道 |
| `ssh_host` | string (nullable) | SSH 服务器主机 IP |
| `ssh_port` | integer (nullable) | SSH 服务端口 |
| `ssh_user` | string (nullable) | SSH 用户名 |
| `ssh_local_port` | integer (nullable) | 本地映射端口 |
| `created_at` | datetime | 创建时间 |
| `updated_at` | datetime | 更新时间 |

---

### 1.2 创建新配置

- **Endpoint**: `POST /api/openclaw/configs`
- **说明**: 为用户创建一个新的 OpenClaw 连接配置。
- **请求 Body**: `OpenClawConfigCreate`
- **响应**: `200 OK`
  - **Body**: `OpenClawConfig` (创建成功后的完整配置对象)

#### `OpenClawConfigCreate` 请求模型

| 字段名 | 类型 | 必填 | 说明 |
| :--- | :--- | :--- | :--- |
| `user_id` | string | 是 | 用户 ID |
| `display_name` | string | 是 | 配置的显示名称 |
| `gateway_url` | string | 是 | 网关 WebSocket 地址 |
| `session_key` | string | 是 | 会话 Key |
| `gateway_token` | string | 否 | 网关鉴权 Token (与 password 二选一) |
| `gateway_password` | string | 否 | 网关鉴权 Password (与 token 二选一) |
| `use_ssh` | boolean | 否 | 是否启用 SSH 隧道 (默认 `false`) |
| `ssh_host` | string | 否 | SSH 主机 (当 `use_ssh=true` 时必填) |
| `ssh_port` | integer | 否 | SSH 端口 (默认 `22`) |
| `ssh_user` | string | 否 | SSH 用户名 (当 `use_ssh=true` 时必填) |
| `ssh_password` | string | 否 | SSH 密码 (当 `use_ssh=true` 时必填) |
| `ssh_local_port`| integer | 否 | 本地端口 (默认 `0` 随机) |

---

### 1.3 更新配置

- **Endpoint**: `PUT /api/openclaw/configs/{config_id}`
- **说明**: 更新一个已存在的 OpenClaw 配置。
- **Path 参数**:
  - `config_id` (string, required): 要更新的配置 ID。
- **请求 Body**: `OpenClawConfigUpdate` (结构同 `OpenClawConfigCreate`，但所有字段可选)
- **响应**: `200 OK`
  - **Body**: `OpenClawConfig` (更新后的完整配置对象)

---

### 1.4 删除配置

- **Endpoint**: `DELETE /api/openclaw/configs/{config_id}`
- **说明**: 删除一个 OpenClaw 配置。
- **Path 参数**:
  - `config_id` (string, required): 要删除的配置 ID。
- **Query 参数**:
  - `user_id` (string, required): 用户 ID，用于校验权限。
- **响应**: `200 OK`
  - **Body**: `{"status": "deleted", "id": "config-id-123"}`

---

## 2. 连接管理

### 2.1 连接已存在的配置

- **Endpoint**: `POST /api/openclaw/connect`
- **说明**: 根据配置 ID 建立与 OpenClaw 的连接。
- **请求 Body**:
  - `config_id` (string, required): 要连接的配置 ID。
- **响应**: `200 OK`
  - **Body**: `{"status": "connected", "config_id": "config-id-123", "message": "OpenClaw 连接成功"}`

### 2.2 创建并连接

- **Endpoint**: `POST /api/openclaw/configs/connect`
- **说明**: 创建一个新的配置并立即尝试连接。
- **请求 Body**: `OpenClawConfigCreate` (同 1.2)
- **响应**: `200 OK`
  - **Body**: `{"status": "connected", "config_id": "new-config-id-456", "message": "OpenClaw 连接成功"}`

---

## 3. 核心功能

### 3.1 对话

- **Endpoint**: `POST /api/openclaw/chat`
- **说明**: 与指定的 OpenClaw 配置进行流式对话。
- **请求 Body**:
  - `config_id` (string, required): 本次对话使用的配置 ID。
  - `message` (string, required): 发送的消息内容。
- **响应**: `text/event-stream` (SSE)
  - **成功**: `data: {"content": "..."}\n\n` ... `data: [DONE]\n\n`
  - **失败**: `data: {"content": "错误信息..."}\n\n` `data: [DONE]\n\n`

### 3.2 获取历史记录

- **Endpoint**: `GET /api/openclaw/history/{config_id}`
- **说明**: 获取指定配置的会话历史记录。
- **Path 参数**:
  - `config_id` (string, required): 要获取历史记录的配置 ID。
- **响应**: `200 OK`
  - **Body**: `Array<Message>` (消息对象数组)
