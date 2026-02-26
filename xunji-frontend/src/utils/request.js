// src/utils/request.js
import axios from 'axios'
import { ElMessage, ElNotification } from 'element-plus'
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
      console.log('全局错误捕获:', error)
      if (error.response) {
        const status = error.response.status
        const detail = error.response.data?.detail
        
        console.log(`HTTP ${status} Error:`, detail)

        let message = '请求失败'
        if (typeof detail === 'string') {
          message = detail
        } else if (typeof detail === 'object' && detail !== null) {
          // 处理 FastAPI 校验错误
          message = JSON.stringify(detail)
        } else if (error.message) {
          message = error.message
        }
        
        console.log('解析后的错误消息:', message)

        // 401 单独处理
        if (status === 401) {
          // 清除 token
          localStorage.removeItem('access_token')
          // 对于账号恢复/登录场景，401 代表用户名或密码错误，需要弹窗提示
          ElNotification.error({
             title: '认证失败',
             message: message || '用户名或密码错误',
             position: 'top-right'
          })
          return Promise.reject(error)
        }
        
        // 400 错误处理 (通常是业务逻辑错误，如重复添加)
        if (status === 400) {
           console.log('触发 400 错误弹窗逻辑')
           ElNotification.error({
             title: '操作失败',
             message: message,
             position: 'top-right'
           })
           return Promise.reject(error)
        }

        // 422 参数校验错误，通常是前端传参问题
        if (status === 422) {
           console.log('触发 422 错误弹窗逻辑')
           ElNotification.error({
             title: '参数校验失败',
             message: message,
             position: 'top-right'
           })
           return Promise.reject(error)
        }

        // 其它错误弹窗
        console.log('触发通用错误弹窗逻辑')
        ElNotification.error({
          title: '错误',
          message: message,
          position: 'top-right'
        })
        return Promise.reject(error)
      } else {
        console.log('触发网络错误弹窗逻辑')
        ElNotification.error({
          title: '网络错误',
          message: '网络连接异常，请检查后端服务是否启动',
          position: 'top-right'
        })
        return Promise.reject(error)
      }
  }
)

export default service
