<script setup>
import { ref, reactive } from 'vue'
import { useRouter } from 'vue-router'
import { register } from '@/api/auth' // 直接调 API 简单点
import { User, Lock, Message } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'

const router = useRouter()
const loading = ref(false)

const form = reactive({
  username: '',
  password: '',
  email: ''
})

const handleRegister = async () => {
  if (!form.username || !form.password) {
    return ElMessage.warning('请填写必填项')
  }

  loading.value = true
  try {
    // 调用后端注册接口
    await register(form)
    ElMessage.success('注册成功，请登录')
    router.push('/login') // 注册完跳去登录
  } catch (err) {
    // 错误已经在 request.js 里拦截提示了，这里不用处理
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <div class="auth-container">
    <el-card class="auth-card">
      <template #header>
        <div class="auth-header">
          <h2>创建账号</h2>
          <p>加入 Nova AI 社区</p>
        </div>
      </template>

      <el-form :model="form">
        <el-form-item>
          <el-input v-model="form.username" placeholder="用户名 (必填)" :prefix-icon="User" size="large" />
        </el-form-item>
        
        <el-form-item>
          <el-input v-model="form.email" placeholder="邮箱 (选填)" :prefix-icon="Message" size="large" />
        </el-form-item>

        <el-form-item>
          <el-input v-model="form.password" type="password" placeholder="密码 (必填)" :prefix-icon="Lock" size="large" show-password />
        </el-form-item>
        
        <el-button type="primary" class="submit-btn" :loading="loading" @click="handleRegister" size="large" round>
          注册
        </el-button>

        <div class="auth-footer">
          <span>已有账号？</span>
          <el-link type="primary" @click="router.push('/login')">去登录</el-link>
        </div>
      </el-form>
    </el-card>
  </div>
</template>

<style scoped lang="scss">
/* 直接复用 Login.vue 的样式，保持一致 */
.auth-container {
  height: 100vh;
  display: flex;
  justify-content: center;
  align-items: center;
  background-color: #f0f2f5;
}
.auth-card {
  width: 400px;
  border-radius: 12px;
  .auth-header { text-align: center; h2 { margin-bottom: 5px; } p { color: #666; font-size: 14px; margin: 0; } }
  .submit-btn { width: 100%; margin-top: 10px; font-weight: bold; }
  .auth-footer { margin-top: 20px; text-align: center; display:flex; justify-content: center; gap: 5px; font-size: 14px;}
}
</style>