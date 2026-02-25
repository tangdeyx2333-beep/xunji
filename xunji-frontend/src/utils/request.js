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
      // 统一错误处理
      if (error.response) {
        const status = error.response.status
        const detail = error.response.data?.detail
        
        let message = '请求失败'
        if (typeof detail === 'string') {
          message = detail
        } else if (typeof detail === 'object' && detail !== null) {
          // 处理 FastAPI 校验错误
          message = JSON.stringify(detail)
        } else if (error.message) {
          message = error.message
        }
        
        // 401 单独处理，避免重复弹窗
        if (status === 401) {
          // 可选：清除 token，但让业务层决定是否跳转
          localStorage.removeItem('access_token')
          return Promise.reject(error)
        }
        
        // 422 参数校验错误，通常是前端传参问题
        if (status === 422) {
           ElMessage.error(`参数校验失败: ${message}`)
           return Promise.reject(error)
        }

        // 其它错误弹窗
        ElMessage.error(message)
        return Promise.reject(error)
      } else {
        ElMessage.error('网络连接异常，请检查后端服务是否启动')
        return Promise.reject(error)
      }
  }
)

export default service
