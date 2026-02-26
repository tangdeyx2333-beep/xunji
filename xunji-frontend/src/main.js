import { createApp } from 'vue'
import { createPinia } from 'pinia'
import 'element-plus/dist/index.css' // 显式引入 Element Plus 样式

import App from './App.vue'
import router from './router'

const app = createApp(App)

app.use(createPinia())
app.use(router)

app.mount('#app')
