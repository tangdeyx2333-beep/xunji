<script setup>
import { ref, reactive, computed, onMounted, nextTick, watch } from 'vue'
import * as echarts from 'echarts'
import {
  Plus, Setting, User,
  ChatDotRound, Menu,
  Compass, DataLine, Trophy, Collection,
  Connection,
  Document, Paperclip, ArrowDown, Delete,
  Share, CopyDocument, Position, Loading, SwitchButton, Close, UploadFilled, Service // 引入新图标
} from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import { openClawChatStream, connectOpenClaw, getOpenClawHistory, getOpenClawConfigs, createAndConnectOpenClaw } from '@/api/openclaw'

// --- API --- API ---
import { getFiles, uploadFile, deleteFile, clearKnowledgeBase } from '@/api/file'
// ★ 引入 chatStream8
import { chatStream, getConversations, getConversationMessages, deleteConversation, getNodePath, getModels, createModel, deleteModel, getAttachmentSignedUrl, getInstructions, createInstruction, updateInstruction, deleteInstruction, getConversationInstructions, createConversationInstruction, updateConversationInstruction, deleteConversationInstruction } from '@/api/chat'
import renderMarkdown from '@/utils/markdown'
import { useUserStore } from '@/stores/userStore'
import { login, upgradeAccount } from '@/api/auth'

import OpenClawSettings from './OpenClawSettings.vue'

// --- 1. 基础配置 ---
const APP_NAME = ref("xunji")
const userStore = useUserStore()
const chatContainerRef = ref(null)

// --- 2. 界面状态 ---
// ★★★ 新增：Session Cache ★★★
const sessionCache = reactive({
  // key: conversationId
  // value: {
  //   messages: [],       // 消息列表
  //   isSending: false,   // 该会话是否正在发送
  //   currentLeafId: null // 上下文节点
  //   scrollTop: 0        // 滚动位置
  // }
})

// ★★★ 新增：即时聊天文件状态 ★★★
const currentAttachments = ref([]) // 格式: [{name, type, base64, size}]
const chatFileInput = ref(null) // 文件输入框 ref
const MAX_DIRECT_READ_SIZE_BYTES = 5 * 1024 * 1024

const isSidebarCollapsed = ref(false)
const inputMessage = ref('')
const currentModel = ref('deepseek-chat')
const enableSearch = ref(false)
const showChatTree = ref(false) // 控制树状图弹窗显示
const showConversationInstructions = ref(false)

// --- 3. 会话管理 ---
const showSettings = ref(false)
const settingsActiveTab = ref('models')
const availableModels = ref([
  // 默认模型 (可以被后端数据覆盖或合并)
  { model_name: 'deepseek-chat', display_name: 'DeepSeek Chat' },
  { model_name: 'deepseek-chat-thinking', display_name: 'DeepSeek Chat Thinking' },
  { model_name: 'kimi-k2.5', display_name: 'Kimi-k2.5 多模态' },
  { model_name: 'kimi-k2-thinking', display_name: 'Kimi-k2 Thinking' },
  { model_name: 'qwen3-max', display_name: 'Qwen3 Max' },

])
const newModelForm = reactive({ model_name: '', display_name: '' })

const aiInstructionInput = ref('')
const aiInstructions = ref([])
const isInstructionsLoading = ref(false)
const isInstructionSubmitting = ref(false)
const isAccountUpgrading = ref(false)
const isAccountRecovering = ref(false)
const accountUpgradeForm = reactive({ username: '', password: '' })
const accountRecoveryForm = reactive({ username: '', password: '' })

const isOpenClawConnecting = ref(false)

const conversationInstructionInput = ref('')
const conversationInstructions = ref([])
const isConversationInstructionsLoading = ref(false)
const isConversationInstructionSubmitting = ref(false)

// --- 3. 会话管理 ---
const currentConversationId = ref(null)
// const currentLeafId = ref(null) // 移除独立的 ref，改用计算属性或从 Cache 获取
// const chatHistory = ref([]) // 移除独立的 ref

// 计算属性：当前是否正在发送
const isSending = computed(() => {
  const parentKey = (currentLeafId.value || 'root')
  if (!currentConversationId.value) {
    return !!tempNewSessionState.sendingByParent?.[parentKey]
  }
  const state = sessionCache[currentConversationId.value]
  return !!state?.sendingByParent?.[parentKey]
})

// 计算属性：当前是否在聊天中（用于显示欢迎页）
const isChatting = computed(() => {
  if (!currentConversationId.value) return false
  const msgs = sessionCache[currentConversationId.value]?.messages || []
  return msgs.length > 0
})

// 计算属性：当前显示的消息列表
const chatHistory = computed(() => {
  if (!currentConversationId.value) return [] // 新会话初始为空，或者需要一个临时变量
  return sessionCache[currentConversationId.value]?.messages || []
})

// 计算属性：当前叶子节点
const currentLeafId = computed({
  get: () => {
    if (!currentConversationId.value) return null
    return sessionCache[currentConversationId.value]?.currentLeafId || null
  },
  set: (val) => {
    if (currentConversationId.value && sessionCache[currentConversationId.value]) {
      sessionCache[currentConversationId.value].currentLeafId = val
    }
  }
})

// 临时变量：用于"新会话"（尚未生成 ID 时）的临时消息存储
// 当用户点击 New Chat 时，currentConversationId = null
// 我们需要一个临时的 storage，等到第一条消息发送成功获得 session_id 后，再迁移到 sessionCache
const tempNewSessionState = reactive({
  messages: [],
  currentLeafId: null,
  isSending: false,
  sendingByParent: {}
})

// 修改 chatHistory 的计算逻辑以支持新会话
const displayMessages = computed(() => {
  if (!currentConversationId.value) {
    return tempNewSessionState.messages
  }
  return sessionCache[currentConversationId.value]?.messages || []
})

const historyList = ref([])

const isOpenClawMode = ref(false)
const openClawConfigs = ref([]) // OpenClaw配置列表
const currentOpenClawConfig = ref(null) // 当前选中的配置
const selectedConfigId = ref(null) // 选中的配置ID
const showOpenClawConfigDialog = ref(false) // 显示配置选择对话框
const openClawState = reactive({
  messages: [],
  isSending: false,
})
const lastNormalConversationId = ref(null)

const viewTitle = computed(() => {
  if (isOpenClawMode.value) {
    return currentOpenClawConfig.value?.display_name || 'OpenClaw'
  }
  return currentModel.value
})

const viewMessages = computed(() => {
  return isOpenClawMode.value ? openClawState.messages : displayMessages.value
})

const isChattingView = computed(() => {
  return viewMessages.value.length > 0
})

const isSendingView = computed(() => {
  return isOpenClawMode.value ? openClawState.isSending : isSending.value
})

// --- OpenClaw 多配置支持 ---
const fetchOpenClawConfigs = async () => {
  try {
    const configs = await getOpenClawConfigs(userStore.userInfo?.id)
    openClawConfigs.value = configs || []
  } catch (error) {
    console.error('获取OpenClaw配置失败:', error)
    ElMessage.error('获取OpenClaw配置失败')
  }
}

const selectOpenClawConfig = async (config) => {
  try {
    currentOpenClawConfig.value = config
    await connectOpenClawByConfig(config.id)
    ElMessage.success(`已切换到配置: ${config.display_name}`)
    
    // 重新进入OpenClaw模式以加载新配置的历史记录
    if (isOpenClawMode.value) {
      await enterOpenClawMode()
    }
  } catch (error) {
    console.error('切换OpenClaw配置失败:', error)
    ElMessage.error('切换配置失败: ' + (error.message || '未知错误'))
  }
}

const handleSelectOpenClawConfig = async () => {
  if (!selectedConfigId.value) {
    ElMessage.warning('请选择一个配置')
    return
  }
  
  const config = openClawConfigs.value.find(c => c.id === selectedConfigId.value)
  if (!config) {
    ElMessage.error('配置不存在')
    return
  }
  
  showOpenClawConfigDialog.value = false
  await selectOpenClawConfig(config)
}

const connectOpenClawByConfig = async (configId) => {
  try {
    isOpenClawConnecting.value = true
    await connectOpenClaw(configId)
    // 连接成功后加载历史记录
    await loadOpenClawHistory(configId)
  } catch (error) {
    console.error('连接OpenClaw失败:', error)
    ElMessage.error('连接OpenClaw失败: ' + error.message)
    throw error
  } finally {
    isOpenClawConnecting.value = false
  }
}

const loadOpenClawHistory = async (configId) => {
  try {
    const history = await getOpenClawHistory(configId)
    console.log('OpenClaw History Data:', history)
    const formattedHistory = history.map((item, index) => {
      try {
        return {
          role: item.role,
          content: item.content[0]?.text || '',
          html: renderMarkdown(item.content[0]?.text || ''),
          loading: false,
          done: true,
          timestamp: item.timestamp
        }
      } catch (e) {
        console.error(`格式化第 ${index} 条历史记录失败:`, item, e)
        throw e
      }
    })
    openClawState.messages = formattedHistory
  } catch (error) {
    console.error('加载OpenClaw历史记录失败:', error)
    ElMessage.error('加载历史记录失败')
    throw error
  }
}

const enterOpenClawMode = async () => {
  if (!isOpenClawMode.value) {
    lastNormalConversationId.value = currentConversationId.value
    isOpenClawMode.value = true
  }

  // 如果没有配置，先获取配置列表
  if (openClawConfigs.value.length === 0) {
    await fetchOpenClawConfigs()
  }

  // 如果没有选中配置且只有一个配置，自动选中
  if (!currentOpenClawConfig.value && openClawConfigs.value.length === 1) {
    currentOpenClawConfig.value = openClawConfigs.value[0]
  }

  // 如果仍然没有选中配置，显示配置选择对话框
  if (!currentOpenClawConfig.value) {
    showOpenClawConfigDialog.value = true
    return
  }

  openClawState.messages = []
  openClawState.isSending = false
  inputMessage.value = ''
  currentAttachments.value = []
  selectedFileIds.value = []

  // 加载历史记录
  try {
    await loadOpenClawHistory(currentOpenClawConfig.value.id)
  } catch (error) {
    ElMessage.error('加载 OpenClaw 历史记录失败，请检查控制台')
    console.error('OpenClaw 历史记录加载错误详情:', error)
  }

  // 添加欢迎消息（如果历史记录为空）
  if (openClawState.messages.length === 0) {
    openClawState.messages.push({
      role: 'ai',
      content: `你好，我是 ${currentOpenClawConfig.value.display_name}。有什么可以帮您？`,
      html: renderMarkdown(`你好，我是 ${currentOpenClawConfig.value.display_name}。有什么可以帮您？`),
      loading: false,
      done: true,
    })
  }

  scrollToBottom()
}

const exitOpenClawMode = async () => {
  if (!isOpenClawMode.value) return
  isOpenClawMode.value = false

  inputMessage.value = ''
  currentAttachments.value = []

  if (lastNormalConversationId.value) {
    await switchSession({ id: lastNormalConversationId.value })
  } else {
    startNewChat()
  }
}

const sendMessageToOpenClaw = async () => {
  const text = inputMessage.value.trim()
  if (!text || openClawState.isSending) return

  openClawState.messages.push({ role: 'user', content: text, loading: false, done: true })
  inputMessage.value = ''
  currentAttachments.value = []

  scrollToBottom()

  const aiMessage = reactive({
    role: 'ai',
    content: '',
    html: '',
    loading: true,
    done: false,
  })
  openClawState.messages.push(aiMessage)
  scrollToBottom()

  openClawState.isSending = true

  await openClawChatStream(
    { message: text, config_id: currentOpenClawConfig.value.id },
    (chunk) => {
      aiMessage.loading = false
      aiMessage.content += chunk
      aiMessage.html = renderMarkdown(aiMessage.content)
      scrollToBottom()
    },
    () => {
      aiMessage.loading = false
      aiMessage.done = true
      openClawState.isSending = false
      scrollToBottom()
    },
    (err) => {
      aiMessage.loading = false
      aiMessage.done = true
      aiMessage.content += `\n[错误: ${err.message}]`
      aiMessage.html = renderMarkdown(aiMessage.content)
      openClawState.isSending = false
      scrollToBottom()
      
      // 如果是未配置错误，自动跳转设置
      if (err.message.includes('未配置') || err.message.includes('前往设置')) {
         showSettings.value = true
         settingsActiveTab.value = 'openclaw'
      }
    }
  )
}

// --- OpenClaw 连接逻辑 ---
// --- 4. RAG 文件逻辑 ---
const selectedFileIds = ref([])
const userFiles = ref([])
const isUploading = ref(false)
const fileInput = ref(null)
const selectedCount = computed(() => selectedFileIds.value.length)

// --- 5. 生命周期 ---
onMounted(async () => {
  await fetchFileList()
  await fetchSessionList()
  await fetchModelList()
  await fetchOpenClawConfigs()
})

const currentSessionMessages = ref([]) // 当前会话的原始消息列表

// --- 6. 核心方法集 ---

watch(showSettings, async (isOpen) => {
  if (!isOpen) return
  await fetchInstructions()
})

watch(showConversationInstructions, async (isOpen) => {
  if (!isOpen) return
  await fetchConversationInstructions()
})

watch(currentConversationId, async () => {
  if (!showConversationInstructions.value) return
  await fetchConversationInstructions()
})

// 监听输入框内容变化，保持滚动位置
watch(inputMessage, () => {
  nextTick(() => {
    scrollToBottom()
  })
})

const fetchModelList = async () => {
  try {
    const res = await getModels()
    // 合并默认模型和后端返回的自定义模型
    // 去重逻辑：如果后端有，优先用后端的（虽然这里简化处理，直接追加）
    const customModels = res.map(m => ({ ...m, is_custom: true }))
    
    // 简单的合并策略：默认模型 + 自定义模型
    // 实际生产中可能希望完全由后端控制
    const defaultModels = [
      { model_name: 'deepseek-chat', display_name: 'DeepSeek Chat' },
      { model_name: 'kimi-k2.5', display_name: 'Kimi-k2.5 多模态' },
      { model_name: 'kimi-k2-thinking', display_name: 'Kimi-k2 Thinking' },
      { model_name: 'qwen3-max', display_name: 'Qwen3 Max' },
    ]
    
    // 过滤掉已经在 customModels 里的默认模型 (按 model_name)
    const existingNames = new Set(customModels.map(m => m.model_name))
    const filteredDefaults = defaultModels.filter(m => !existingNames.has(m.model_name))
    
    availableModels.value = [...filteredDefaults, ...customModels]
  } catch (error) {
    console.error("加载模型列表失败:", error)
  }
}

const fetchInstructions = async () => {
  try {
    isInstructionsLoading.value = true
    const res = await getInstructions()
    aiInstructions.value = Array.isArray(res) ? res : []
  } catch (error) {
    console.error('加载 AI 指令失败:', error)
    ElMessage.error('加载 AI 指令失败')
  } finally {
    isInstructionsLoading.value = false
  }
}

const handleAddInstruction = async () => {
  const content = (aiInstructionInput.value || '').trim()
  if (!content) {
    ElMessage.warning('请输入指令内容')
    return
  }
  try {
    isInstructionSubmitting.value = true
    await createInstruction({ content })
    aiInstructionInput.value = ''
    ElMessage.success('添加成功')
    await fetchInstructions()
  } catch (error) {
    ElMessage.error(error?.message || '添加失败')
  } finally {
    isInstructionSubmitting.value = false
  }
}

const handleDeleteInstruction = async (row) => {
  try {
    await deleteInstruction(row.id)
    ElMessage.success('删除成功')
    await fetchInstructions()
  } catch (error) {
    ElMessage.error(error?.message || '删除失败')
  }
}

const moveInstructionUp = async (row) => {
  const idx = aiInstructions.value.findIndex((r) => r.id === row.id)
  if (idx <= 0) return
  const prev = aiInstructions.value[idx - 1]
  const curr = aiInstructions.value[idx]
  try {
    await updateInstruction(curr.id, { sort_order: prev.sort_order })
    await updateInstruction(prev.id, { sort_order: curr.sort_order })
    await fetchInstructions()
  } catch (error) {
    ElMessage.error(error?.message || '排序调整失败')
  }
}

const moveInstructionDown = async (row) => {
  const idx = aiInstructions.value.findIndex((r) => r.id === row.id)
  if (idx < 0 || idx >= aiInstructions.value.length - 1) return
  const next = aiInstructions.value[idx + 1]
  const curr = aiInstructions.value[idx]
  try {
    await updateInstruction(curr.id, { sort_order: next.sort_order })
    await updateInstruction(next.id, { sort_order: curr.sort_order })
    await fetchInstructions()
  } catch (error) {
    ElMessage.error(error?.message || '排序调整失败')
  }
}

const fetchConversationInstructions = async () => {
  if (!currentConversationId.value) {
    conversationInstructions.value = []
    return
  }
  try {
    isConversationInstructionsLoading.value = true
    const res = await getConversationInstructions(currentConversationId.value)
    conversationInstructions.value = Array.isArray(res) ? res : []
  } catch (error) {
    console.error('加载会话指令失败:', error)
    ElMessage.error('加载会话指令失败')
  } finally {
    isConversationInstructionsLoading.value = false
  }
}

const handleAddConversationInstruction = async () => {
  if (!currentConversationId.value) {
    ElMessage.warning('请先开始一次对话生成会话')
    return
  }
  const content = (conversationInstructionInput.value || '').trim()
  if (!content) {
    ElMessage.warning('请输入指令内容')
    return
  }
  try {
    isConversationInstructionSubmitting.value = true
    await createConversationInstruction(currentConversationId.value, { content })
    conversationInstructionInput.value = ''
    ElMessage.success('添加成功')
    await fetchConversationInstructions()
  } catch (error) {
    ElMessage.error(error?.message || '添加失败')
  } finally {
    isConversationInstructionSubmitting.value = false
  }
}

const handleDeleteConversationInstruction = async (row) => {
  if (!currentConversationId.value) return
  try {
    await deleteConversationInstruction(currentConversationId.value, row.id)
    ElMessage.success('删除成功')
    await fetchConversationInstructions()
  } catch (error) {
    ElMessage.error(error?.message || '删除失败')
  }
}

const moveConversationInstructionUp = async (row) => {
  if (!currentConversationId.value) return
  const idx = conversationInstructions.value.findIndex((r) => r.id === row.id)
  if (idx <= 0) return
  const prev = conversationInstructions.value[idx - 1]
  const curr = conversationInstructions.value[idx]
  try {
    await updateConversationInstruction(currentConversationId.value, curr.id, { sort_order: prev.sort_order })
    await updateConversationInstruction(currentConversationId.value, prev.id, { sort_order: curr.sort_order })
    await fetchConversationInstructions()
  } catch (error) {
    ElMessage.error(error?.message || '排序调整失败')
  }
}

const moveConversationInstructionDown = async (row) => {
  if (!currentConversationId.value) return
  const idx = conversationInstructions.value.findIndex((r) => r.id === row.id)
  if (idx < 0 || idx >= conversationInstructions.value.length - 1) return
  const next = conversationInstructions.value[idx + 1]
  const curr = conversationInstructions.value[idx]
  try {
    await updateConversationInstruction(currentConversationId.value, curr.id, { sort_order: next.sort_order })
    await updateConversationInstruction(currentConversationId.value, next.id, { sort_order: curr.sort_order })
    await fetchConversationInstructions()
  } catch (error) {
    ElMessage.error(error?.message || '排序调整失败')
  }
}

const handleAddModel = async () => {
  if (!newModelForm.model_name || !newModelForm.display_name) {
    ElMessage.warning('请填写完整信息')
    return
  }
  try {
    await createModel(newModelForm)
    ElMessage.success('添加成功')
    newModelForm.model_name = ''
    newModelForm.display_name = ''
    await fetchModelList()
  } catch (error) {
    ElMessage.error(error.message || '添加失败')
  }
}

const handleDeleteModel = async (model) => {
  if (!model.is_custom) {
    ElMessage.warning('默认模型不可删除')
    return
  }
  try {
    await deleteModel(model.id)
    ElMessage.success('删除成功')
    await fetchModelList()
    // 如果当前选中的是被删除的模型，重置为默认
    if (currentModel.value === model.model_name) {
       currentModel.value = 'deepseek-chat'
    }
  } catch (error) {
    ElMessage.error('删除失败')
  }
}

const fetchSessionList = async () => {
  try {
    const res = await getConversations({ limit: 50 })
    historyList.value = res
  } catch (error) {
    console.error("加载历史会话失败:", error)
  }
}

const switchSession = async (session) => {
  if (isOpenClawMode.value) {
    isOpenClawMode.value = false
  }
  // 确保设置界面和弹窗关闭
  showSettings.value = false
  showConversationInstructions.value = false
  showChatTree.value = false
  if (currentConversationId.value === session.id) return

  // 1. 记录当前会话的滚动位置 (如果存在)
  if (currentConversationId.value && sessionCache[currentConversationId.value] && chatContainerRef.value) {
     sessionCache[currentConversationId.value].scrollTop = chatContainerRef.value.scrollTop
  }

  currentConversationId.value = session.id
  
  // 2. 检查缓存中是否有数据
  if (sessionCache[session.id]) {
    // 命中缓存，无需重新请求
    // 恢复滚动位置
    nextTick(() => {
       if (chatContainerRef.value && sessionCache[session.id].scrollTop !== undefined) {
          chatContainerRef.value.scrollTop = sessionCache[session.id].scrollTop
       } else {
          scrollToBottom()
       }
    })
    return
  }

  // 3. 未命中缓存，初始化结构
  sessionCache[session.id] = {
    messages: [],
    isSending: false,
    sendingByParent: {},
    currentLeafId: null,
    scrollTop: 0
  }

  try {
    const messages = await getConversationMessages(session.id)
    currentSessionMessages.value = messages // 保存原始消息用于树状恢复
    
    // 转换消息格式
    sessionCache[session.id].messages = messages.map(msg => {
      // 兼容后端可能返回的各种角色名
      const isAI = ['assistant', 'ai', 'model'].includes(msg.role)
      return {
        role: isAI ? 'ai' : 'user',
        content: msg.content,
        html: isAI ? renderMarkdown(msg.content) : '',
        attachments: msg.attachments || [],
        loading: false,
        done: true // 历史消息默认已完成
      }
    })
    
    // 更新 currentLeafId
    if (messages.length > 0) {
       const lastMsg = messages[messages.length - 1]
       sessionCache[session.id].currentLeafId = lastMsg.node_id
    }
    
    scrollToBottom()
  } catch (error) {
    ElMessage.error("加载消息失败")
    // 加载失败，清理缓存防止下次误判
    delete sessionCache[session.id]
  }
}

const startNewChat = () => {
  if (isOpenClawMode.value) {
    isOpenClawMode.value = false
  }
  // 开始新会话前确保设置界面和弹窗关闭
  showSettings.value = false
  showConversationInstructions.value = false
  showChatTree.value = false
  currentConversationId.value = null
  // 重置临时状态
  tempNewSessionState.messages = []
  tempNewSessionState.currentLeafId = null
  tempNewSessionState.isSending = false
  tempNewSessionState.sendingByParent = {}
  
  inputMessage.value = ''
  selectedFileIds.value = []
}

const removeSession = async (e, id) => {
  e.stopPropagation()
  try {
    await deleteConversation(id)
    ElMessage.success('删除成功')
    await fetchSessionList()
    if (currentConversationId.value === id) {
      startNewChat()
    }
  } catch (error) {
    ElMessage.error('删除失败')
  }
}

const handleUpgradeAccount = async () => {
  if (!accountUpgradeForm.username) {
    ElMessage.warning('请填写用户名')
    return
  }
  try {
    isAccountUpgrading.value = true
    const res = await upgradeAccount({
      username: accountUpgradeForm.username,
      password: accountUpgradeForm.password || null
    })
    userStore.token = res.access_token
    userStore.userInfo = { id: res.user_id, username: res.username }
    localStorage.setItem('access_token', res.access_token)
    localStorage.setItem('user_info', JSON.stringify(userStore.userInfo))
    if (res.device_id) {
      localStorage.setItem('device_id', res.device_id)
    }
    ElMessage.success('账号已升级')
  } catch (error) {
    const message = error?.response?.data?.detail || '升级失败'
    ElMessage.error(message)
  } finally {
    isAccountUpgrading.value = false
  }
}

const handleRecoverAccount = async () => {
  if (!accountRecoveryForm.username) {
    ElMessage.warning('请填写用户名')
    return
  }
  try {
    isAccountRecovering.value = true
    const res = await login({
      username: accountRecoveryForm.username,
      password: accountRecoveryForm.password || ''
    })
    userStore.token = res.access_token
    userStore.userInfo = { id: res.user_id, username: res.username }
    localStorage.setItem('access_token', res.access_token)
    localStorage.setItem('user_info', JSON.stringify(userStore.userInfo))
    if (res.device_id) {
      localStorage.setItem('device_id', res.device_id)
    }
    ElMessage.success('恢复成功')
  } catch (error) {
    const message = error?.response?.data?.detail || '恢复失败'
    ElMessage.error(message)
  } finally {
    isAccountRecovering.value = false
  }
}

const handleLogout = () => {
  userStore.logout()
  ElMessage.success('已退出登录')
}

// --- 聊天树逻辑 ---
const openChatTree = async () => {
  if (!currentConversationId.value) return
  
  try {
    // 每次打开都重新获取一次，保证最新
    const messages = await getConversationMessages(currentConversationId.value)
    currentSessionMessages.value = messages
    
    // 转换数据为 ECharts 树形结构
    const highlightNodeId = sessionCache[currentConversationId.value]?.currentLeafId || (messages.length ? messages[messages.length - 1].node_id : null)
    if (currentConversationId.value && sessionCache[currentConversationId.value] && !sessionCache[currentConversationId.value].currentLeafId && highlightNodeId) {
      sessionCache[currentConversationId.value].currentLeafId = highlightNodeId
    }
    const treeData = buildEChartsTree(messages, highlightNodeId)
    showChatTree.value = true
    
    // 等待 DOM 渲染后初始化 ECharts
    nextTick(() => {
       initEChartsTree(treeData, highlightNodeId)
    })
    
  } catch (error) {
    ElMessage.error('加载聊天树失败')
    console.error(error)
  }
}

// 构建 ECharts 需要的树结构
function buildEChartsTree(items, highlightId) {
  const nodeMap = {}
  const rootNodes = []

  // 1. 初始化 Map
  items.forEach(item => {
    const raw = (item.content || '').replace(/\s+/g, ' ').trim()
    const label = raw.length > 18 ? raw.substring(0, 18) + '...' : raw
    const isHL = highlightId && item.node_id === highlightId
    nodeMap[item.node_id] = { 
      name: `${item.role === 'user' ? '用户' : 'AI'}\n${label}`,
      id: item.node_id, // 存储真实ID用于点击
      value: item.role, // 可以用来区分颜色
      children: [],
      original: item,
      // 样式配置
      itemStyle: {
        color: isHL ? '#fffbe6' : '#fff',
        borderColor: isHL ? '#f56c6c' : '#000',
        borderWidth: isHL ? 3 : 1.5,
      },
      label: {
        color: '#000',
        fontSize: 12,
        align: 'center',
        verticalAlign: 'middle',
        backgroundColor: isHL ? '#fde047' : 'transparent'
      },
      // 矩形节点
      symbol: 'rect',
      symbolSize: isHL ? [140, 50] : [120, 40]
    }
  })

  // 2. 组装树
  items.forEach(item => {
    if (!item.node_id) return
    const node = nodeMap[item.node_id]
    if (item.parent_node_id && nodeMap[item.parent_node_id]) {
      nodeMap[item.parent_node_id].children.push(node)
    } else {
      rootNodes.push(node)
    }
  })
  
  // ECharts Tree 只支持单根节点，如果有多个根（通常不会），需要创建一个虚拟根
  if (rootNodes.length === 1) return rootNodes[0]
  return {
    name: 'Root',
    children: rootNodes,
    symbolSize: 0,
    label: { show: false }
  }
}

const computeTreeLayoutStats = (root) => {
  const levelCounts = []
  let maxDepth = 0

  const walk = (node, depth) => {
    if (!node) return
    if (!levelCounts[depth]) levelCounts[depth] = 0
    levelCounts[depth] += 1
    maxDepth = Math.max(maxDepth, depth)
    for (const child of node.children || []) {
      walk(child, depth + 1)
    }
  }

  walk(root, 0)
  const maxBreadth = levelCounts.length ? Math.max(...levelCounts) : 1
  return { maxDepth, maxBreadth }
}

// 查找高亮节点及其深度
const findNodeAndDepth = (node, targetId, currentDepth = 0) => {
  if (!node) return null
  if (node.id === targetId) {
    return { node, depth: currentDepth }
  }
  if (node.children) {
    for (const child of node.children) {
      const result = findNodeAndDepth(child, targetId, currentDepth + 1)
      if (result) return result
    }
  }
  return null
}

// 初始化 ECharts
const initEChartsTree = (data, highlightNodeId) => {
  const chartDom = document.getElementById('echarts-tree-container')
  if (!chartDom) return
  
  // 销毁旧实例
  let myChart = echarts.getInstanceByDom(chartDom)
  if (myChart) myChart.dispose()
  
  myChart = echarts.init(chartDom)
  
  const { maxDepth, maxBreadth } = computeTreeLayoutStats(data)
  const minNodeGap = 56
  const minLayerPadding = 160
  const estimatedWidth = Math.max(chartDom.clientWidth || 800, maxBreadth * (140 + minNodeGap) + 320)
  const estimatedHeight = Math.max(chartDom.clientHeight || 600, (maxDepth + 1) * minLayerPadding + 240)

  // 默认位置：初始时隐藏，计算位置后再显示
  let seriesTop = 0
  let seriesLeft = 0
  let initialOpacity = highlightNodeId ? 0 : 1 // 如果需要高亮定位，先隐藏避免跳变

  const option = {
    tooltip: {
      trigger: 'item',
      triggerOn: 'mousemove',
      extraCssText: 'max-width: 400px; white-space: normal; word-break: break-all;', // 限制宽度并允许换行
      formatter: function (params) {
         // 悬浮显示完整内容
         const original = params.data.original
         if (original) {
             const role = original.role === 'user' ? '用户' : 'AI'
             let content = original.content
             // 限制为 200 字，超出显示省略号
             if (content.length > 200) {
                 content = content.substring(0, 200) + '...'
             }
             return `<strong>${role}</strong>:<br/>${content}`
         }
         return params.name
      }
    },
    series: [
      {
        type: 'tree',
        data: [data],
        top: seriesTop,
        left: seriesLeft,
        right: null,
        bottom: null,
        width: estimatedWidth,
        height: estimatedHeight,
        symbolSize: 7,
        orient: 'TB', // 从上到下 (Top-Bottom)
        layout: 'orthogonal',
        nodeGap: minNodeGap,
        layerPadding: minLayerPadding,
        roam: true,
        scaleLimit: { min: 0.2, max: 2.5 },
        
        // 连接线样式
        itemStyle: {
          borderWidth: 1.5,
          borderColor: '#000',
          opacity: initialOpacity
        },
        lineStyle: {
          color: '#000',
          width: 1.5,
          curveness: 0, // 直线 (类似手绘风格)
          opacity: initialOpacity
        },
        
        label: {
          position: 'inside', // 文字在框内
          verticalAlign: 'middle',
          align: 'center',
          fontSize: 12,
          lineHeight: 14,
          opacity: initialOpacity,
          formatter: function(params) {
              return params.name
          }
        },
        
        leaves: {
          label: {
            position: 'inside',
            verticalAlign: 'middle',
            align: 'center',
            opacity: initialOpacity
          }
        },
        
        expandAndCollapse: true,
        animationDuration: 0, // 初始渲染无动画，避免位置计算前的跳动
        animationDurationUpdate: 750,
        initialTreeDepth: -1 // 展开所有
      }
    ]
  }

  myChart.setOption(option)
  
  // 动态计算居中偏移
   if (highlightNodeId) {
      const adjustPosition = () => {
         // 防止重复触发
         myChart.off('finished', adjustPosition)
         
         const seriesModel = myChart.getModel().getSeriesByIndex(0)
         const tree = seriesModel.getData().tree
         let targetNode = null
         
         // 深度优先遍历树查找节点
         const traverse = (node) => {
             if (!node) return
             // 检查节点数据中的 id
             const model = node.getModel()
             const rawData = model ? model.option : null
             if (rawData && rawData.id === highlightNodeId) {
                 targetNode = node
                 return
             }
             
             if (node.children && node.children.length) {
                 for (const child of node.children) {
                     traverse(child)
                     if (targetNode) return
                 }
             }
         }
         
         if (tree && tree.root) {
             traverse(tree.root)
         }
         
         if (targetNode) {
            // 获取节点相对于容器左上角的坐标 {x, y}
            const layout = targetNode.getLayout()
            
            if (layout) {
                const containerWidth = chartDom.clientWidth
                const containerHeight = chartDom.clientHeight
                
                // 计算需要的偏移量
                const newLeft = containerWidth / 2 - layout.x
                const newTop = containerHeight / 2 - layout.y
                
                // 更新图表位置并显示
                myChart.setOption({
                    series: [{
                        left: newLeft,
                        top: newTop,
                        animationDuration: 550, // 恢复动画
                        itemStyle: { opacity: 1 },
                        lineStyle: { opacity: 1 },
                        label: { opacity: 1 },
                        leaves: { label: { opacity: 1 } }
                    }]
                })
            }
         } else {
             // 没找到节点，直接显示
             myChart.setOption({
                series: [{
                    animationDuration: 550,
                    itemStyle: { opacity: 1 },
                    lineStyle: { opacity: 1 },
                    label: { opacity: 1 },
                    leaves: { label: { opacity: 1 } }
                }]
             })
         }
      }
      
      myChart.on('finished', adjustPosition)
      
      // 兜底：如果 300ms 后还没触发 finished，强制显示
      // 避免因为某种原因事件未触发导致树图一直不可见
      setTimeout(() => {
          const currentOpt = myChart.getOption()
          // 简单检查一下 opacity，或者直接覆盖
          // 这里不做复杂判断，直接触发显示，反正 setOption 是合并模式
          myChart.setOption({
            series: [{
                itemStyle: { opacity: 1 },
                lineStyle: { opacity: 1 },
                label: { opacity: 1 },
                leaves: { label: { opacity: 1 } }
            }]
          })
      }, 300)
   }
  
  // 点击事件
  myChart.on('click', function (params) {
    if (params.data.id) {
       handleTreeNodeClick({ id: params.data.id })
    }
  })
  
  // 监听窗口大小改变
  window.addEventListener('resize', function() {
    myChart.resize()
  })
}

// 树节点点击事件
const handleTreeNodeClick = async (data) => {
  console.log('点击节点:', data)
  
  try {
    // 1. 设置当前点击的节点为新的父节点
    // 这样下次对话就会挂在这个节点下面
    // currentLeafId.value = data.id // 改为通过 sessionCache 设置
    
    // 2. 调用后端接口获取【从根节点到当前点击节点】的完整路径
    // 注意：这里不再自动向后延伸，而是准确地停在用户点击的那个节点
    const pathMessages = await getNodePath(data.id)
    
    // 3. 更新界面
    // 关键修复：直接更新 sessionCache 中的消息列表，而不是只更新 chatHistory (它现在是 computed)
    if (currentConversationId.value && sessionCache[currentConversationId.value]) {
        sessionCache[currentConversationId.value].currentLeafId = data.id // 更新叶子节点
        
        sessionCache[currentConversationId.value].messages = pathMessages.map(msg => {
          const isAI = ['assistant', 'ai', 'model'].includes(msg.role)
          return {
            role: isAI ? 'ai' : 'user',
            content: msg.content,
            html: isAI ? renderMarkdown(msg.content) : '',
            attachments: msg.attachments || [],
            loading: false,
            done: true
          }
        })
    }
    
    scrollToBottom()
    
    // 4. 关闭弹窗
    showChatTree.value = false
    ElMessage.success('已切换到选中节点')
    
  } catch (error) {
    console.error(error)
    ElMessage.error('切换分支失败')
  }
}

// 辅助：查找指定节点所在分支的最远叶子节点 (暂时不用，保留备用)
const findLeafNodeInBranch = (nodeId) => {
  if (!currentSessionMessages.value.length) return nodeId
  
  // 建立 parent_id -> [children] 的映射
  const childrenMap = {}
  currentSessionMessages.value.forEach(msg => {
    if (msg.parent_node_id) {
      if (!childrenMap[msg.parent_node_id]) {
        childrenMap[msg.parent_node_id] = []
      }
      childrenMap[msg.parent_node_id].push(msg)
    }
  })

  // 从当前节点开始向下找
  // 策略：如果有多个子节点（分叉），默认选择最新的那一个（按时间/ID排序）
  // 也可以根据需求改为选择“第一条”或者其他逻辑
  let currId = nodeId
  while (true) {
    const children = childrenMap[currId]
    if (!children || children.length === 0) {
      // 没有子节点了，说明 currId 就是叶子
      break
    }
    
    // 找到最新的子节点 (假设 id 生成是时序的，或者依赖 created_at)
    // 这里简单地取最后一个子节点（通常是最后添加的）
    // 如果 children 需要排序，请先 sort
    // 假设后端返回的数据已经是按时间排序的，那最后一个就是最新的
    const latestChild = children[children.length - 1]
    currId = latestChild.node_id
  }
  
  return currId
}

// 辅助：从指定节点回溯到根节点，构建聊天记录
const restoreChatPath = (leafNodeId) => {
  if (!currentSessionMessages.value.length) return

  // 建立 id -> msg 映射
  const msgMap = {}
  currentSessionMessages.value.forEach(msg => {
    msgMap[msg.node_id] = msg
  })
  
  const pathMessages = []
  let currId = leafNodeId
  
  while (currId && msgMap[currId]) {
    const msg = msgMap[currId]
    pathMessages.unshift(msg) // 插入到开头
    currId = msg.parent_node_id // 向上找
  }
  
  // 更新界面
  chatHistory.value = pathMessages.map(msg => ({
    role: msg.role === 'assistant' ? 'ai' : 'user',
    content: msg.content,
    html: msg.role === 'assistant' ? renderMarkdown(msg.content) : '',
    loading: false
  }))
  
  scrollToBottom()
}

const handleCopy = async (text) => {
  try {
    await navigator.clipboard.writeText(text)
    ElMessage.success('复制成功')
  } catch (err) {
    ElMessage.error('复制失败')
  }
}

const handleMarkdownClick = async (e) => {
  const btn = e?.target?.closest?.('.copy-code-btn')
  if (!btn) return
  const container = btn.closest('.code-block')
  const codeEl = container?.querySelector?.('pre code')
  const text = (codeEl?.textContent || '').trimEnd()
  if (!text) return
  await handleCopy(text)
  const prev = btn.textContent
  btn.textContent = '已复制'
  window.setTimeout(() => {
    btn.textContent = prev
  }, 1200)
}

const getParentKey = (parentId) => parentId || 'root'

const beginSending = (sessionState, parentKey) => {
  if (!sessionState.sendingByParent) sessionState.sendingByParent = {}
  sessionState.sendingByParent[parentKey] = (sessionState.sendingByParent[parentKey] || 0) + 1
  sessionState.isSending = true
}

const endSending = (sessionState, parentKey) => {
  if (!sessionState?.sendingByParent) {
    sessionState.isSending = false
    return
  }
  const nextVal = (sessionState.sendingByParent[parentKey] || 0) - 1
  if (nextVal > 0) sessionState.sendingByParent[parentKey] = nextVal
  else delete sessionState.sendingByParent[parentKey]
  sessionState.isSending = Object.keys(sessionState.sendingByParent).length > 0
}

// ★★★ 发送消息核心逻辑 (改为流式调用) ★★★
const sendMessage = async () => {
  // 发送消息前确保设置弹窗关闭
  showConversationInstructions.value = false
  
  if (isOpenClawMode.value) {
    if (currentAttachments.value.length > 0) {
      ElMessage.warning('OpenClaw 模式暂不支持附件')
      currentAttachments.value = []
    }
    await sendMessageToOpenClaw()
    return
  }

  const text = inputMessage.value.trim()
  const attachmentsSnapshot = [...currentAttachments.value]
  if (!text && attachmentsSnapshot.length === 0) return

  // --- 1. 确定当前操作的会话上下文 ---
  // 如果是新会话，操作 tempNewSessionState
  // 如果是旧会话，操作 sessionCache[currentConversationId.value]
  const isNewSession = !currentConversationId.value
  let activeSessionState = null
  
  if (isNewSession) {
    activeSessionState = tempNewSessionState
  } else {
    // 确保缓存存在 (理论上 switchSession 已经保证了，但做个兜底)
    if (!sessionCache[currentConversationId.value]) {
       sessionCache[currentConversationId.value] = { messages: [], isSending: false, sendingByParent: {}, currentLeafId: null }
    }
    activeSessionState = sessionCache[currentConversationId.value]
  }

  const parentKeyAtSend = getParentKey(activeSessionState.currentLeafId)
  if (isNewSession) {
    if (activeSessionState.isSending) return
  } else {
    if (activeSessionState.sendingByParent?.[parentKeyAtSend]) return
  }

  beginSending(activeSessionState, parentKeyAtSend)

  // --- 2. 用户消息上屏 ---
  activeSessionState.messages.push({ role: 'user', content: text, attachments: attachmentsSnapshot })
  inputMessage.value = ''
  currentAttachments.value = []
  
  scrollToBottom()

  // --- 3. AI Loading 占位 ---
  const aiMessage = reactive({
    role: 'ai', content: '', html: '', loading: true, done: false 
  })
  activeSessionState.messages.push(aiMessage)
  scrollToBottom()

  // --- 3. 构造请求体 ---
  const payload = {
    user_id: userStore.userInfo?.id,
    message: text,
    model_name: currentModel.value,
    enable_search: enableSearch.value,
    enable_rag: selectedCount.value > 0,
    file_ids: selectedFileIds.value,
    conversation_id: currentConversationId.value,
    parent_id: activeSessionState.currentLeafId, // 使用当前会话的状态
    files: attachmentsSnapshot // ★ 传递即时聊天文件
  }

  // --- 5. 发起流式请求 ---
  let fullText = "" 
  
  // 保存发起请求时的 Session ID，用于闭包中判断是否还是当前视图
  const requestSessionId = currentConversationId.value

  let ended = false
  const endOnce = () => {
    if (ended) return
    ended = true
    const targetState = isNewSession
      ? (currentConversationId.value ? sessionCache[currentConversationId.value] : tempNewSessionState)
      : activeSessionState
    endSending(targetState, parentKeyAtSend)
  }

  await chatStream(
    payload,
    // onMessage: 收到片段
    (chunk) => {
      // 智能滚动逻辑：只有当【当前视图】就是【发起请求的会话】时，才处理滚动
      // 否则只更新数据，不滚动
      const isViewingRequestSession = currentConversationId.value === requestSessionId
      
      let shouldScroll = false
      if (isViewingRequestSession) {
          const el = chatContainerRef.value
          if (el) {
              const threshold = 100 
              const distanceToBottom = el.scrollHeight - el.scrollTop - el.clientHeight
              shouldScroll = distanceToBottom < threshold
          }
      }

      aiMessage.loading = false
      fullText += chunk
      aiMessage.content = fullText
      aiMessage.html = renderMarkdown(fullText)
      
      if (shouldScroll) {
          scrollToBottom()
      }
    },
    // onDone: 完成
    () => {
      aiMessage.loading = false
      aiMessage.done = true 
      endOnce()
      
      // 如果是新会话，流结束后刷新列表以显示新标题
      if (isNewSession) {
         fetchSessionList()
      }
    },
    // onError: 报错
    (err) => {
      aiMessage.loading = false
      aiMessage.done = true
      endOnce()

      aiMessage.html += `<br><span style="color:red">[网络错误: ${err.message}]</span>`
    },
    // onMeta: 收到元数据 (session_id, user_node_id, ai_node_id)
    (meta) => {
      // --- 处理新会话转正逻辑 ---
      if (meta.session_id) {
        if (isNewSession && !currentConversationId.value) {
           // 1. 设置 ID
           currentConversationId.value = meta.session_id
           
           // 2. 初始化缓存
           sessionCache[meta.session_id] = {
             messages: [...tempNewSessionState.messages], // 迁移临时消息
             isSending: true,
             sendingByParent: { [parentKeyAtSend]: 1 },
             currentLeafId: null,
             scrollTop: 0
           }

           tempNewSessionState.messages = []
           tempNewSessionState.currentLeafId = null
           tempNewSessionState.isSending = false
           tempNewSessionState.sendingByParent = {}
           
           // 3. 将 activeSessionState 指向新缓存，确保后续闭包更新正确对象
           // 注意：这一步其实不需要，因为 aiMessage 是 reactive 对象，引用没变。
           // 我们只需要更新 activeSessionState.isSending 这种基础类型引用的地方。
           // 但由于上面的回调闭包里引用的是 aiMessage 对象本身，所以数据更新没问题。
           // 主要是 isSending 的状态需要同步。
           
           // 4. 刷新列表
           fetchSessionList()
        }
      }
      
      // 更新叶子节点
      // 注意：这里需要更新的是【发起请求的那个会话】的状态，而不是 currentConversationId
      // 但对于新会话，上面已经切换了 currentConversationId，所以可以直接用
      const targetSessionState = isNewSession ? sessionCache[currentConversationId.value] : activeSessionState
      
      if (targetSessionState) {
          if (meta.user_node_id) {
             targetSessionState.currentLeafId = meta.user_node_id
          }
          if (meta.ai_node_id) {
             targetSessionState.currentLeafId = meta.ai_node_id
             
             // ★ 核心修复：收到 ai_node_id 意味着 AI 内容回复完毕 ★
             // 此时即使流还没断（因为后台还在生成标题），我们也可以认为本次对话交互已经结束
             // 提前结束 Loading 状态，恢复发送按钮
             aiMessage.loading = false
             aiMessage.done = true 
             endOnce()

             if (isNewSession) fetchSessionList()
          }
          if (meta.user_attachments_saved && Array.isArray(meta.user_attachments_saved)) {
             const msgs = targetSessionState.messages || []
             for (let i = msgs.length - 1; i >= 0; i--) {
               if (msgs[i].role === 'user') {
                 const localAtts = Array.isArray(msgs[i].attachments) ? msgs[i].attachments : []
                 const saved = meta.user_attachments_saved
                 msgs[i].attachments = saved.map(s => {
                   const matched = localAtts.find(a => (a.name || a.filename) === s.filename)
                   return { ...matched, ...s, mime: matched?.mime || s.mime }
                 })
                 break
               }
             }
          }
      }
      
      // ★ 实时更新标题 ★
      if (meta.new_title) {
         // 更新历史列表中的标题
         const session = historyList.value.find(s => s.id === meta.session_id || s.id === currentConversationId.value)
         if (session) {
            session.title = meta.new_title
         }
      }
    }
  )
}

// --- 文件相关方法 ---
const fetchFileList = async () => {
  try { userFiles.value = await getFiles() } catch (e) { }
}
const triggerFileInput = () => fileInput.value.click()
const handleFileChange = async (e) => {
  const files = e.target.files
  if (!files || !files.length) return
  const formData = new FormData()
  formData.append('file', files[0])
  isUploading.value = true
  try {
    await uploadFile(formData)
    ElMessage.success('上传成功')
    await fetchFileList()
  } catch (e) { console.error(e) } finally {
    isUploading.value = false
    e.target.value = ''
  }
}

const handleDeleteKnowledgeFile = async (fileId) => {
  const ok = window.confirm('确定删除该知识库文件吗？')
  if (!ok) return
  try {
    await deleteFile(fileId)
    selectedFileIds.value = selectedFileIds.value.filter(id => id !== fileId)
    await fetchFileList()
    ElMessage.success('删除成功')
  } catch (e) {
    ElMessage.error('删除失败')
  }
}

const handleClearKnowledgeBase = async () => {
  const ok = window.confirm('确定清空本地知识库吗？该操作会移除你上传的所有知识库文件索引。')
  if (!ok) return
  const ok2 = window.confirm('再次确认：真的要清空吗？')
  if (!ok2) return
  try {
    await clearKnowledgeBase()
    selectedFileIds.value = []
    await fetchFileList()
    ElMessage.success('知识库已清空')
  } catch (e) {
    ElMessage.error('清空失败')
  }
}

// ★★★ 新增：即时聊天文件处理逻辑 ★★★
const triggerChatFileInput = () => chatFileInput.value.click()

const handleChatFileSelect = async (e) => {
  const files = Array.from(e.target.files)
  if (!files.length) return
  
  for (const file of files) {
    await processAttachment(file)
  }
  e.target.value = '' // 重置 input
}

const handlePaste = async (e) => {
  const items = e.clipboardData.items
  for (const item of items) {
    if (item.kind === 'file') {
      const file = item.getAsFile()
      if (file) await processAttachment(file)
    }
  }
}

const processAttachment = (file) => {
  return new Promise((resolve) => {
    const reader = new FileReader()
    reader.onload = (e) => {
      const base64Url = e.target.result
      // 提取纯 Base64 (去除 data:image/xxx;base64, 前缀)
      const base64Data = base64Url.split(',')[1]
      
      let type = 'file'
      if (file.type.startsWith('image/')) type = 'image'
      if (file.type.startsWith('video/')) type = 'video'
      
      currentAttachments.value.push({
        name: file.name,
        type: type,
        mime: file.type,
        base64: base64Data,
        size: file.size
      })
      ElMessage.success(`已添加附件：${file.name}`)
      if (file.size > MAX_DIRECT_READ_SIZE_BYTES) {
        ElMessage.warning('附件超过 5MB：后端将自动使用检索模式提取相关片段')
      }
      resolve()
    }
    reader.readAsDataURL(file)
  })
}

const removeAttachment = (index) => {
  currentAttachments.value.splice(index, 1)
}

const formatSize = (bytes) => {
  if (bytes === 0) return '0 B'
  const k = 1024
  const sizes = ['B', 'KB', 'MB', 'GB']
  const i = Math.floor(Math.log(bytes) / Math.log(k))
  return parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + ' ' + sizes[i]
}

const signedUrlTasks = new Map()

const isPdfAttachment = (att) => {
  const mime = (att?.mime || '').toLowerCase()
  const name = (att?.filename || att?.name || '').toLowerCase()
  return mime === 'application/pdf' || name.endsWith('.pdf')
}

const ensureSignedUrl = async (att) => {
  if (att.url) return att.url
  if (!att.id) return null
  const existingTask = signedUrlTasks.get(att.id)
  if (existingTask) return await existingTask
  try {
    const task = getAttachmentSignedUrl(att.id).then((res) => {
      att.url = res.url
      att.expires_at = res.expires_at
      return att.url
    })
    signedUrlTasks.set(att.id, task)
    return await task
  } catch (e) {
    ElMessage.error('获取附件链接失败')
    return null
  } finally {
    signedUrlTasks.delete(att.id)
  }
}

const openAttachment = async (att) => {
  const url = att.url || (att.base64 ? `data:${att.mime || 'application/octet-stream'};base64,${att.base64}` : null) || await ensureSignedUrl(att)
  if (!url) return
  window.open(url, '_blank', 'noopener')
}

const getAttachmentSrc = (att) => {
  if (att.url) return att.url
  if (att.base64) return `data:${att.mime || 'application/octet-stream'};base64,${att.base64}`
  return ''
}

watch(viewMessages, async (messages) => {
  try {
    const tasks = []
    for (const msg of messages || []) {
      for (const att of msg?.attachments || []) {
        if (!att) continue
        if (att.url || att.base64) continue
        if (!att.id) continue
        const isImage = (att.mime || '').startsWith('image/') || att.type === 'image'
        const isVideo = (att.mime || '').startsWith('video/') || att.type === 'video'
        if (!isImage && !isVideo) continue
        tasks.push(ensureSignedUrl(att))
      }
    }
    if (tasks.length > 0) {
      await Promise.allSettled(tasks)
    }
  } catch (e) {
    console.error('预拉取附件链接失败:', e)
  }
}, { deep: true, immediate: true })

// 辅助方法
const scrollToBottom = () => {
  nextTick(() => {
    if (chatContainerRef.value) chatContainerRef.value.scrollTop = chatContainerRef.value.scrollHeight
  })
}
const clickCard = (text) => {
  inputMessage.value = text
  sendMessage()
}
const handleOpenClawConfigCommand = (command) => {
  if (command.type === 'select') {
    selectOpenClawConfig(command.config)
  } else if (command.type === 'manage') {
    showSettings.value = true
    settingsActiveTab.value = 'openclaw'
  }
}

</script>

<template>
  <div class="gemini-layout">
    <aside class="sidebar" :class="{ 'collapsed': isSidebarCollapsed }">
      <div class="sidebar-header">
        <el-button link @click="toggleSidebar" class="menu-btn">
          <el-icon :size="20">
            <Menu />
          </el-icon>
        </el-button>
        <transition name="fade">
          <div v-if="!isSidebarCollapsed" class="new-chat-pill" @click="startNewChat">
            <el-icon>
              <Plus />
            </el-icon>
            <span>New Chat</span>
          </div>
        </transition>
      </div>

      <div class="history-container" v-if="!isSidebarCollapsed">
        <div class="history-group">
          <span class="group-label">Recent</span>

          <div v-if="historyList.length === 0" class="empty-history">
            暂无历史会话
          </div>

          <div v-for="item in historyList" :key="item.id" class="history-item"
            :class="{ 'active': currentConversationId === item.id }" @click="switchSession(item)">
            <!-- 状态图标：如果正在发送，显示 Loading；否则显示默认气泡 -->
            <el-icon class="msg-icon" v-if="sessionCache[item.id]?.isSending">
              <Loading class="is-loading" />
            </el-icon>
            <el-icon class="msg-icon" v-else>
              <ChatDotRound />
            </el-icon>
            
            <span class="text-truncate" :title="item.title">
              {{ item.title || '新对话' }}
            </span>
            <el-icon class="delete-icon" @click="(e) => removeSession(e, item.id)">
              <Delete />
            </el-icon>
          </div>
        </div>
      </div>

      <div class="sidebar-footer" v-if="!isSidebarCollapsed">
        <div class="footer-item" @click="showSettings = true" style="cursor: pointer;">
          <el-icon>
            <Setting />
          </el-icon> Settings
        </div>
      </div>
    </aside>

    <main class="main-area">
      <!-- 设置页面 (嵌入式) -->
      <div v-if="showSettings" class="settings-embedded-container">
        <div class="settings-sidebar">
          <h2 class="settings-title">Settings</h2>
          <div class="settings-menu">
            <div class="menu-item" :class="{ active: settingsActiveTab === 'models' }" @click="settingsActiveTab = 'models'">
              模型管理
            </div>
            <div class="menu-item" :class="{ active: settingsActiveTab === 'instructions' }" @click="settingsActiveTab = 'instructions'">
              AI 指令
            </div>
          <div class="menu-item" :class="{ active: settingsActiveTab === 'openclaw' }" @click="settingsActiveTab = 'openclaw'">
              OpenClaw
            </div>
            <div class="menu-item" :class="{ active: settingsActiveTab === 'account' }" @click="settingsActiveTab = 'account'">
              账号
            </div>
          </div>
        </div>
        <div class="settings-content">
          <!-- 模型管理 -->
          <div v-if="settingsActiveTab === 'models'" class="settings-panel">
            <h3>添加新模型</h3>
            <div class="add-model-form">
              <el-input v-model="newModelForm.model_name" placeholder="模型ID (如 gpt-4)" style="margin-bottom: 10px" />
              <el-input v-model="newModelForm.display_name" placeholder="显示名称 (如 GPT-4)" style="margin-bottom: 10px" />
              <el-button type="primary" @click="handleAddModel" style="width: 100%">添加</el-button>
            </div>

            <h3 style="margin-top: 20px">可用模型列表</h3>
            <el-table :data="availableModels" style="width: 100%" max-height="400">
              <el-table-column prop="display_name" label="名称" />
              <el-table-column prop="model_name" label="ID" />
              <el-table-column label="操作" width="80">
                <template #default="scope">
                  <el-button 
                    v-if="scope.row.is_custom" 
                    link 
                    type="danger" 
                    @click="handleDeleteModel(scope.row)"
                  >
                    删除
                  </el-button>
                  <span v-else style="color: #999; font-size: 12px">默认</span>
                </template>
              </el-table-column>
            </el-table>
          </div>

          <!-- AI 指令 -->
          <div v-if="settingsActiveTab === 'instructions'" class="settings-panel">
            <h3>添加指令</h3>
            <el-input
              v-model="aiInstructionInput"
              type="textarea"
              :rows="4"
              placeholder="例如：请用简洁中文回答；先给结论再解释；代码请给可运行示例"
              style="margin-bottom: 10px"
            />
            <el-button
              type="primary"
              :loading="isInstructionSubmitting"
              @click="handleAddInstruction"
              style="width: 100%"
            >
              添加
            </el-button>

            <h3 style="margin-top: 20px">指令列表</h3>
            <el-table :data="aiInstructions" style="width: 100%" max-height="400" v-loading="isInstructionsLoading">
              <el-table-column prop="content" label="内容" />
              <el-table-column label="操作" width="170">
                <template #default="scope">
                  <el-button link size="small" @click="moveInstructionUp(scope.row)" :disabled="scope.$index === 0">
                    上移
                  </el-button>
                  <el-button
                    link
                    size="small"
                    @click="moveInstructionDown(scope.row)"
                    :disabled="scope.$index === aiInstructions.length - 1"
                  >
                    下移
                  </el-button>
                  <el-button link type="danger" size="small" @click="handleDeleteInstruction(scope.row)">
                    删除
                  </el-button>
                </template>
              </el-table-column>
            </el-table>
          </div>

          <!-- OpenClaw 管理 -->
          <div v-if="settingsActiveTab === 'openclaw'" class="settings-panel">
            <OpenClawSettings />
          </div>

          <div v-if="settingsActiveTab === 'account'" class="settings-panel">
            <h3>账号管理</h3>
            <el-form label-position="top" label-width="100px" style="max-width: 460px;">
              <el-form-item label="当前账号">
                <el-input :model-value="userStore.userInfo?.username || '匿名用户'" disabled />
              </el-form-item>
            </el-form>

            <h3 style="margin-top: 20px">升级账号</h3>
            <el-form label-position="top" label-width="100px" style="max-width: 460px;">
              <el-form-item label="用户名">
                <el-input v-model="accountUpgradeForm.username" placeholder="输入用户名" />
              </el-form-item>
              <el-form-item label="密码（可选）">
                <el-input v-model="accountUpgradeForm.password" placeholder="设置密码（可选）" type="password" show-password />
              </el-form-item>
              <el-button type="primary" :loading="isAccountUpgrading" @click="handleUpgradeAccount" style="width: 100%">
                升级账号
              </el-button>
            </el-form>

            <h3 style="margin-top: 20px">恢复已有账号</h3>
            <el-form label-position="top" label-width="100px" style="max-width: 460px;">
              <el-form-item label="用户名">
                <el-input v-model="accountRecoveryForm.username" placeholder="输入用户名" />
              </el-form-item>
              <el-form-item label="密码">
                <el-input v-model="accountRecoveryForm.password" placeholder="输入密码" type="password" show-password />
              </el-form-item>
              <el-button type="primary" :loading="isAccountRecovering" @click="handleRecoverAccount" style="width: 100%">
                恢复账号
              </el-button>
            </el-form>
          </div>
        </div>
      </div>

      <!-- 聊天主界面 -->
      <div v-else class="chat-container-wrapper">
        <header class="top-bar">
          <template v-if="!isOpenClawMode">
            <el-dropdown trigger="click" @command="(cmd) => currentModel = cmd">
              <span class="model-name cursor-pointer">
                {{ currentModel }}
                <el-icon class="el-icon--right"><ArrowDown /></el-icon>
              </span>
              <template #dropdown>
                <el-dropdown-menu>
                  <el-dropdown-item v-for="model in availableModels" :key="model.model_name" :command="model.model_name">
                    {{ model.display_name }}
                  </el-dropdown-item>
                </el-dropdown-menu>
              </template>
            </el-dropdown>
          </template>

          <template v-else>
            <el-dropdown trigger="click" @command="handleOpenClawConfigCommand" class="openclaw-config-dropdown">
              <span class="model-name cursor-pointer">
                {{ viewTitle }}
                <el-icon class="el-icon--right"><ArrowDown /></el-icon>
              </span>
              <template #dropdown>
                <el-dropdown-menu>
                  <el-dropdown-item 
                    v-for="config in openClawConfigs" 
                    :key="config.id" 
                    :command="{ type: 'select', config: config }"
                    :class="{ 'is-active': currentOpenClawConfig?.id === config.id }"
                  >
                    <div class="config-dropdown-item">
                      <div class="config-name">{{ config.display_name }}</div>
                      <div class="config-url">{{ config.gateway_url }}</div>
                    </div>
                  </el-dropdown-item>
                  <el-dropdown-item divided :command="{ type: 'manage' }">
                    <el-icon><Setting /></el-icon> 管理配置
                  </el-dropdown-item>
                </el-dropdown-menu>
              </template>
            </el-dropdown>
          </template>
        
          <!-- 新增：聊天树按钮 -->
          <el-button v-if="currentConversationId && !isOpenClawMode" circle @click="openChatTree" title="查看对话树" style="margin-right: 12px; margin-left: auto;">
             <el-icon><Share /></el-icon>
          </el-button>

          <el-button v-if="!isOpenClawMode" circle @click="showConversationInstructions = true" title="会话指令" style="margin-right: 12px;">
            <el-icon><Setting /></el-icon>
          </el-button>

          <!-- OpenClaw Button -->
          <el-button circle @click="enterOpenClawMode" title="OpenClaw" style="margin-right: 12px;">
             <el-icon><Service /></el-icon>
          </el-button>

          <el-button v-if="isOpenClawMode" @click="exitOpenClawMode" style="margin-right: 12px;">
            退出
          </el-button>

          <!-- 用户头像下拉菜单 -->
          <el-dropdown trigger="click" @command="(cmd) => cmd === 'logout' && handleLogout()">
            <el-avatar :size="32" class="user-avatar cursor-pointer" style="margin-left: 12px">U</el-avatar>
            <template #dropdown>
              <el-dropdown-menu>
                <el-dropdown-item command="logout" style="color: #f56c6c;">
                  <el-icon><SwitchButton /></el-icon> 注销
                </el-dropdown-item>
              </el-dropdown-menu>
            </template>
          </el-dropdown>
        </header>

      <div class="content-scroll-area" ref="chatContainerRef">
        <div v-if="!isChattingView" class="welcome-container">
          <div class="greeting">
            <h1 class="gradient-text">Hello, Developer</h1>
            <h1 class="sub-text">How can I help you today?</h1>
          </div>
        </div>

        <div v-else class="chat-list">
          <div v-for="(msg, index) in viewMessages" :key="index" class="message" :class="msg.role">
            <div class="avatar-col">
              <!-- 用户头像: 紫色背景 + 白色字母 -->
              <div v-if="msg.role === 'user'" class="avatar-circle user-theme">U</div>
              <!-- AI头像: 恢复带有动画的 AI Logo -->
              <div v-else class="ai-logo">✨</div>
            </div>
            <div class="text-col">
              <div v-if="msg.role === 'ai'" class="markdown-body">
                <div v-if="msg.loading && !msg.html" class="typing-indicator"><span></span><span></span><span></span></div>
                <div v-else>
                   <div v-html="msg.html" @click="handleMarkdownClick"></div>
                   <!-- 复制按钮 -->
                   <div v-if="msg.done" class="message-actions">
                     <el-button type="primary" plain size="small" @click="handleCopy(msg.content)">
                       <el-icon style="margin-right: 4px"><CopyDocument /></el-icon> 
                     </el-button>
                   </div>
                </div>
              </div>
              <div v-else class="user-text">
                <div v-if="msg.content">{{ msg.content }}</div>
                <div v-if="msg.attachments && msg.attachments.length > 0" class="message-attachments">
                  <div v-for="att in msg.attachments" :key="att.id || att.storage_key || att.name" class="att-item" @click="openAttachment(att)">
                    <img
                      v-if="(att.mime || '').startsWith('image/') || att.type === 'image'"
                      class="att-thumb"
                      :src="getAttachmentSrc(att)"
                    />
                    <video
                      v-else-if="(att.mime || '').startsWith('video/') || att.type === 'video'"
                      class="att-thumb"
                      :src="getAttachmentSrc(att)"
                      muted
                      playsinline
                      preload="metadata"
                    />
                    <div v-else class="att-icon">
                      <el-icon><Document /></el-icon>
                    </div>
                    <div class="att-meta">
                      <div class="att-name" :title="att.filename || att.name">{{ att.filename || att.name }}</div>
                      <div class="att-sub">{{ (att.mime || '').toLowerCase() || (isPdfAttachment(att) ? 'application/pdf' : 'file') }}</div>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>

      <div class="input-container-wrapper">
        <div class="input-box">
          <!-- 0. 附件预览区 (新增) -->
          <div v-if="currentAttachments.length > 0" class="attachment-preview-area">
            <div v-for="(file, index) in currentAttachments" :key="index" class="attachment-card">
              <!-- 图片预览 -->
              <div v-if="file.type === 'image'" class="preview-thumb" :style="{ backgroundImage: `url(${file.base64})` }"></div>
              <!-- 文件预览 -->
              <div v-else class="preview-file">
                <el-icon><Document /></el-icon>
              </div>
              
              <div class="file-meta">
                <span class="fname" :title="file.name">{{ file.name }}</span>
                <span class="fsize">{{ formatSize(file.size) }}</span>
              </div>
              
              <div class="remove-btn" @click="removeAttachment(index)">
                <el-icon><Close /></el-icon>
              </div>
            </div>
          </div>

          <!-- 1. 输入区域 (顶部) -->
          <el-input 
            v-model="inputMessage" 
            type="textarea" 
            :autosize="{ minRows: 1, maxRows: 8 }"
            :placeholder="isOpenClawMode ? '问问 OpenClaw' : (selectedCount > 0 ? `已引用 ${selectedCount} 个文件...` : '问问 xunji (支持粘贴图片/文件)')"
            class="gemini-input" 
            resize="none" 
            @keydown.enter.exact.prevent="sendMessage"
            @paste="handlePaste"
          />

          <!-- 2. 工具栏 (底部) -->
          <div class="input-toolbar">
            <!-- 左侧工具: 添加附件、知识库 -->
            <div class="toolbar-left">
              <!-- 知识库引用 (保持不变) -->
              <el-popover placement="top-start" :width="300" trigger="click" popper-class="file-selector-popover">
                <template #reference>
                  <el-button circle link class="action-btn" :class="{ 'has-files': selectedCount > 0 }" title="引用知识库">
                    <el-icon :size="20"><Collection /></el-icon>
                  </el-button>
                </template>
                <!-- ... Popover 内容 ... -->
                <div class="file-list-header">
                  <span>引用知识库</span>
                  <span class="count" v-if="selectedCount > 0">{{ selectedCount }} 选中</span>
                </div>
                <el-scrollbar max-height="200px">
                  <div v-if="userFiles.length === 0" class="empty-files">暂无文件，请上传</div>
                  <el-checkbox-group v-model="selectedFileIds" class="file-checkbox-group">
                    <div v-for="file in userFiles" :key="file.id" class="file-item">
                      <el-checkbox :label="file.id">
                        <div class="file-info">
                          <el-icon><Document /></el-icon>
                          <span class="fname" :title="file.filename">{{ file.filename }}</span>
                        </div>
                      </el-checkbox>
                      <el-button circle link class="action-btn" title="删除" @click.stop="handleDeleteKnowledgeFile(file.id)">
                        <el-icon :size="16"><Delete /></el-icon>
                      </el-button>
                    </div>
                  </el-checkbox-group>
                </el-scrollbar>
                <div style="display:flex;justify-content:space-between;align-items:center;margin-top:8px;">
                  <span style="font-size:12px;color:#888;">管理知识库</span>
                  <el-button type="danger" link size="small" @click="handleClearKnowledgeBase">清空知识库</el-button>
                </div>
              </el-popover>

              <!-- 上传到知识库 (保持不变，或根据需求移动位置) -->
              <input type="file" ref="fileInput" style="display: none" accept=".pdf,.txt,.md,.docx,.py,.java" @change="handleFileChange">
              <el-tooltip content="上传到知识库" placement="top" effect="dark">
                <el-button circle link class="action-btn" @click="triggerFileInput" :loading="isUploading">
                  <el-icon :size="20" v-if="!isUploading"><UploadFilled /></el-icon>
                </el-button>
              </el-tooltip>
              
              <!-- ★ 新增：添加到当前对话 (本地文件/多模态) ★ -->
              <input type="file" ref="chatFileInput" style="display: none" multiple @change="handleChatFileSelect">
              <el-tooltip content="添加到对话 (图片/文档)" placement="top" effect="dark">
                <el-button circle link class="action-btn" @click="triggerChatFileInput">
                  <el-icon :size="20"><Paperclip /></el-icon>
                </el-button>
              </el-tooltip>
            </div>

            <!-- 右侧工具: 搜索、发送 -->
            <div class="toolbar-right">
              <el-tooltip effect="dark" :content="enableSearch ? '联网搜索: 开' : '联网搜索: 关'" placement="top">
                <el-button circle link class="search-btn" :class="{ 'is-active': enableSearch }" :disabled="isOpenClawMode" @click="enableSearch = !enableSearch">
                  <el-icon :size="18"><Connection /></el-icon>
                </el-button>
              </el-tooltip>
              
              <el-button
                circle
                :type="inputMessage || currentAttachments.length > 0 ? 'primary' : ''"
                :disabled="isSendingView || (!inputMessage && currentAttachments.length === 0)"
                @click="sendMessage"
                class="send-btn"
              >
                <el-icon :size="18">
                  <Loading v-if="isSendingView" class="is-loading" />
                  <Position v-else />
                </el-icon>
              </el-button>
            </div>
          </div>
        </div>
        <div class="disclaimer">{{ APP_NAME }} may display inaccurate info.</div>
      </div>
    </div>
    </main>

    <!-- 聊天树弹窗 -->
    <el-dialog v-model="showChatTree" title="Conversation Tree" width="80%" top="5vh">
      <div id="echarts-tree-container" class="tree-container"></div>
    </el-dialog>

    <!-- OpenClaw配置选择对话框 -->
    <el-dialog v-model="showOpenClawConfigDialog" title="选择OpenClaw配置" width="400px">
      <div class="openclaw-config-selection">
        <p style="margin-bottom: 16px; color: #666;">请选择要连接的OpenClaw配置：</p>
        <el-radio-group v-model="selectedConfigId" class="config-radio-group">
          <el-radio 
            v-for="config in openClawConfigs" 
            :key="config.id" 
            :label="config.id"
            class="config-radio"
          >
            <div class="config-info">
              <div class="config-name">{{ config.display_name }}</div>
              <div class="config-url">{{ config.gateway_url }}</div>
            </div>
          </el-radio>
        </el-radio-group>
        <div v-if="openClawConfigs.length === 0" class="no-configs">
          <el-empty description="暂无配置" :image-size="60" />
          <el-button type="primary" @click="showSettings = true; settingsActiveTab = 'openclaw'; showOpenClawConfigDialog = false" style="width: 100%; margin-top: 16px;">
            创建配置
          </el-button>
        </div>
      </div>
      <template #footer>
        <el-button @click="showOpenClawConfigDialog = false">取消</el-button>
        <el-button 
          type="primary" 
          @click="handleSelectOpenClawConfig"
          :disabled="!selectedConfigId"
          :loading="isOpenClawConnecting"
        >
          连接
        </el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="showConversationInstructions" title="会话指令" width="520px" :modal="false" :close-on-click-modal="false" :destroy-on-close="true">
      <div class="settings-section">
        <h3>添加指令</h3>
        <el-input
          v-model="conversationInstructionInput"
          type="textarea"
          :rows="4"
          placeholder="仅对当前会话生效；会拼接进 system prompt"
          style="margin-bottom: 10px"
        />
        <el-button
          type="primary"
          :loading="isConversationInstructionSubmitting"
          @click="handleAddConversationInstruction"
          style="width: 100%"
        >
          添加
        </el-button>

        <h3 style="margin-top: 20px">指令列表</h3>
        <el-table :data="conversationInstructions" style="width: 100%" max-height="320" v-loading="isConversationInstructionsLoading">
          <el-table-column prop="content" label="内容" />
          <el-table-column label="操作" width="170">
            <template #default="scope">
              <el-button link size="small" @click="moveConversationInstructionUp(scope.row)" :disabled="scope.$index === 0">
                上移
              </el-button>
              <el-button
                link
                size="small"
                @click="moveConversationInstructionDown(scope.row)"
                :disabled="scope.$index === conversationInstructions.length - 1"
              >
                下移
              </el-button>
              <el-button link type="danger" size="small" @click="handleDeleteConversationInstruction(scope.row)">
                删除
              </el-button>
            </template>
          </el-table-column>
        </el-table>
      </div>
    </el-dialog>

  </div>
</template>

<style lang="scss" scoped>
/* 树状图样式 */
.tree-container {
  width: 100%;
  height: 80vh;
  min-height: 600px;
  overflow: hidden;
}

/* 变量 */
$bg-sidebar: #f0f4f9;
$bg-main: #ffffff;
$bg-input: #f0f4f9;
$text-primary: #1f1f1f;
$text-secondary: #5f6368;
$hover-color: #e3e3e3;

/* 消息操作栏 (复制按钮) */
.message-actions {
  margin-top: 8px;
  display: flex;
  justify-content: flex-end;
  opacity: 0; /* 默认隐藏 */
  transition: opacity 0.3s;
}

.message:hover .message-actions {
  opacity: 1; /* 鼠标悬停显示 */
}

/* 旋转动画 */
.is-loading {
  animation: rotate 2s linear infinite;
}

/* 头像样式优化 */
.avatar-circle {
  width: 32px;
  height: 32px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-weight: bold;
  font-size: 16px;
  color: white;
  flex-shrink: 0;
}

.user-theme {
  background-color: #7B3DCC; /* 紫色 */
}

/* 恢复 AI 动画头像样式 */
.ai-logo {
  font-size: 24px;
  animation: pulse 2s infinite;
  display: flex;
  align-items: center;
  justify-content: center;
  width: 32px;
  height: 32px;
}

@keyframes pulse {
  0% { transform: scale(1); opacity: 1; }
  50% { transform: scale(1.1); opacity: 0.8; }
  100% { transform: scale(1); opacity: 1; }
}

/* 消息操作栏显眼化 */
.message-actions {
  margin-top: 12px;
  display: flex;
  justify-content: flex-start; /* 左对齐 */
  opacity: 1 !important; /* 强制常驻显示，作为结束标志 */
  border-top: 1px solid #eee;
  padding-top: 8px;
}

@keyframes rotate {
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
}

.gemini-layout {
  display: flex;
  height: 100vh;
  width: 100vw;
  background-color: $bg-main;
  color: $text-primary;
  font-family: 'Google Sans', 'Inter', sans-serif;
}

/* 侧边栏 */
.sidebar {
  width: 280px;
  background-color: $bg-sidebar;
  display: flex;
  flex-direction: column;
  padding: 20px 15px;
  transition: width 0.3s cubic-bezier(0.2, 0, 0, 1);

  &.collapsed {
    width: 70px;

    .history-container,
    .location-text,
    .new-chat-pill span,
    .sidebar-footer {
      display: none;
    }

    .new-chat-pill {
      width: 40px;
      padding: 10px;
      justify-content: center;
    }
  }

  .sidebar-header {
    margin-bottom: 20px;
  }

  .menu-btn {
    color: $text-secondary;
    margin-bottom: 20px;
    margin-left: 5px;
  }

  .new-chat-pill {
    background-color: #dde3ea;
    color: #444746;
    border-radius: 20px;
    padding: 10px 15px;
    width: 140px;
    display: flex;
    align-items: center;
    gap: 10px;
    cursor: pointer;
    font-size: 14px;
    font-weight: 500;

    &:hover {
      background-color: #d0d7de;
    }
  }

  .history-container {
    flex: 1;
    overflow-y: auto;
    margin-top: 10px;

    .group-label {
      font-size: 12px;
      font-weight: 500;
      color: $text-secondary;
      padding-left: 10px;
      margin-bottom: 10px;
    }

    .empty-history {
      font-size: 12px;
      color: #999;
      text-align: center;
      margin-top: 20px;
    }

    .history-item {
      display: flex;
      align-items: center;
      gap: 12px;
      padding: 10px 15px;
      border-radius: 20px;
      cursor: pointer;
      color: $text-primary;
      font-size: 14px;
      position: relative;
      height: 44px;

      &:hover {
        background-color: $hover-color;

        .delete-icon {
          display: block;
        }
      }

      &.active {
        background-color: #d3e3fd;
        color: #0b57d0;
        font-weight: 500;
      }

      .text-truncate {
        overflow: hidden;
        text-overflow: ellipsis;
        white-space: nowrap;
        flex: 1;
      }

      .delete-icon {
        display: none;
        color: #5f6368;
        font-size: 14px;
        padding: 4px;
        border-radius: 50%;

        &:hover {
          background-color: rgba(0, 0, 0, 0.1);
          color: #d93025;
        }
      }
    }
  }
}

/* 主区域 (和之前的基本一致，保持样式完整性) */
.main-area {
  flex: 1;
  display: flex;
  flex-direction: column;
  position: relative;
  background: $bg-main;
}

/* 嵌入式设置页样式 */
.settings-embedded-container {
  flex: 1;
  display: flex;
  background-color: $bg-main;
  overflow: hidden;
  height: 100%;
}

.settings-sidebar {
  width: 240px;
  border-right: 1px solid #e0e0e0;
  padding: 30px 20px;
  display: flex;
  flex-direction: column;
  background-color: #fafafa;

  .settings-title {
    font-size: 24px;
    font-weight: 600;
    margin-bottom: 30px;
    color: $text-primary;
  }

  .settings-menu {
    display: flex;
    flex-direction: column;
    gap: 8px;

    .menu-item {
      padding: 10px 15px;
      border-radius: 8px;
      cursor: pointer;
      color: $text-secondary;
      font-size: 15px;
      transition: all 0.2s;

      &:hover {
        background-color: #e8e8e8;
        color: $text-primary;
      }

      &.active {
        background-color: #e3e3e3;
        color: $text-primary;
        font-weight: 500;
      }
    }
  }
}

.settings-content {
  flex: 1;
  padding: 40px 60px;
  overflow-y: auto;

  .settings-panel {
    max-width: 800px;
    margin: 0 auto;

    h3 {
      font-size: 20px;
      margin-bottom: 24px;
      font-weight: 500;
      color: $text-primary;
    }

    .setting-tip {
      font-size: 12px;
      color: #909399;
      line-height: 1.4;
      margin-top: 4px;
    }

    .advanced-settings {
      border: none;
      margin-top: 10px;
      
      :deep(.el-collapse-item__header) {
        border-bottom: none;
        height: 32px;
        color: #409eff;
        font-size: 13px;
      }
      
      :deep(.el-collapse-item__wrap) {
        border-bottom: none;
        background-color: transparent;
      }

      :deep(.el-collapse-item__content) {
        padding-bottom: 10px;
      }
    }
  }
}

/* 聊天主界面容器 */
.chat-container-wrapper {
  flex: 1;
  display: flex;
  flex-direction: column;
  height: 100%;
  overflow: hidden;
}

.top-bar {
  height: 60px;
  padding: 0 20px;
  display: flex;
  justify-content: space-between;
  align-items: center;

  .model-name {
    font-size: 16px;
    color: #444746;
    cursor: pointer;
    display: flex;
    align-items: center;
    gap: 5px;
  }
}

.content-scroll-area {
  flex: 1;
  overflow-y: auto;
  padding: 20px;
  display: flex;
  flex-direction: column;
  align-items: center;

  &::-webkit-scrollbar {
    width: 6px;
  }

  &::-webkit-scrollbar-thumb {
    background-color: #e0e0e0;
    border-radius: 3px;
  }
}

.welcome-container {
  max-width: 800px;
  width: 100%;
  margin-top: 10vh;
  display: flex;
  flex-direction: column;
  align-items: center;

  .greeting {
    margin-bottom: 40px;
    text-align: center;

    h1 {
      font-size: 56px;
      line-height: 1.2;
      font-weight: 500;
      margin: 0;
    }

    .gradient-text {
      background: linear-gradient(90deg, #4285f4, #9b72cb, #d96570);
      -webkit-background-clip: text;
      -webkit-text-fill-color: transparent;
      display: inline-block;
    }

    .sub-text {
      color: #c4c7c5;
      margin-top: 10px;
    }
  }

  .cards-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
    gap: 15px;
    width: 100%;

    .suggestion-card {
      background: #f0f4f9;
      border-radius: 12px;
      padding: 20px;
      height: 160px;
      cursor: pointer;
      display: flex;
      flex-direction: column;
      justify-content: space-between;

      &:hover {
        background: #dde3ea;
      }

      p {
        margin: 0;
        font-size: 15px;
        line-height: 1.5;
      }

      .card-icon {
        align-self: flex-end;
        background: #fff;
        padding: 10px;
        border-radius: 50%;
        display: flex;
      }
    }
  }
}

.chat-list {
  width: 100%;
  max-width: 800px;
  padding-bottom: 20px;
  margin-top: 20px;

  .message {
    display: flex;
    gap: 15px;
    margin-bottom: 30px;

    .avatar-col {
      flex-shrink: 0;
      width: 30px;
    }

    .text-col {
      flex: 1;
      line-height: 1.6;
      font-size: 16px;
      color: #333;
      overflow-x: hidden;

      .message-attachments {
        margin-top: 8px;
        display: flex;
        flex-wrap: wrap;
        gap: 8px;

        .att-item {
          display: inline-flex;
          align-items: center;
          gap: 8px;
          max-width: 320px;
          padding: 8px 10px;
          border: 1px solid #e0e0e0;
          border-radius: 10px;
          background: #fff;
          cursor: pointer;
          color: inherit;
          overflow: hidden;
        }

        .att-thumb {
          width: 72px;
          height: 54px;
          border-radius: 8px;
          border: 1px solid #eee;
          background: #f6f7f8;
          object-fit: cover;
          flex-shrink: 0;
        }

        .att-icon {
          width: 72px;
          height: 54px;
          border-radius: 8px;
          border: 1px solid #eee;
          background: #f6f7f8;
          display: flex;
          align-items: center;
          justify-content: center;
          color: #666;
          flex-shrink: 0;
        }

        .att-meta {
          display: flex;
          flex-direction: column;
          gap: 2px;
          min-width: 0;
        }

        .att-name {
          font-size: 13px;
          font-weight: 600;
          color: #1f1f1f;
          overflow: hidden;
          text-overflow: ellipsis;
          white-space: nowrap;
        }

        .att-sub {
          font-size: 12px;
          color: #666;
          overflow: hidden;
          text-overflow: ellipsis;
          white-space: nowrap;
        }
      }
    }

    .user-avatar {
      background: #8e44ad;
      color: white;
      font-weight: bold;
    }

    .ai-logo {
      width: 30px;
      height: 30px;
      display: flex;
      align-items: center;
      justify-content: center;
      font-size: 20px;
      animation: spin 3s linear infinite;
    }
  }
}

:deep(.markdown-body) {
  p {
    margin-bottom: 10px;
  }

  .code-block {
    position: relative;
  }

  .copy-code-btn {
    position: absolute;
    top: 10px;
    right: 10px;
    font-size: 12px;
    line-height: 1;
    padding: 6px 8px;
    border: 1px solid rgba(255, 255, 255, 0.18);
    border-radius: 8px;
    background: rgba(0, 0, 0, 0.35);
    color: rgba(255, 255, 255, 0.92);
    cursor: pointer;
    user-select: none;
  }

  .copy-code-btn:hover {
    background: rgba(0, 0, 0, 0.5);
  }

  pre {
    background: #282c34;
    padding: 15px;
    border-radius: 8px;
    overflow-x: auto;
    color: #abb2bf;
    margin: 10px 0;
  }

  code {
    font-family: 'Consolas', monospace;
    font-size: 0.9em;
    background-color: rgba(0, 0, 0, 0.05);
    padding: 2px 4px;
    border-radius: 4px;
  }

  pre code {
    background-color: transparent;
    padding: 0;
  }

  ul,
  ol {
    padding-left: 20px;
    margin-bottom: 10px;
  }

  h1,
  h2,
  h3 {
    margin-top: 20px;
    margin-bottom: 10px;
    font-weight: 600;
    color: #1f1f1f;
  }

  a {
    color: #1967d2;
    text-decoration: none;
  }

  blockquote {
    border-left: 4px solid #dfe2e5;
    color: #6a737d;
    padding-left: 15px;
    margin: 10px 0;
  }
}

.typing-indicator {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 10px 0;

  span {
    width: 6px;
    height: 6px;
    background: #ccc;
    border-radius: 50%;
    animation: bounce 1.4s infinite ease-in-out both;

    &:nth-child(1) {
      animation-delay: -0.32s;
    }

    &:nth-child(2) {
      animation-delay: -0.16s;
    }
  }
}

@keyframes bounce {

  0%,
  80%,
  100% {
    transform: scale(0);
  }

  40% {
    transform: scale(1);
  }
}

@keyframes spin {
  0% {
    transform: rotate(0deg);
  }

  100% {
    transform: rotate(360deg);
  }
}

.input-container-wrapper {
  padding: 0 20px 30px 20px;
  display: flex;
  flex-direction: column;
  align-items: center;
  width: 100%;
  background: transparent;

  .input-box {
    width: 100%;
    max-width: 800px;
    background: #ffffff; /* 改为白色背景 */
    border-radius: 24px; /* 增加圆角 */
    padding: 16px 20px 10px 20px; /* 调整内边距 */
    display: flex;
    flex-direction: column; /* 改为纵向布局 */
    transition: all 0.2s ease;
    border: 1px solid #e0e0e0; /* 增加边框 */
    box-shadow: 0 2px 6px rgba(0, 0, 0, 0.05); /* 增加阴影 */

    &:focus-within {
      background: white;
      box-shadow: 0 4px 12px rgba(0, 0, 0, 0.1); /* 聚焦时加深阴影 */
      border-color: #d0d0d0;
    }

    /* 移除旧的 action-btn 样式，统一在 toolbar 中管理 */
    .action-btn {
      color: $text-secondary;
      margin-right: 5px;
      transition: color 0.2s;
      width: 36px;
      height: 36px;

      &.has-files {
        color: #4285f4;
        background-color: #e8f0fe;
      }

      &:hover {
        color: #1f1f1f;
        background-color: #f1f3f4;
      }
    }

    /* 附件预览区样式 */
    .attachment-preview-area {
      display: flex;
      gap: 10px;
      padding-bottom: 10px;
      margin-bottom: 10px;
      border-bottom: 1px solid #f0f0f0;
      overflow-x: auto;
      
      .attachment-card {
        position: relative;
        display: flex;
        flex-direction: column;
        align-items: center;
        width: 100px;
        background: #f8f9fa;
        border-radius: 8px;
        padding: 8px;
        border: 1px solid #e0e0e0;
        
        .preview-thumb {
          width: 80px;
          height: 60px;
          background-size: cover;
          background-position: center;
          border-radius: 4px;
          margin-bottom: 6px;
        }
        
        .preview-file {
          width: 80px;
          height: 60px;
          display: flex;
          align-items: center;
          justify-content: center;
          font-size: 32px;
          color: #909399;
          margin-bottom: 6px;
        }
        
        .file-meta {
          width: 100%;
          text-align: center;
          
          .fname {
            display: block;
            font-size: 12px;
            color: #333;
            white-space: nowrap;
            overflow: hidden;
            text-overflow: ellipsis;
          }
          
          .fsize {
            font-size: 10px;
            color: #999;
          }
        }
        
        .remove-btn {
          position: absolute;
          top: -6px;
          right: -6px;
          width: 20px;
          height: 20px;
          background: #ff4d4f;
          color: white;
          border-radius: 50%;
          display: flex;
          align-items: center;
          justify-content: center;
          cursor: pointer;
          font-size: 12px;
          opacity: 0;
          transition: opacity 0.2s;
        }
        
        &:hover .remove-btn {
          opacity: 1;
        }
      }
    }

    .gemini-input {
      width: 100%;
      margin: 0 0 10px 0; /* 底部留白给工具栏 */

      :deep(.el-textarea__inner) {
        box-shadow: none !important;
        background: transparent !important;
        padding: 0;
        border: none !important;
        font-size: 16px;
        color: $text-primary;
        line-height: 1.5;
        min-height: 24px !important;

        &::-webkit-scrollbar {
          width: 4px;
        }

        &::-webkit-scrollbar-thumb {
          background: #ccc;
          border-radius: 2px;
        }
        
        &::placeholder {
          color: #8e8e8e; /* 调整 placeholder 颜色 */
        }
      }
    }
    
    /* 工具栏样式 */
    .input-toolbar {
      display: flex;
      justify-content: space-between;
      align-items: center;
      width: 100%;
      
      .toolbar-left, .toolbar-right {
        display: flex;
        align-items: center;
        gap: 4px;
      }
      
      .search-btn {
        color: #5f6368;
        width: 36px;
        height: 36px;
        transition: all 0.3s ease;

        &:hover {
          background-color: #f1f3f4;
        }

        &.is-active {
          background-color: #e8f0fe;
          color: #1967d2;
        }
      }

      .send-btn {
        margin-left: 4px;
        width: 36px;
        height: 36px;
        
        &.is-disabled {
          background-color: transparent;
        }
      }
    }
  }

  .disclaimer {
    margin-top: 12px;
    font-size: 11px;
    color: $text-secondary;
  }
}

/* OpenClaw配置选择样式 */
.openclaw-config-selection {
  .config-radio-group {
    display: flex;
    flex-direction: column;
    gap: 12px;
    width: 100%;
  }
  
  .config-radio {
    display: block;
    margin-right: 0;
    padding: 12px;
    border: 1px solid #e4e7ed;
    border-radius: 6px;
    transition: all 0.3s;
    
    &:hover {
      border-color: #409eff;
      background-color: #f5f7fa;
    }
    
    &.is-checked {
      border-color: #409eff;
      background-color: #ecf5ff;
    }
    
    .config-info {
      display: flex;
      flex-direction: column;
      gap: 4px;
      
      .config-name {
        font-weight: 500;
        color: #303133;
        font-size: 14px;
      }
      
      .config-url {
        color: #909399;
        font-size: 12px;
        word-break: break-all;
      }
    }
  }
  
  .no-configs {
    text-align: center;
    padding: 20px 0;
  }
}

</style>

<style lang="scss">
.file-selector-popover {
  padding: 10px !important;
  border-radius: 12px !important;

  .file-list-header {
    font-size: 13px;
    font-weight: 600;
    color: #5f6368;
    margin-bottom: 10px;
    padding: 0 5px;
    display: flex;
    justify-content: space-between;

    .count {
      color: #4285f4;
    }
  }

  .empty-files {
    text-align: center;
    padding: 20px;
    color: #999;
    font-size: 12px;
  }

  .file-checkbox-group {
    display: flex;
    flex-direction: column;
    gap: 5px;
  }

  .file-item {
    .el-checkbox {
      width: 100%;
      margin-right: 0;
      height: auto;
      padding: 8px 5px;
      border-radius: 6px;

      &:hover {
        background-color: #f5f5f5;
      }
    }

    .el-checkbox__label {
      width: 100%;
    }

    .file-info {
      display: flex;
      align-items: center;
      gap: 8px;
      width: 100%;

      .fname {
        font-size: 14px;
        color: #333;
        overflow: hidden;
        text-overflow: ellipsis;
        white-space: nowrap;
        max-width: 180px;
      }
    }
  }
}

/* OpenClaw配置下拉菜单样式 */
.openclaw-config-dropdown {
  .config-dropdown-item {
    display: flex;
    flex-direction: column;
    gap: 4px;
    padding: 8px 0;
    min-width: 200px;
    
    .config-name {
      font-weight: 500;
      color: #303133;
      font-size: 14px;
    }
    
    .config-url {
      color: #909399;
      font-size: 12px;
      word-break: break-all;
    }
  }
  
  .el-dropdown-menu__item.is-active {
    background-color: #ecf5ff;
    color: #409eff;
  }
}
</style>
