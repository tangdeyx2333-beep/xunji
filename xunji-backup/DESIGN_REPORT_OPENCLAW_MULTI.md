# OpenClaw 多连接支持设计文档

## 修改摘要

本次重构将 OpenClaw 从“单配置单连接”模式升级为“多配置动态切换”模式：
- 数据层：用户与 OpenClaw 配置从 1:1 变为 1:N，新增 `display_name` 字段用于前端展示
- API 层：新增 `/configs` CRUD 端点，原 `/connect` 与 `/chat` 改为按配置 ID 维度管理连接与对话
- 前端：设置页支持增删改查多配置；顶部 OpenClaw 按钮改为下拉列表，用户可即时切换目标服务
- 状态管理：内存缓存 `active_connections/active_tunnels` 的 key 由 `user_id` 改为 `config_id`，实现配置级隔离

## 架构设计思路

### 1. 数据模型变更

#### 1.1 实体关系调整
```python
# 旧：User 1-1 OpenClawConfig
class User(Base):
    openclaw_config = relationship("OpenClawConfig", back_populates="user", uselist=False)

# 新：User 1-N OpenClawConfig
class User(Base):
    openclaw_configs = relationship("OpenClawConfig", back_populates="user")
```

#### 1.2 OpenClawConfig 表新增字段
```python
class OpenClawConfig(Base):
    display_name = Column(String, nullable=False, default="默认 OpenClaw", server_default="默认 OpenClaw")
```
**用途**：前端下拉列表展示，用户可自定义如“公司测试机”“家庭 NAS”等易读名称。

### 2. API 设计

#### 2.1 配置管理端点（新增）
| 方法 | 路径 | 功能 | 请求体 | 响应 |
|------|------|------|--------|------|
| GET | `/api/openclaw/configs?user_id=xxx` | 获取用户全部配置 | - | `[{id, display_name, gateway_url, ...}]` |
| POST | `/api/openclaw/configs` | 新建配置 | `OpenClawConnectRequest`（含 display_name） | `OpenClawConfig` |
| PUT | `/api/openclaw/configs/{config_id}` | 更新配置 | `OpenClawUpdateRequest` | `OpenClawConfig` |
| DELETE | `/api/openclaw/configs/{config_id}?user_id=xxx` | 删除配置 | - | `{"status":"deleted","id":xxx}` |

#### 2.2 连接与对话端点（改造）
| 方法 | 路径 | 变更点 | 说明 |
|------|------|--------|------|
| POST | `/api/openclaw/connect` | 请求体新增 `config_id` | 不再隐式使用 user_id 查找单配置，而是按 config_id 精确连接 |
| POST | `/api/openclaw/chat` | 请求体用 `config_id` 替代 `user_id` | 聊天时明确指定目标配置，实现多服务并行支持 |

#### 2.3 请求模型变更
```python
class OpenClawConnectRequest(BaseModel):
    user_id: str
    display_name: str          # 新增
    gateway_url: str
    ...

class OpenClawChatRequest(BaseModel):
    config_id: str             # 替代 user_id
    message: str
```

### 3. 内存状态管理

#### 3.1 缓存 Key 升级
```python
# 旧：以 user_id 为 key，无法区分多配置
active_connections: Dict[str, OpenClawChatWsAdapter]  # key = user_id
active_tunnels: Dict[str, SSHTunnelForwarder]         # key = user_id

# 新：以 config_id 为 key，实现配置级隔离
active_connections: Dict[str, OpenClawChatWsAdapter]  # key = config_id
active_tunnels: Dict[str, SSHTunnelForwarder]         # key = config_id
```

#### 3.2 连接生命周期
- 连接建立：调用 `POST /connect` 时传入 `config_id`，成功后将 adapter 与 tunnel 以 `config_id` 为 key 存入内存
- 连接复用：下次同 `config_id` 聊天时直接命中内存，无需重建 SSH 与 WebSocket
- 连接清理：支持单配置断开（`DELETE /connect/{config_id}`）或用户级全部断开（遍历其 configs）

### 4. 前端交互流程

#### 4.1 设置页 – 配置管理
```
┌──────────────┐
│ + 添加配置   │  ─┐
└──────────────┘   │ 弹出表单（display_name / URL / token / SSH 等）
┌──────────────┐   │ 提交 POST /configs
│ 配置列表     │ ◄─┘
│ ┌────────────┐
│ │ 公司测试机 │ 编辑 / 删除 / 连接测试
│ └────────────┘
│ ┌────────────┐
│ │ 家庭 NAS   │
│ └────────────┘
└──────────────┘
```
- 进入页面即 `GET /configs` 拉取列表
- 支持行内编辑（PUT）与删除（DELETE）
- 可一键“连接测试”确保配置可用

#### 4.2 顶部操作区 – 动态下拉
```
┌────────────────────┐
│ ▼ OpenClaw         │ 点击展开下拉
└────────────────────┘
    ├─ 公司测试机     ◄─ 选中后立即调用 /connect（若未连），后续聊天走此配置
    ├─ 家庭 NAS
    └─ 管理配置...    ── 跳转设置页
```
- 首次加载时默认选中第一个已连接或列表第一项
- 切换选项时即时切换 `config_id`，主输入框发送逻辑随之指向新服务
- 下拉底部提供“管理配置”入口，方便快速跳转

### 5. 安全与隔离

- **配置隔离**：同一用户不同配置完全独立，互不干扰；A 配置断线不影响 B 配置
- **权限校验**：所有 config 操作均校验 `user_id`，防止横向越权访问他人配置
- **软删除**：数据库仍保留 `is_deleted` 字段，支持误删恢复（本阶段可暂不实现 UI）

### 6. 向后兼容

- 旧版前端未传 `config_id` 时，后端可降级策略：若用户仅有一个配置则自动选用，无或多配置则返回错误提示“请升级客户端”，确保接口可平滑过渡

## 环境变量详细配置指南

### 可选配置

#### 1. 单用户最大配置数
```bash
# 每个用户最多可创建的 OpenClaw 配置数量
# [可选] 默认：10
# [配置效果] 防止用户创建过多配置导致数据库与内存膨胀
# [格式] 正整数
MAX_OPENCLAW_CONFIGS_PER_USER=10
```

#### 2. 连接空闲超时
```bash
# OpenClaw 连接在内存中的最大空闲时长（秒），超时后自动断开以释放资源
# [可选] 默认：1800（30 分钟）
# [配置效果] 降低服务器内存占用；下次聊天时会自动重连
# [格式] 正整数
OPENCLAW_CONNECTION_IDLE_TIMEOUT=1800
```

### 配置示例（.env.example）
```bash
# ====================
# OpenClaw 多连接配置
# ====================

# 每个用户最多可创建的 OpenClaw 配置数量
# [可选] 默认：10
# [配置效果] 防止用户创建过多配置导致数据库与内存膨胀
# [格式] 正整数
MAX_OPENCLAW_CONFIGS_PER_USER=10

# OpenClaw 连接在内存中的最大空闲时长（秒），超时后自动断开以释放资源
# [可选] 默认：1800（30 分钟）
# [配置效果] 降低服务器内存占用；下次聊天时会自动重连
# [格式] 正整数
OPENCLAW_CONNECTION_IDLE_TIMEOUT=1800
```

## 前端集成建议

### 1. 状态管理（Pinia / Vuex）
```typescript
interface OpenClawConfig {
  id: string
  display_name: string
  gateway_url: string
  session_key: string
  use_ssh: boolean
  // ... 其他字段
}

export const useOpenClawStore = defineStore('openclaw', () => {
  const configs = ref<OpenClawConfig[]>([])
  const activeConfigId = ref<string>('')
  const isConnected = computed(() => activeConfigId.value !== '')

  async function loadConfigs(user_id: string) {
    configs.value = await api.get(`/openclaw/configs?user_id=${user_id}`)
    if (configs.value.length > 0 && !activeConfigId.value) {
      activeConfigId.value = configs.value[0].id
    }
  }

  async function connect(configId: string) {
    await api.post('/openclaw/connect', { config_id: configId })
    activeConfigId.value = configId
  }

  return { configs, activeConfigId, isConnected, loadConfigs, connect }
})
```

### 2. 顶部下拉组件伪代码
```vue
<template>
  <el-dropdown @command="handleSelect">
    <el-button>{{ currentName || 'OpenClaw' }} <i class="el-icon-arrow-down"></i></el-button>
    <template #dropdown>
      <el-dropdown-menu>
        <el-dropdown-item v-for="cfg in configs" :key="cfg.id" :command="cfg.id">
          {{ cfg.display_name }}
        </el-dropdown-item>
        <el-dropdown-item divided command="manage">管理配置</el-dropdown-item>
      </el-dropdown-menu>
    </template>
  </el-dropdown>
</template>

<script setup>
const openclawStore = useOpenClawStore()
const { configs, activeConfigId } = storeToRefs(openclawStore)

const currentName = computed(() => {
  const cfg = configs.value.find(c => c.id === activeConfigId.value)
  return cfg ? cfg.display_name : ''
})

function handleSelect(cmd: string) {
  if (cmd === 'manage') {
    router.push('/settings#openclaw')
  } else {
    openclawStore.connect(cmd)
  }
}
</script>
```

### 3. 设置页表单字段
- `display_name`（必填，最大 20 字符）
- `gateway_url`（必填，WebSocket URL 格式校验）
- `session_key`（必填）
- `gateway_token / gateway_password`（二选一）
- `use_ssh` 开关，展开后显示 SSH 主机、端口、用户名、密码

### 4. 错误处理
- 当用户无配置时，顶部下拉仅显示“管理配置”引导
- 连接失败时在下拉项右侧小红点提示，hover 显示错误原因
- 聊天接口返回 400/500 时自动弹出“重新连接”按钮

## 性能与监控

### 1. 关键指标
- **配置数量分布**：统计用户拥有配置数的 P50/P90，评估 `MAX_OPENCLAW_CONFIGS_PER_USER` 合理性
- **连接复用率**：内存命中次数 / 总聊天次数，衡量长连接有效性
- **SSH 隧道数**：监控 `active_tunnels` 总量，防止端口耗尽

### 2. 日志规范
```python
logger.info("[OpenClaw] connect success", extra={"config_id": cfg.id, "user_id": user.id})
logger.warning("[OpenClaw] connect failed", extra={"config_id": cfg.id, "error": str(e)})
```

### 3. 可扩展预留
- 后续若需支持“系统级共享配置”，可在 `OpenClawConfig` 增加 `scope: 'user' | 'system'` 字段
- 若需支持“配置分组/标签”，可新增关联表，前端展示树形或标签页选择

## 测试策略

### 1. 单元测试（后端）
- CRUD 接口权限隔离：A 用户无法操作 B 用户配置
- 连接建立与复用：同 `config_id` 多次聊天只建一次连接
- 配置删除后内存回收：调用 `DELETE /configs/{id}` 后对应 adapter 与 tunnel 被清理

### 2. 前端集成测试
- 设置页增删改查后列表实时刷新
- 顶部切换配置后聊天请求体携带正确 `config_id`
- 网络异常时下拉项错误提示与重连引导

### 3. 端到端验收
- 场景：用户添加两个配置 → 分别连接 → 交替聊天 → 删除一个 → 剩余配置仍可正常对话
- 性能：20 配置并发聊天，内存占用与响应延迟可接受

## 交付清单

1. **数据库迁移脚本**：新增 `display_name` 字段 & 回填默认值
2. **后端代码**：
   - `app/models/sql_models.py` 关系与字段调整
   - `app/api/endpoints/openclaw.py` 新增 CRUD 与改造 connect/chat
3. **API 文档**：`OPENCLAW_API.md` 更新接口参数与示例
4. **前端代码**：
   - 设置页组件（配置列表 + 表单抽屉）
   - 顶部下拉组件（状态管理 + 事件绑定）
5. **测试覆盖**：
   - `tests/test_openclaw_multi.py` 单元与集成用例
   - 人工端到端验收报告
6. **配置模板**：`.env.example` 新增可选参数说明

---

> 本设计文档遵循“先文档后代码”原则，所有后续实现必须与此文档保持一致；如需变更，须先更新本文档并评审通过。