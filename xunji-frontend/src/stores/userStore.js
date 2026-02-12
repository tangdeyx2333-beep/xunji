// src/stores/userStore.js
import { defineStore } from 'pinia'
import { ref } from 'vue'
import { login as loginApi, register as registerApi } from '@/api/auth'

export const useUserStore = defineStore('user', () => {
  // --- State ---
  // 优先从 localStorage 读取，防止刷新页面后状态丢失
  const token = ref(localStorage.getItem('access_token') || '')
  const userInfo = ref(JSON.parse(localStorage.getItem('user_info') || '{}'))

  // --- Actions ---
  
  // 1. 登录动作
  const login = async (loginForm) => {
    try {
      const res = await loginApi(loginForm)
      token.value = res.access_token
      userInfo.value = { id: res.user_id, username: res.username }
      localStorage.setItem('access_token', res.access_token)
      localStorage.setItem('user_info', JSON.stringify(userInfo.value))
      if (res.device_id) {
        localStorage.setItem('device_id', res.device_id)
      }
      
      return { success: true }
    } catch (error) {
      const status = error?.response?.status
      const detail = error?.response?.data?.detail
      const message = status === 401 ? '用户名或密码错误' : (detail || '登录失败，请稍后再试')
      return { success: false, message }
    }
  }

  // 2. 注册动作
  const register = async (registerForm) => {
    try {
      await registerApi(registerForm)
      return true
    } catch (error) {
      return false
    }
  }

  // 3. 退出登录
  const logout = () => {
    token.value = ''
    userInfo.value = {}
    localStorage.removeItem('access_token')
    localStorage.removeItem('user_info')
    // 可以在这里做路由跳转，或者在组件里做
  }

  return {
    token,
    userInfo,
    login,
    register,
    logout
  }
})
