import { createRouter, createWebHistory } from 'vue-router'
import GeminiLayout from '../views/GeminiLayout.vue'
import Login from '../views/Login.vue'
import Register from '../views/Register.vue'

const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes: [
    {
      path: '/',
      name: 'home',
      component: GeminiLayout,
      meta: { requiresAuth: true } // ★ 标记：这个页面需要登录才能看
    },
    {
      path: '/login',
      name: 'login',
      component: Login
    },
    {
      path: '/register',
      name: 'register',
      component: Register
    }
  ]
})

// --- 路由守卫 (全局拦截器) ---
router.beforeEach((to, from, next) => {
  // 1. 获取 Token
  const token = localStorage.getItem('access_token')

  // 2. 检查目标路由是否需要登录
  if (to.meta.requiresAuth) {
    if (token) {
      // 有 Token，放行
      next()
    } else {
      // 没 Token，强制去登录页
      next('/login')
    }
  } else {
    // 不需要登录的页面 (Login/Register)，直接放行
    next()
  }
})

export default router