<script setup>
import { ref, reactive } from 'vue'
import { useRouter } from 'vue-router'
import { useUserStore } from '@/stores/userStore'
import { User, Lock } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'

const router = useRouter()
const userStore = useUserStore()

const loading = ref(false)
const loginForm = reactive({
  username: '',
  password: ''
})

const handleLogin = async () => {
  if (!loginForm.username || !loginForm.password) {
    ElMessage.warning('请输入用户名和密码')
    return
  }
  
  loading.value = true
  // 调用我们在 store 里写好的 login action
  const success = await userStore.login(loginForm)
  loading.value = false

  if (success) {
    ElMessage.success('登录成功')
    router.push('/') // 跳转到主页 (Chat)
  }
}
</script>

<template>
  <div class="auth-container">
    <el-card class="auth-card">
      <template #header>
        <div class="auth-header">
          <h2>欢迎回来</h2>
          <p>登录 Nova AI 开始对话</p>
        </div>
      </template>

      <el-form :model="loginForm" @keyup.enter="handleLogin">
        <el-form-item>
          <el-input 
            v-model="loginForm.username" 
            placeholder="用户名" 
            :prefix-icon="User" 
            size="large"
          />
        </el-form-item>
        <el-form-item>
          <el-input 
            v-model="loginForm.password" 
            type="password" 
            placeholder="密码" 
            :prefix-icon="Lock" 
            size="large"
            show-password
          />
        </el-form-item>
        
        <el-button 
          type="primary" 
          class="submit-btn" 
          :loading="loading" 
          @click="handleLogin" 
          size="large" 
          round
        >
          立即登录
        </el-button>

        <div class="auth-footer">
          <span>还没有账号？</span>
          <el-link type="primary" @click="router.push('/register')">去注册</el-link>
        </div>
      </el-form>
    </el-card>
  </div>
</template>

<style scoped lang="scss">
.auth-container {
  height: 100vh;
  display: flex;
  justify-content: center;
  align-items: center;
  background-color: #f0f2f5; /* 浅灰背景 */
}

.auth-card {
  width: 400px;
  border-radius: 12px;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.08);

  .auth-header {
    text-align: center;
    h2 { margin: 0 0 10px; color: #333; }
    p { margin: 0; color: #666; font-size: 14px; }
  }
  
  .submit-btn {
    width: 100%;
    margin-top: 10px;
    font-weight: bold;
    font-size: 16px;
  }

  .auth-footer {
    margin-top: 20px;
    text-align: center;
    font-size: 14px;
    color: #666;
    display: flex;
    justify-content: center;
    gap: 5px;
  }
}
</style>