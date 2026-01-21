<script setup>
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessageBox } from 'element-plus'
import { Camera, Clock, HomeFilled, Setting, UserFilled } from '@element-plus/icons-vue'

const props = defineProps({
  title: { type: String, default: '智能周界安全平台' },
  avatarUrl: { type: String, default: '' },
  userName: { type: String, default: '管理员' },
  userRole: { type: String, default: '' },
})

const route = useRoute()
const router = useRouter()

const clock = ref('')
let timer = null

const active = computed(() => route.path)

const menu = [
  { path: '/', label: '仪表盘 (Dashboard)', icon: HomeFilled },
  { path: '/config', label: '配置中心', icon: Setting },
  { path: '/history', label: '报警记录', icon: Clock },
  { path: '/sources', label: '视频源管理', icon: Camera },
]

const updateClock = () => {
  const d = new Date()
  clock.value = d.toLocaleTimeString()
}

onMounted(() => {
  updateClock()
  timer = setInterval(updateClock, 1000)
})

onBeforeUnmount(() => {
  if (timer) clearInterval(timer)
})

const go = (path) => {
  router.push(path)
}

const logout = async () => {
  try {
    await ElMessageBox.confirm('确认退出登录？', '提示', {
      confirmButtonText: '退出',
      cancelButtonText: '取消',
      type: 'warning',
    })
  } catch {
    return
  }

  localStorage.removeItem('token')
  router.replace('/login')
}
</script>

<template>
  <div class="app">
    <header class="topbar">
      <div class="brand">
        <div class="brand-icon">
          <el-icon size="18"><UserFilled /></el-icon>
        </div>
        <div class="brand-title">{{ props.title }}</div>
      </div>

      <div class="topbar-right">
        <div class="clock">
          <span class="clock-ico">⏱</span>
          <span class="clock-text">{{ clock }}</span>
          <span class="clock-sep">|</span>
          <span class="clock-date">2023-10-27</span>
        </div>

        <div class="user" @click="logout">
          <div class="avatar" :style="props.avatarUrl ? { backgroundImage: `url('${props.avatarUrl}')` } : {}"></div>
          <div class="user-text">
            <div class="user-name">{{ props.userName }}</div>
            <div class="user-role">{{ props.userRole }}</div>
          </div>
          <div class="user-more">退出</div>
        </div>
      </div>
    </header>

    <div class="body">
      <aside class="sidebar">
        <div class="nav">
          <div
            v-for="item in menu"
            :key="item.path"
            class="nav-item"
            :class="{ active: active === item.path }"
            @click="go(item.path)"
          >
            <div class="nav-ico">
              <el-icon size="18"><component :is="item.icon" /></el-icon>
            </div>
            <div class="nav-label">{{ item.label }}</div>
            <div v-if="item.path === '/history' && active !== '/history'" class="badge">9+</div>
          </div>
        </div>

        <div class="sidebar-footer">
          <div class="storage">
            <div class="storage-top">
              <span class="storage-label">系统存储</span>
              <span class="storage-val">75%</span>
            </div>
            <div class="storage-bar">
              <div class="storage-bar-in" />
            </div>
          </div>
        </div>
      </aside>

      <main class="content">
        <slot />
      </main>
    </div>

    <footer class="footer">
      <div class="footer-left">
        <span class="dot" />
        <span class="footer-text">System Online</span>
        <span class="footer-sep">|</span>
        <span class="footer-text">Source: CAM-01</span>
        <span class="footer-sep">|</span>
        <span class="footer-text">FPS: 24</span>
      </div>
      <div class="footer-right">
        <span class="footer-ver">v2.4.1 (Stable)</span>
      </div>
    </footer>
  </div>
</template>

<style scoped>
.app {
  height: 100vh;
  width: 100vw;
  overflow: hidden;
  background: #101922;
  color: #fff;
  display: flex;
  flex-direction: column;
}

.topbar {
  height: 64px;
  flex: 0 0 auto;
  background: #1c252e;
  border-bottom: 1px solid #2a3642;
  padding: 0 16px;
  display: flex;
  align-items: center;
  justify-content: space-between;
}
.brand {
  display: flex;
  align-items: center;
  gap: 12px;
}
.brand-icon {
  width: 32px;
  height: 32px;
  border-radius: 8px;
  background: rgba(19, 127, 236, 0.2);
  color: #137fec;
  display: flex;
  align-items: center;
  justify-content: center;
}
.brand-title {
  font-size: 16px;
  font-weight: 800;
  letter-spacing: 0.2px;
}

.topbar-right {
  display: flex;
  align-items: center;
  gap: 16px;
}
.clock {
  display: none;
  align-items: center;
  gap: 8px;
  font-size: 12px;
  color: #9dabb9;
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, 'Liberation Mono',
    'Courier New', monospace;
}
@media (min-width: 900px) {
  .clock {
    display: flex;
  }
}
.clock-ico {
  font-size: 14px;
}
.clock-sep {
  opacity: 0.6;
}

.user {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 4px 8px;
  border-radius: 10px;
  cursor: pointer;
}
.user:hover {
  background: rgba(255, 255, 255, 0.05);
}
.avatar {
  width: 32px;
  height: 32px;
  border-radius: 999px;
  background: #334155;
  background-size: cover;
  background-position: center;
}
.user-text {
  display: none;
}
@media (min-width: 1100px) {
  .user-text {
    display: block;
  }
}
.user-name {
  font-size: 13px;
  font-weight: 700;
  line-height: 1.1;
}
.user-role {
  margin-top: 2px;
  font-size: 12px;
  color: #9dabb9;
}
.user-more {
  color: #9dabb9;
}

.body {
  flex: 1 1 auto;
  min-height: 0;
  display: flex;
}

.sidebar {
  width: 256px;
  background: #101922;
  border-right: 1px solid #2a3642;
  flex: 0 0 auto;
  display: flex;
  flex-direction: column;
}

.nav {
  flex: 1 1 auto;
  min-height: 0;
  padding: 12px;
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.nav-item {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px 12px;
  border-radius: 10px;
  color: #94a3b8;
  cursor: pointer;
  user-select: none;
}
.nav-item:hover {
  color: #fff;
  background: rgba(255, 255, 255, 0.05);
}
.nav-item.active {
  background: #137fec;
  color: #fff;
  box-shadow: 0 10px 24px rgba(19, 127, 236, 0.2);
}
.nav-ico {
  width: 18px;
  text-align: center;
}
.nav-label {
  font-size: 13px;
  font-weight: 600;
}
.badge {
  margin-left: auto;
  background: #ef4444;
  color: #fff;
  font-size: 10px;
  font-weight: 800;
  padding: 2px 6px;
  border-radius: 999px;
}

.sidebar-footer {
  flex: 0 0 auto;
  border-top: 1px solid #2a3642;
  padding: 12px;
}
.storage {
  background: rgba(51, 65, 85, 0.25);
  border-radius: 10px;
  padding: 10px;
}
.storage-top {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 8px;
  font-size: 12px;
}
.storage-label {
  color: #9dabb9;
}
.storage-val {
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, 'Liberation Mono',
    'Courier New', monospace;
}
.storage-bar {
  height: 6px;
  background: #334155;
  border-radius: 999px;
  overflow: hidden;
}
.storage-bar-in {
  width: 75%;
  height: 100%;
  background: #137fec;
}

.content {
  flex: 1 1 auto;
  min-width: 0;
  min-height: 0;
  background: #000;
}

.footer {
  height: 32px;
  flex: 0 0 auto;
  background: rgba(19, 127, 236, 0.1);
  border-top: 1px solid rgba(19, 127, 236, 0.2);
  padding: 0 12px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  font-size: 11px;
  color: #9dabb9;
  user-select: none;
}
.footer-left {
  display: flex;
  align-items: center;
  gap: 10px;
}
.dot {
  width: 8px;
  height: 8px;
  border-radius: 999px;
  background: #10b981;
}
.footer-text {
  color: #cbd5e1;
}
.footer-sep {
  opacity: 0.5;
}
.footer-right {
  color: #137fec;
}
</style>
