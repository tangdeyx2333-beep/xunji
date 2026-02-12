import request from '@/utils/request'
import { ElMessage } from 'element-plus'

/**
 * 建立 OpenClaw 连接并持久化配置
 * @param {Object} data 连接配置信息
 * @returns {Promise}
 */
export function connectOpenClaw(data) {
  return request({
    url: '/api/openclaw/connect',
    method: 'post',
    data
  })
}


/**
 * 获取 OpenClaw 历史记录
 * @param {string} user_id 用户ID
 * @returns {Promise<Array<{role: string, content: Array<{type: string, text: string}>, timestamp: number}>>}
 */
export function getOpenClawHistory(user_id) {
  return request({
    url: '/api/openclaw/history',
    method: 'get',
    params: { user_id }
  })
}

/**
 * OpenClaw 独立流式对话
 * @param {Object} data 请求数据 { message: string, user_id: string }
 * @param {Function} onMessage 收到消息回调
 * @param {Function} onDone 完成回调
 * @param {Function} onError 错误回调
 */
export async function openClawChatStream(data, onMessage, onDone, onError) {
  try {
    const token = localStorage.getItem('access_token')

    const baseUrl = import.meta.env.VITE_API_BASE_URL
    if (!baseUrl) {
      throw new Error('Missing required env: VITE_API_BASE_URL')
    }
    
    const response = await fetch(`${baseUrl}/api/openclaw/chat`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${token}`
      },
      body: JSON.stringify(data)
    })

    if (!response.ok) {
       if (response.status === 401) ElMessage.error('登录已过期')
       // 读取错误信息
       try {
         const errJson = await response.json()
         if (errJson.detail) {
            throw new Error(errJson.detail)
         }
       } catch (e) {
         // ignore
       }
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
      // 使用更严格的正则或分隔符处理，确保不会因为数据包拼接导致解析失败
      let boundary = buffer.indexOf('\n\n')
      while (boundary !== -1) {
        const line = buffer.slice(0, boundary).trim()
        buffer = buffer.slice(boundary + 2)
        
        if (line.startsWith('data: ')) {
          const jsonStr = line.slice(6).trim()
          if (jsonStr === '[DONE]') {
            onDone()
            return
          }
          try {
            const payload = JSON.parse(jsonStr)
            if (payload.content !== undefined) {
              onMessage(payload.content)
            }
          } catch (e) {
            console.warn('解析流式JSON失败:', e, jsonStr)
          }
        }
        boundary = buffer.indexOf('\n\n')
      }
    }
    onDone()

  } catch (error) {
    console.error("Stream Error:", error)
    if (onError) onError(error)
  }
}
