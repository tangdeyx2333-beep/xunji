# OpenClaw 接口文档

## 1. 建立连接 (`/api/openclaw/connect`)

用于建立与 OpenClaw 网关的连接，并持久化保存配置信息。支持通过 SSH 隧道连接。

- **Method**: `POST`
- **Content-Type**: `application/json`

### 请求参数 (`OpenClawConnectRequest`)

| 参数名 | 类型 | 必填 | 说明 |
| :--- | :--- | :--- | :--- |
| `user_id` | string | 是 | 用户 ID，用于绑定连接配置 |
| `gateway_url` | string | 是 | OpenClaw 网关 WebSocket 地址 (如 `ws://127.0.0.1:18789`) |
| `session_key` | string | 是 | 会话 Key (如 `agent:main:main`) |
| `gateway_token` | string | 否 | 网关鉴权 Token (与 password 二选一) |
| `gateway_password` | string | 否 | 网关鉴权 Password (与 token 二选一) |
| `use_ssh` | boolean | 否 | 是否启用 SSH 隧道 (默认 `false`) |
| `ssh_host` | string | 否 | SSH 服务器主机 IP (当 `use_ssh=true` 时必填) |
| `ssh_port` | integer | 否 | SSH 服务端口 (默认 `22`) |
| `ssh_user` | string | 否 | SSH 用户名 (当 `use_ssh=true` 时必填) |
| `ssh_password` | string | 否 | SSH 密码 (当 `use_ssh=true` 时必填) |
| `ssh_local_port` | integer | 否 | 本地映射端口，`0` 表示随机分配 (默认 `0`) |

### 响应示例

**成功**:
```json
{
  "status": "connected",
  "user_id": "user-123",
  "message": "OpenClaw 连接成功并已保存配置"
}
```

**失败 (SSH 错误)**:
```json
{
  "detail": "SSH 隧道建立失败。请检查 SSH 配置信息，或确认服务器是否开启了 SSH 隧道功能 (AllowTcpForwarding)。错误: ..."
}
```

**失败 (连接错误)**:
```json
{
  "detail": "连接 OpenClaw 服务失败: ... 请检查 URL 是否连通或信息是否正确。"
}
```

---

## 2. 发送对话 (`/api/openclaw/chat`)

发送消息给 OpenClaw 并获取流式响应。系统会自动使用该用户的活跃连接或尝试从数据库恢复连接。

- **Method**: `POST`
- **Content-Type**: `application/json`
- **Response-Type**: `text/event-stream` (SSE)

### 请求参数 (`OpenClawChatRequest`)

| 参数名 | 类型 | 必填 | 说明 |
| :--- | :--- | :--- | :--- |
| `user_id` | string | 是 | 用户 ID，用于查找连接配置 |
| `message` | string | 是 | 发送给 AI 的消息内容 |

### 响应格式 (SSE)

响应为 Server-Sent Events 流，每条数据为 JSON 格式。

**正常响应**:
```text
data: {"content": "你好"}

data: {"content": "，"}

data: {"content": "我是"}

data: {"content": " OpenClaw。"}

data: [DONE]
```

**错误响应**:
```text
data: {"content": "连接 OpenClaw 服务失败，请前往设置页面配置连接信息。"}

data: [DONE]
```
