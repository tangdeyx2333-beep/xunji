<script setup>
import { RouterView } from 'vue-router'
import { onMounted } from 'vue'
import { anonymousLogin } from '@/api/auth'
import { getOrCreateDeviceId } from '@/utils/deviceFingerprint'

onMounted(async () => {
  const token = localStorage.getItem('access_token')
  if (token) {
    return
  }
  const deviceId = getOrCreateDeviceId()
  try {
    const res = await anonymousLogin({ device_id: deviceId })
    localStorage.setItem('access_token', res.access_token)
    localStorage.setItem('user_info', JSON.stringify({ id: res.user_id, username: res.username }))
    if (res.device_id) {
      localStorage.setItem('device_id', res.device_id)
    }
  } catch (error) {
  }
})
</script>

<template>
  <RouterView />
</template>

<style>
body { margin: 0; padding: 0; }
</style>
