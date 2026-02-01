<script setup>
import { ref, reactive, computed, onMounted, nextTick } from 'vue'
import * as echarts from 'echarts'
import {
  Plus, Setting, User,
  ChatDotRound, Menu,
  Compass, DataLine, Trophy, Collection,
  Connection,
  Document, Paperclip, ArrowDown, Delete,
  Share, CopyDocument, Position, Loading // 引入新图标
} from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'

// --- API --- API ---
import { getFiles, uploadFile } from '@/api/file'
// ★ 引入 chatStream8
import { chatStream, getConversations, getConversationMessages, deleteConversation, getNodePath, getModels, createModel, deleteModel } from '@/api/chat'
import renderMarkdown from '@/utils/markdown'
import { useUserStore } from '@/stores/userStore'

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

const isSidebarCollapsed = ref(false)
const inputMessage = ref('')
const currentModel = ref('deepseek-chat')
const enableSearch = ref(false)
const showChatTree = ref(false) // 控制树状图弹窗显示

// --- 3. 会话管理 ---
const showSettings = ref(false)
const availableModels = ref([
  // 默认模型 (可以被后端数据覆盖或合并)
  { model_name: 'deepseek-chat', display_name: 'DeepSeek Chat' },
  { model_name: 'gpt-3.5-turbo', display_name: 'GPT-3.5 Turbo' },
  { model_name: 'gpt-4', display_name: 'GPT-4' },
  { model_name: 'kimi-k2.5', display_name: 'Kimi-k2.5' },
  { model_name: 'qwen-turbo', display_name: 'Qwen Turbo' },
  { model_name: 'qwen-plus', display_name: 'Qwen Plus' },
  { model_name: 'gemini-pro', display_name: 'Gemini Pro' }
])
const newModelForm = reactive({ model_name: '', display_name: '' })

// --- 3. 会话管理 ---
const currentConversationId = ref(null)
// const currentLeafId = ref(null) // 移除独立的 ref，改用计算属性或从 Cache 获取
// const chatHistory = ref([]) // 移除独立的 ref

// 计算属性：当前是否正在发送
const isSending = computed(() => {
  if (!currentConversationId.value) return false // 新会话（未创建ID前）暂时不支持并发锁（或者需要另外处理）
  return sessionCache[currentConversationId.value]?.isSending || false
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

// 临时变量：用于“新会话”（尚未生成 ID 时）的临时消息存储
// 当用户点击 New Chat 时，currentConversationId = null
// 我们需要一个临时的 storage，等到第一条消息发送成功获得 session_id 后，再迁移到 sessionCache
const tempNewSessionState = reactive({
  messages: [],
  currentLeafId: null
})

// 修改 chatHistory 的计算逻辑以支持新会话
const displayMessages = computed(() => {
  if (!currentConversationId.value) {
    return tempNewSessionState.messages
  }
  return sessionCache[currentConversationId.value]?.messages || []
})

const historyList = ref([])

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
})

const currentSessionMessages = ref([]) // 当前会话的原始消息列表

// --- 6. 核心方法集 ---

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
      { model_name: 'gpt-3.5-turbo', display_name: 'GPT-3.5 Turbo' },
      { model_name: 'gpt-4', display_name: 'GPT-4' },
      { model_name: 'kimi-k2.5', display_name: 'Kimi-k2.5' },
      { model_name: 'qwen-turbo', display_name: 'Qwen Turbo' },
      { model_name: 'qwen-plus', display_name: 'Qwen Plus' },
      { model_name: 'gemini-pro', display_name: 'Gemini Pro' },
      { model_name: 'ollama/llama3.2:1b', display_name: 'Llama3 (Local)' } // 添加默认的 Ollama 示例
    ]
    
    // 过滤掉已经在 customModels 里的默认模型 (按 model_name)
    const existingNames = new Set(customModels.map(m => m.model_name))
    const filteredDefaults = defaultModels.filter(m => !existingNames.has(m.model_name))
    
    availableModels.value = [...filteredDefaults, ...customModels]
  } catch (error) {
    console.error("加载模型列表失败:", error)
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
  currentConversationId.value = null
  // 重置临时状态
  tempNewSessionState.messages = []
  tempNewSessionState.currentLeafId = null
  
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

// --- 聊天树逻辑 ---
const openChatTree = async () => {
  if (!currentConversationId.value) return
  
  try {
    // 每次打开都重新获取一次，保证最新
    const messages = await getConversationMessages(currentConversationId.value)
    currentSessionMessages.value = messages
    
    // 转换数据为 ECharts 树形结构
    const treeData = buildEChartsTree(messages)
    showChatTree.value = true
    
    // 等待 DOM 渲染后初始化 ECharts
    nextTick(() => {
       initEChartsTree(treeData)
    })
    
  } catch (error) {
    ElMessage.error('加载聊天树失败')
    console.error(error)
  }
}

// 构建 ECharts 需要的树结构
function buildEChartsTree(items) {
  const nodeMap = {}
  const rootNodes = []

  // 1. 初始化 Map
  items.forEach(item => {
    // 截断过长文本
    const label = item.content.length > 15 ? item.content.substring(0, 15) + '...' : item.content
    nodeMap[item.node_id] = { 
      name: `${item.role === 'user' ? '用户' : 'AI'}\n${label}`,
      id: item.node_id, // 存储真实ID用于点击
      value: item.role, // 可以用来区分颜色
      children: [],
      original: item,
      // 样式配置
      itemStyle: {
        color: '#fff',
        borderColor: '#000',
        borderWidth: 1.5,
      },
      label: {
        color: '#000',
        fontSize: 12,
        align: 'center',
        verticalAlign: 'middle',
        backgroundColor: 'transparent'
      },
      // 矩形节点
      symbol: 'rect',
      symbolSize: [120, 40]
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

// 初始化 ECharts
const initEChartsTree = (data) => {
  const chartDom = document.getElementById('echarts-tree-container')
  if (!chartDom) return
  
  // 销毁旧实例
  let myChart = echarts.getInstanceByDom(chartDom)
  if (myChart) myChart.dispose()
  
  myChart = echarts.init(chartDom)
  
  const option = {
    tooltip: {
      trigger: 'item',
      triggerOn: 'mousemove',
      formatter: function (params) {
         // 悬浮显示完整内容
         const original = params.data.original
         if (original) {
             return `${original.role === 'user' ? '用户' : 'AI'}:<br/>${original.content}`
         }
         return params.name
      }
    },
    series: [
      {
        type: 'tree',
        data: [data],
        top: '5%',
        left: '15%', // 留出左边距
        bottom: '5%',
        right: '20%',
        symbolSize: 7,
        orient: 'TB', // 从上到下 (Top-Bottom)
        
        // 连接线样式
        itemStyle: {
          borderWidth: 1.5,
          borderColor: '#000',
        },
        lineStyle: {
          color: '#000',
          width: 1.5,
          curveness: 0 // 直线 (类似手绘风格)
        },
        
        label: {
          position: 'inside', // 文字在框内
          verticalAlign: 'middle',
          align: 'center',
          fontSize: 12,
          lineHeight: 14,
          formatter: function(params) {
              return params.name
          }
        },
        
        leaves: {
          label: {
            position: 'inside',
            verticalAlign: 'middle',
            align: 'center'
          }
        },
        
        expandAndCollapse: true,
        animationDuration: 550,
        animationDurationUpdate: 750,
        initialTreeDepth: -1 // 展开所有
      }
    ]
  }

  myChart.setOption(option)
  
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
    currentLeafId.value = data.id 
    
    // 2. 调用后端接口获取【从根节点到当前点击节点】的完整路径
    // 注意：这里不再自动向后延伸，而是准确地停在用户点击的那个节点
    const pathMessages = await getNodePath(data.id)
    
    // 3. 更新界面
    chatHistory.value = pathMessages.map(msg => ({
      role: msg.role === 'assistant' ? 'ai' : 'user',
      content: msg.content,
      html: msg.role === 'assistant' ? renderMarkdown(msg.content) : '',
      loading: false
    }))
    
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

// ★★★ 发送消息核心逻辑 (改为流式调用) ★★★
const sendMessage = async () => {
  const text = inputMessage.value.trim()
  if (!text) return
  if (isSending.value) return // 防止重复发送

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
       sessionCache[currentConversationId.value] = { messages: [], isSending: false, currentLeafId: null }
    }
    activeSessionState = sessionCache[currentConversationId.value]
  }

  // --- 2. 用户消息上屏 ---
  activeSessionState.messages.push({ role: 'user', content: text })
  inputMessage.value = ''
  
  // 设置发送状态 (注意：对于新会话，这里设置的是临时变量，暂时没用 computed 追踪它，但没关系)
  if (!isNewSession) {
     activeSessionState.isSending = true 
  }
  
  scrollToBottom()

  // --- 3. AI Loading 占位 ---
  const aiMessage = reactive({
    role: 'ai', content: '', html: '', loading: true, done: false 
  })
  activeSessionState.messages.push(aiMessage)
  scrollToBottom()

  // --- 4. 构造请求体 ---
  const payload = {
    user_id: userStore.userInfo?.id,
    message: text,
    model_name: currentModel.value,
    enable_search: enableSearch.value,
    enable_rag: selectedCount.value > 0,
    file_ids: selectedFileIds.value,
    conversation_id: currentConversationId.value,
    parent_id: activeSessionState.currentLeafId // 使用当前会话的状态
  }

  // --- 5. 发起流式请求 ---
  let fullText = "" 
  
  // 保存发起请求时的 Session ID，用于闭包中判断是否还是当前视图
  const requestSessionId = currentConversationId.value

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
      
      if (!isNewSession) {
         activeSessionState.isSending = false
      }
      
      // 如果是新会话，流结束后刷新列表以显示新标题
      if (isNewSession) {
         fetchSessionList()
      }
    },
    // onError: 报错
    (err) => {
      aiMessage.loading = false
      aiMessage.done = true
      if (!isNewSession) {
         activeSessionState.isSending = false
      }
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
             isSending: true, // 继承发送状态
             currentLeafId: null,
             scrollTop: 0
           }
           
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
const toggleSidebar = () => isSidebarCollapsed.value = !isSidebarCollapsed.value

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
      <header class="top-bar">
        <!-- 模型切换下拉菜单 -->
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
        
        <!-- 新增：聊天树按钮 -->
        <el-button v-if="currentConversationId" circle @click="openChatTree" title="查看对话树" style="margin-right: 12px; margin-left: auto;">
           <el-icon><Share /></el-icon>
        </el-button>

        <el-avatar :size="32" class="user-avatar" style="margin-left: 12px">U</el-avatar>
      </header>

      <div class="content-scroll-area" ref="chatContainerRef">
        <div v-if="!isChatting" class="welcome-container">
          <div class="greeting">
            <h1 class="gradient-text">Hello, Developer</h1>
            <h1 class="sub-text">How can I help you today?</h1>
          </div>
        </div>

        <div v-else class="chat-list">
          <div v-for="(msg, index) in chatHistory" :key="index" class="message" :class="msg.role">
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
                   <div v-html="msg.html"></div>
                   <!-- 复制按钮 -->
                   <div v-if="msg.done" class="message-actions">
                     <el-button type="primary" plain size="small" @click="handleCopy(msg.content)">
                       <el-icon style="margin-right: 4px"><CopyDocument /></el-icon> 复制内容
                     </el-button>
                   </div>
                </div>
              </div>
              <div v-else class="user-text">{{ msg.content }}</div>
            </div>
          </div>
        </div>
      </div>

      <div class="input-container-wrapper">
        <div class="input-box">
          <!-- 1. 输入区域 (顶部) -->
          <el-input 
            v-model="inputMessage" 
            type="textarea" 
            :autosize="{ minRows: 1, maxRows: 8 }"
            :placeholder="selectedCount > 0 ? `已引用 ${selectedCount} 个文件...` : '问问 xunji'"
            class="gemini-input" 
            resize="none" 
            @keydown.enter.exact.prevent="sendMessage" 
          />

          <!-- 2. 工具栏 (底部) -->
          <div class="input-toolbar">
            <!-- 左侧工具: 添加附件、知识库 -->
            <div class="toolbar-left">
              <el-popover placement="top-start" :width="300" trigger="click" popper-class="file-selector-popover">
                <template #reference>
                  <el-button circle link class="action-btn" :class="{ 'has-files': selectedCount > 0 }">
                    <el-icon :size="20"><Plus /></el-icon>
                  </el-button>
                </template>
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
                    </div>
                  </el-checkbox-group>
                </el-scrollbar>
              </el-popover>

              <input type="file" ref="fileInput" style="display: none" accept=".pdf,.txt,.md,.docx,.py,.java" @change="handleFileChange">
              <el-tooltip content="上传文件" placement="top" effect="dark">
                <el-button circle link class="action-btn" @click="triggerFileInput" :loading="isUploading">
                  <el-icon :size="20" v-if="!isUploading"><Paperclip /></el-icon>
                </el-button>
              </el-tooltip>
            </div>

            <!-- 右侧工具: 搜索、发送 -->
            <div class="toolbar-right">
              <el-tooltip effect="dark" :content="enableSearch ? '联网搜索: 开' : '联网搜索: 关'" placement="top">
                <el-button circle link class="search-btn" :class="{ 'is-active': enableSearch }" @click="enableSearch = !enableSearch">
                  <el-icon :size="18"><Connection /></el-icon>
                </el-button>
              </el-tooltip>
              
              <el-button circle :type="inputMessage ? 'primary' : ''" :disabled="!inputMessage && !isSending" @click="sendMessage" class="send-btn">
                <el-icon :size="18">
                  <Loading v-if="isSending" class="is-loading" />
                  <Position v-else />
                </el-icon>
              </el-button>
            </div>
          </div>
        </div>
        <div class="disclaimer">{{ APP_NAME }} may display inaccurate info.</div>
      </div>
    </main>

    <!-- 聊天树弹窗 -->
    <el-dialog v-model="showChatTree" title="Conversation Tree" width="80%" top="5vh">
      <div id="echarts-tree-container" class="tree-container"></div>
    </el-dialog>

    <!-- 设置弹窗 -->
    <el-dialog v-model="showSettings" title="设置" width="500px">
      <el-tabs>
        <el-tab-pane label="模型管理" name="models">
          <div class="settings-section">
            <h3>添加新模型</h3>
            <div class="add-model-form">
              <el-input v-model="newModelForm.model_name" placeholder="模型ID (如 gpt-4)" style="margin-bottom: 10px" />
              <el-input v-model="newModelForm.display_name" placeholder="显示名称 (如 GPT-4)" style="margin-bottom: 10px" />
              <el-button type="primary" @click="handleAddModel" style="width: 100%">添加</el-button>
            </div>

            <h3 style="margin-top: 20px">可用模型列表</h3>
            <el-table :data="availableModels" style="width: 100%" max-height="300">
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
        </el-tab-pane>
      </el-tabs>
    </el-dialog>

  </div>
</template>

<style lang="scss" scoped>
/* 树状图样式 */
.tree-container {
  width: 100%;
  height: 600px;
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
</style>