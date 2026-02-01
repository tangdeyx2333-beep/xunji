// src/api/auth.js
import request from '@/utils/request'

// 注册
export function register(data) {
  return request({
    url: '/api/auth/register',
    method: 'post',
    data // { username, password, email }
  })
}

// 登录
export function login(data) {
  // 注意：OAuth2PasswordRequestForm 期望表单格式，但我们后端如果用 Pydantic 接收 JSON
  // 根据之前的后端代码，我们是用 JSON 接收的 (UserLogin Schema)
  return request({
    url: '/api/auth/login',
    method: 'post',
    data // { username, password }
  })
}

// 获取当前用户信息 (预留)
export function getMe() {
  return request({
    url: '/api/users/me', // 假设以后有这个接口
    method: 'get'
  })
}