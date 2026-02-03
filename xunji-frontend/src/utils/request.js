// src/utils/request.js
import axios from 'axios'
import { ElMessage } from 'element-plus'

// const apiBaseUrl = import.meta.env.VITE_API_BASE_URL
const apiBaseUrl = import.meta.env.VITE_API_BASE_URL
if (!apiBaseUrl) {
  throw new Error('Missing required env: VITE_API_BASE_URL')
}

// 1. 创建 axios 实例
const service = axios.create({
  // 这里的地址要和你的 FastAPI 后端地址一致
  baseURL: apiBaseUrl,
  timeout: 50000 // 请求超时时间 (50秒，因为 AI 回复有时较慢)
})

// 2. 请求拦截器 (自动带 Token)
service.interceptors.request.use(
  (config) => {
    // 从 localStorage 获取 token
    const token = localStorage.getItem('access_token')
    if (token) {
      // 按照 OAuth2 标准，Header 格式为 "Bearer <token>"
      config.headers['Authorization'] = `Bearer ${token}`
    }
    return config
  },
  (error) => {
    return Promise.reject(error)
  }
)

// 3. 响应拦截器 (统一处理错误)
service.interceptors.response.use(
  (response) => {
    // 如果后端直接返回数据，这里直接返回 response.data
    return response.data
  },
  (error) => {
    // 处理 HTTP 错误状态码
    if (error.response) {
      const status = error.response.status
      const msg = error.response.data.detail || '请求失败'

      if (status === 401) {
        // Token 过期或未登录
        ElMessage.error('登录已过期，请重新登录')
        localStorage.removeItem('access_token') // 清除失效 Token
        localStorage.removeItem('user_info')
        // 强制刷新页面或跳转到登录页 (简单粗暴但有效)
        setTimeout(() => {
           window.location.href = '/login'
        }, 1000)
      } else {
        ElMessage.error(msg)
      }
    } else {
      ElMessage.error('网络连接异常，请检查后端服务是否启动')
    }
    return Promise.reject(error)
  }
)

export default service
