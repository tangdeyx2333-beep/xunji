// src/utils/request.js
import axios from 'axios'
import { ElMessage } from 'element-plus'
import { getOrCreateDeviceId } from './deviceFingerprint'

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
    const token = localStorage.getItem('access_token')
    const deviceId = getOrCreateDeviceId()
    config.headers['X-Device-ID'] = deviceId
    if (token) {
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
    return response.data
  },
  (error) => {
    if (error.response) {
      const status = error.response.status
      const msg = error.response.data.detail || '请求失败'
      const requestUrl = error.config?.url || ''
      const isLoginRequest = requestUrl.includes('/api/auth/login')

      if (isLoginRequest) {
        return Promise.reject(error)
      }

      if (status === 401) {
        ElMessage.error('登录已过期，请重新登录')
        localStorage.removeItem('access_token')
        localStorage.removeItem('user_info')
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
