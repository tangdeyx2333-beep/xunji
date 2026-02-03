import request from '@/utils/request'
import { ElMessage } from 'element-plus'

// 保留原有的非流式方法（可选，或者删除）
export function chatWithModel(data) {
  return request({ url: '/api/chat', method: 'post', data })
}

export function getConversations(params) {
  return request({ url: '/api/conversations', method: 'get', params })
}

export function getConversationMessages(conversationId) {
  return request({ url: `/api/conversations/${conversationId}/messages`, method: 'get' })
}

export function deleteConversation(conversationId) {
  return request({ url: `/api/conversations/${conversationId}`, method: 'delete' })
}

// 新增：根据节点ID获取完整路径消息
export function getNodePath(nodeId) {
  return request({ url: `/api/tree/path/${nodeId}`, method: 'get' })
}

// --- 模型管理 API ---
export function getModels() {
  return request({ url: '/api/models', method: 'get' })
}

export function createModel(data) {
  return request({ url: '/api/models', method: 'post', data })
}

export function deleteModel(modelId) {
  return request({ url: `/api/models/${modelId}`, method: 'delete' })
}

export function getAttachmentSignedUrl(attachmentId, params) {
  return request({ url: `/api/attachments/${attachmentId}/signed-url`, method: 'get', params })
}

// --- AI 指令 API ---
export function getInstructions() {
  return request({ url: '/api/instructions', method: 'get' })
}

export function createInstruction(data) {
  return request({ url: '/api/instructions', method: 'post', data })
}

export function updateInstruction(instructionId, data) {
  return request({ url: `/api/instructions/${instructionId}`, method: 'put', data })
}

export function deleteInstruction(instructionId) {
  return request({ url: `/api/instructions/${instructionId}`, method: 'delete' })
}

/**
 * ★★★ 新增：流式对话核心方法 ★★★
 * 使用原生 fetch 实现
 */
export async function chatStream(data, onMessage, onDone, onError, onMeta) {
  try {
    const token = localStorage.getItem('access_token')

    const baseUrl = import.meta.env.VITE_API_BASE_URL
    if (!baseUrl) {
      throw new Error('Missing required env: VITE_API_BASE_URL')
    }
    
    const response = await fetch(`${baseUrl}/api/chat`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${token}`
      },
      body: JSON.stringify(data)
    })

    if (!response.ok) {
       if (response.status === 401) ElMessage.error('登录已过期')
       throw new Error(`HTTP error! status: ${response.status}`)
    }

    const reader = response.body.getReader()
    const decoder = new TextDecoder('utf-8')
    let buffer = ''

    while (true) {
      const { done, value } = await reader.read()
      if (done) break
      
      const chunk = decoder.decode(value, { stream: true })
      buffer += chunk
      
      // 处理 SSE 数据包 (格式: data: {...}\n\n)
      const lines = buffer.split('\n\n')
      buffer = lines.pop() // 保留最后可能不完整的片段

      for (const line of lines) {
        if (line.startsWith('data: ')) {
          const jsonStr = line.slice(6)
          if (jsonStr.trim() === '[DONE]') {
            onDone()
            return
          }
          try {
            const payload = JSON.parse(jsonStr)
            
            // 1. 内容片段
            if (payload.content) {
              onMessage(payload.content)
            }
            
            // 2. 元数据通知 (session_id, user_node_id, ai_node_id, new_title, etc.)
            if (onMeta) {
               // 只要不是纯内容片段，都视为元数据通知给上层
               // 这样以后增加字段不需要修改这里
               if (!payload.content) {
                 onMeta(payload)
               } else {
                 // 如果既有 content 又有其他字段（虽然目前后端逻辑是分开的），也尝试回调
                 // 提取出非 content 的字段
                 const { content, ...metaData } = payload
                 if (Object.keys(metaData).length > 0) {
                    onMeta(metaData)
                 }
               }
            }
          } catch (e) {
            console.warn('非JSON数据:', jsonStr)
          }
        }
      }
    }
    onDone()

  } catch (error) {
    console.error("Stream Error:", error)
    if (onError) onError(error)
  }
}
