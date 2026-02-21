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
  return request({
    url: '/api/auth/login',
    method: 'post',
    data // { username, password }
  })
}

export function anonymousLogin(data) {
  return request({
    url: '/api/auth/anonymous-login',
    method: 'post',
    data
  })
}

export function upgradeAccount(data) {
  return request({
    url: '/api/auth/upgrade-account',
    method: 'post',
    data
  })
}

// 获取当前用户信息 (预留)
export function getMe() { 
  return request({
    url: '/api/users/me', // 假设以后有这个接口
    method: 'get'
  })
}
