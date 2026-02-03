# AI 指令功能设计文档

## 修改摘要

本功能实现了用户可自定义的AI指令系统，允许用户在设置中添加多条指令，这些指令会在发起AI请求时自动拼接到系统提示词中，从而个性化AI的行为和响应风格。

### 主要改动

1. **数据库层**：新增 `ai_instructions` 表，用于存储用户指令
2. **API层**：新增 `/api/instructions` 端点，提供完整的CRUD操作
3. **服务层**：在聊天服务中实现指令注入逻辑
4. **测试层**：编写全面的单元测试，覆盖CRUD、权限隔离和prompt注入

## 架构设计思路

### 1. 数据库设计

#### 表结构：`ai_instructions`

```sql
CREATE TABLE ai_instructions (
    id VARCHAR PRIMARY KEY,           -- 唯一标识
    user_id VARCHAR NOT NULL,         -- 外键，关联用户表
    content TEXT NOT NULL,            -- 指令内容
    sort_order INTEGER DEFAULT 0,     -- 排序顺序
    created_at DATETIME,              -- 创建时间
    updated_at DATETIME,              -- 更新时间
    is_deleted BOOLEAN DEFAULT FALSE, -- 软删除标记
    FOREIGN KEY (user_id) REFERENCES users(id)
);
```

**设计考量：**

- **用户隔离**：通过 `user_id` 外键确保每个用户只能看到自己的指令
- **排序支持**：`sort_order` 字段允许用户自定义指令的显示和执行顺序
- **软删除**：使用 `is_deleted` 标记而非物理删除，便于数据恢复和审计
- **时间追踪**：`created_at` 和 `updated_at` 记录操作时间，便于问题排查

### 2. API 设计

#### 端点列表

| 方法 | 路径 | 功能 | 认证要求 |
|------|------|------|----------|
| GET | `/api/instructions` | 获取当前用户所有指令 | 需要 |
| POST | `/api/instructions` | 创建新指令 | 需要 |
| PUT | `/api/instructions/{id}` | 更新指令（内容/顺序） | 需要 |
| DELETE | `/api/instructions/{id}` | 删除指令 | 需要 |

#### 请求/响应格式

**创建指令请求：**
```json
{
  "content": "string"  // 必填，指令内容
}
```

**更新指令请求：**
```json
{
  "content": "string",      // 可选，新内容
  "sort_order": integer     // 可选，新排序
}
```

**响应格式：**
```json
{
  "id": "string",
  "content": "string",
  "sort_order": integer
}
```

**设计考量：**

- **RESTful风格**：遵循标准的HTTP方法和路径规范
- **最小化数据传输**：只返回必要的字段，减少网络开销
- **幂等性**：PUT和DELETE操作具备幂等性，可安全重试
- **权限控制**：所有操作都通过 `current_user` 进行用户隔离

### 3. 指令注入逻辑

#### 实现位置

在 `chat_services.py` 的 `astream_chat_with_model` 方法中，分别在两个分支注入指令：

1. **多模态分支**（支持图片/视频）
2. **非多模态分支**（纯文本）

#### 注入策略

```python
def _get_user_instructions(self, db: Session, user_id: str) -> str:
    """获取用户指令并格式化为字符串"""
    instructions = db.query(AiInstruction)\
        .filter(AiInstruction.user_id == user_id)\
        .filter(AiInstruction.is_deleted == False)\
        .order_by(AiInstruction.sort_order.asc(), AiInstruction.created_at.asc())\
        .all()
    
    if not instructions:
        return ""
    
    instruction_texts = [f"{i+1}. {inst.content}" for i, inst in enumerate(instructions)]
    return "额外指令：\n" + "\n".join(instruction_texts)
```

**格式化示例：**

```
额外指令：
1. 请用简洁的语言回答
2. 如果涉及代码，请提供完整的示例
3. 回答前先分析用户意图
```

**设计考量：**

- **无侵入性**：如果用户没有指令，不添加任何额外内容
- **清晰标识**：使用"额外指令："作为标题，明确告知AI这是用户自定义规则
- **有序列表**：使用数字编号，便于AI理解和遵循优先级
- **统一注入点**：在两个分支（多模态/非多模态）都注入，确保一致性

### 4. 权限与安全设计

#### 数据隔离

- **查询过滤**：所有数据库查询都包含 `user_id = current_user.id` 条件
- **操作验证**：更新和删除操作先验证记录归属，防止越权
- **软删除机制**：删除操作只标记 `is_deleted = True`，不物理删除

#### 输入验证

- **内容非空**：创建和更新时验证 `content` 不能为空
- **长度限制**：建议前端限制单条指令长度（如500字符），防止prompt过长
- **数量限制**：建议限制单个用户最多指令数（如20条），避免性能问题

### 5. 性能考量

#### 数据库优化

- **索引设计**：在 `user_id` 和 `sort_order` 字段上创建复合索引
  ```sql
  CREATE INDEX idx_ai_instructions_user_sort ON ai_instructions(user_id, sort_order);
  ```
- **查询优化**：使用 `filter().order_by().all()` 一次性获取所有数据

#### 缓存策略

- **短期缓存**：可考虑在请求级别缓存用户指令，避免多次查询
- **缓存失效**：用户修改指令后立即失效缓存

## 环境变量详细配置指南

### 必需配置

本功能不依赖额外的环境变量，使用现有的数据库配置即可。

### 可选配置

#### 1. 指令长度限制

```bash
# 单条指令最大长度（字符数）
# [可选] 默认：500
# [配置效果] 限制用户输入的指令长度，防止过长的指令影响token消耗和响应质量
# [格式] 正整数
MAX_INSTRUCTION_LENGTH=500
```

#### 2. 指令数量限制

```bash
# 每个用户最多可创建的指令数量
# [可选] 默认：20
# [配置效果] 防止用户创建过多指令导致prompt过长，影响API响应速度和成本
# [格式] 正整数
MAX_INSTRUCTIONS_PER_USER=20
```

#### 3. 指令注入开关

```bash
# 是否启用AI指令注入功能
# [可选] 默认：true
# [配置效果] 设置为false可临时禁用指令注入，便于问题排查
# [格式] true/false
ENABLE_AI_INSTRUCTIONS=true
```

### 配置示例（.env.example）

```bash
# ====================
# AI 指令配置
# ====================

# 单条指令最大长度（字符数）
# [可选] 默认：500
# [配置效果] 限制用户输入的指令长度，防止过长的指令影响token消耗和响应质量
# [格式] 正整数
MAX_INSTRUCTION_LENGTH=500

# 每个用户最多可创建的指令数量
# [可选] 默认：20
# [配置效果] 防止用户创建过多指令导致prompt过长，影响API响应速度和成本
# [格式] 正整数
MAX_INSTRUCTIONS_PER_USER=20

# 是否启用AI指令注入功能
# [可选] 默认：true
# [配置效果] 设置为false可临时禁用指令注入，便于问题排查
# [格式] true/false
ENABLE_AI_INSTRUCTIONS=true
```

## 前端集成建议

### 1. 设置页面UI

建议在设置弹窗中新增"AI指令"标签页，包含：

- **添加区域**：文本输入框 + 添加按钮
- **列表区域**：显示现有指令，支持编辑/删除/排序
- **提示信息**：说明指令的作用和使用方法

### 2. API调用示例

```javascript
// 获取指令列表
const instructions = await fetch('/api/instructions', {
  headers: { 'Authorization': `Bearer ${token}` }
}).then(r => r.json());

// 创建指令
await fetch('/api/instructions', {
  method: 'POST',
  headers: {
    'Content-Type': 'application/json',
    'Authorization': `Bearer ${token}`
  },
  body: JSON.stringify({ content: '新指令内容' })
});
```

### 3. 用户体验优化

- **实时预览**：显示指令将如何被格式化并注入到prompt中
- **字符计数**：实时显示已输入字符数，接近限制时警告
- **拖拽排序**：支持拖拽调整指令顺序
- **批量操作**：支持批量删除指令

## 扩展性考虑

### 1. 指令模板

未来可扩展支持指令模板功能：

- **预设模板**：提供常见场景的指令模板（如"代码助手"、"翻译专家"等）
- **自定义模板**：用户可保存自己的指令组合为模板
- **模板市场**：分享和发现优质指令模板

### 2. 条件指令

支持基于条件的指令激活：

- **模型特定指令**：不同模型使用不同指令集
- **场景特定指令**：根据对话主题自动选择相关指令
- **时间特定指令**：在特定时间段激活特定指令

### 3. 指令效果分析

- **使用统计**：记录每条指令被使用的频率
- **效果评估**：分析指令对AI响应质量的影响
- **智能建议**：基于用户行为推荐优化指令

## 安全注意事项

1. **Prompt注入防护**：对用户输入的指令进行适当的清理，防止恶意prompt注入
2. **内容审核**：考虑对指令内容进行敏感词过滤
3. **审计日志**：记录指令的创建、修改和删除操作，便于安全审计
4. **数据备份**：定期备份指令数据，防止意外丢失

## 性能监控指标

建议监控以下指标：

- **指令查询耗时**：`db.query(AiInstruction)...` 的执行时间
- **Prompt总长度**：注入后的系统提示词长度（影响token消耗）
- **指令使用率**：有多少比例的请求包含用户指令
- **缓存命中率**：如果实现了缓存，监控缓存效果

## 总结

本设计实现了完整的AI指令功能，从数据库到API再到前端集成，提供了灵活的用户自定义能力。通过合理的权限控制和性能优化，确保了系统的安全性和可用性。架构设计考虑了未来的扩展性，为后续功能迭代留下了空间。