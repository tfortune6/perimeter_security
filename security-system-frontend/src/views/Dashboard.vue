<script setup>
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import AppLayout from '../components/layout/AppLayout.vue'
import { getDashboardEvents, getDashboardOverlays, getDashboardZones } from '../api/dashboard'
import { getDemoVideo } from '../api/videos'
import { getSources } from '../api/config'
import { getSystemStatus, updateSystemStatus } from '../api/system'
import { getVideoFile } from '../storage/videoStore'

const fallbackBg =
  'https://lh3.googleusercontent.com/aida-public/AB6AXuCXDlvjY7G8IVkVAOOq9Pxd9fMyTbU_H28BFcZu_LIyJ6lo6-k-cu7QIk-8Gnwa3Lo8IcwA9IuUtEarNjXFa3vFvwtmxm4h8XdvzfOX-sZ9_jfh5YTpggRPEDL0m4jKD_IoluE6ye2i66nZeg2qh2I8V1C4q9Qb8UmmbvppC4K7FrAKo3957eIHIUq1Xydj9dZv163NJg5a5xQXMkJ1L8GVtsYYRGLzBycDpTclw9jICDYAdwmvwLXDr6jIBCORa3CE7gV9VKNvRvk'

const userAvatar =
  'https://lh3.googleusercontent.com/aida-public/AB6AXuBw_U7F6T6qfTV8Bm9nj4aOabzd9KgjjATZ21OkZ1YsuuKTkirUCIOJk4AsWQ4_d39X9opwjcZB32_IuWay8QEamkxgzcIBXH0_ZmsB1Xo14f9UWCBCdHNedtJ8LvDICPdrNBcb_PneogAfLsZZwFOuJlvwGxWUwcJHPBTTGyRifBlLfwa-yO2Yph0DGAQlsUVH6uK1rC2QBOFFb_T4QiX2tu4qDHmMEUnDYHzP9vP57TyVYYXe4EV0abzOA2Va3MNVtxpFLSyHNMw'

const demoVideo = ref(null)
const loadingVideo = ref(false)
const demoVideoUrl = ref('')
let demoVideoObjectUrl = null

const events = ref([])
const overlays = ref({ boxes: [] })
const zones = ref([])
const loadingEvents = ref(false)
const loadingZones = ref(false)

const sources = ref([])
const currentSourceId = ref('')

let timer = null

const videoWrapRef = ref(null)
const isFullscreen = ref(false)

const fetchDemoVideo = async () => {
  loadingVideo.value = true
  try {
    const video = await getDemoVideo()
    demoVideo.value = video

    if (demoVideoObjectUrl) {
      URL.revokeObjectURL(demoVideoObjectUrl)
      demoVideoObjectUrl = null
    }

    if (video) {
      // 优先从 IndexedDB 取本地文件
      const file = await getVideoFile(video.id)
      if (file) {
        demoVideoObjectUrl = URL.createObjectURL(file)
        demoVideoUrl.value = demoVideoObjectUrl
      } else {
        // 其次用 mock 的 previewUrl
        demoVideoUrl.value = video.previewUrl || ''
      }
    } else {
      demoVideoUrl.value = ''
    }
  } catch {
    demoVideo.value = null
    demoVideoUrl.value = ''
  } finally {
    loadingVideo.value = false
  }
}

const fetchEvents = async () => {
  loadingEvents.value = true
  try {
    events.value = await getDashboardEvents(20)
  } catch (e) {
    ElMessage.error(e?.message || '加载实时事件失败')
  } finally {
    loadingEvents.value = false
  }
}

const fetchOverlays = async () => {
  if (!currentSourceId.value) return
  try {
    overlays.value = await getDashboardOverlays(currentSourceId.value)
  } catch {
    overlays.value = { boxes: [] }
  }
}

const fetchZones = async () => {
  if (!currentSourceId.value) return
  loadingZones.value = true
  try {
    zones.value = await getDashboardZones(currentSourceId.value)
  } catch {
    zones.value = []
  } finally {
    loadingZones.value = false
  }
}

const initSource = async () => {
  try {
    sources.value = await getSources()
    const status = await getSystemStatus()
    currentSourceId.value = status.currentSourceId || sources.value[0]?.id || 'cam1'
  } catch {
    currentSourceId.value = 'cam1'
  }
}

const syncFullscreenState = () => {
  const el = videoWrapRef.value
  if (!el) {
    isFullscreen.value = false
    return
  }
  isFullscreen.value = document.fullscreenElement === el
}

const toggleFullscreen = async () => {
  const el = videoWrapRef.value
  if (!el) return

  try {
    if (document.fullscreenElement) {
      await document.exitFullscreen()
    } else {
      await el.requestFullscreen()
    }
  } catch (e) {
    ElMessage.error(e?.message || '全屏失败')
  }
}

watch(currentSourceId, async (val, old) => {
  if (!val || val === old) return
  try {
    await updateSystemStatus({ currentSourceId: val })
  } catch {
    // 忽略
  }
  await fetchOverlays()
  await fetchZones()
})

onMounted(async () => {
  await initSource()

  await fetchDemoVideo()
  await fetchOverlays()
  await fetchZones()
  await fetchEvents()

  document.addEventListener('fullscreenchange', syncFullscreenState)

  timer = setInterval(async () => {
    await fetchEvents()
    await fetchDemoVideo()

    // 同步视频源列表（上传新视频后，仪表盘下拉可自动出现）
    try {
      const list = await getSources()
      sources.value = list
      if (currentSourceId.value && !list.some((s) => s.id === currentSourceId.value)) {
        currentSourceId.value = list[0]?.id || ''
      }
    } catch {
      // 忽略
    }

    await fetchZones()
  }, 3000)
})

onBeforeUnmount(() => {
  if (timer) clearInterval(timer)
  if (demoVideoObjectUrl) URL.revokeObjectURL(demoVideoObjectUrl)
  document.removeEventListener('fullscreenchange', syncFullscreenState)
})

const levelClass = (lvl) => {
  if (lvl === 'danger') return 'event-danger'
  if (lvl === 'warning') return 'event-warning'
  return 'event-normal'
}

const pillClass = (lvl) => {
  if (lvl === 'danger') return 'pill-danger'
  if (lvl === 'warning') return 'pill-warning'
  return 'pill-normal'
}

const bboxClass = (lvl) => {
  if (lvl === 'danger') return 'bbox-danger'
  if (lvl === 'warning') return 'bbox-warning'
  return 'bbox-success'
}

const zoneClass = (z) => {
  const cls = ['zone']
  if (z.type === 'warning') cls.push('zone-warning')
  else cls.push('zone-core')
  return cls.join(' ')
}

const zonePoints = (z) => (z.polygonPoints || []).map(([x, y]) => `${x},${y}`).join(' ')

const currentSourceName = computed(() => {
  const s = sources.value.find((x) => x.id === currentSourceId.value)
  return s?.name || currentSourceId.value || '-'
})
</script>

<template>
  <AppLayout title="智能周界安全平台" :avatar-url="userAvatar" user-name="Admin User" user-role="系统管理员">
    <div class="dashboard">
      <div ref="videoWrapRef" class="video">
        <div class="video-bg" :style="{ backgroundImage: `url('${fallbackBg}')` }"></div>

        <video
          v-if="demoVideoUrl"
          class="video-player"
          :src="demoVideoUrl"
          autoplay
          muted
          loop
          playsinline
        />

        <div class="video-tag">
          <div class="video-tag-line">{{ currentSourceName }}</div>
          <div class="video-tag-rec">REC ●</div>
        </div>

        <div class="source-switch">
          <el-select v-model="currentSourceId" size="small" class="source-select" :disabled="sources.length === 0">
            <el-option v-for="s in sources" :key="s.id" :label="s.name" :value="s.id" />
          </el-select>
        </div>

        <svg class="zone-layer" viewBox="0 0 800 450" preserveAspectRatio="none">
          <polygon v-for="z in zones" :key="z.id" :points="zonePoints(z)" :class="zoneClass(z)" />
        </svg>

        <div
          v-for="b in overlays.boxes"
          :key="b.id"
          class="bbox"
          :class="bboxClass(b.level)"
          :style="{
            left: `${b.x * 100}%`,
            top: `${b.y * 100}%`,
            width: `${b.w * 100}%`,
            height: `${b.h * 100}%`,
          }"
        >
          <div
            class="bbox-label"
            :class="b.level === 'warning' ? 'bbox-label-warning' : b.level === 'success' ? 'bbox-label-success' : ''"
          >
            {{ b.label }}: {{ Math.round(b.score * 100) }}%
          </div>
        </div>

        <div class="crosshair">
          <div class="crosshair-box">
            <div class="crosshair-h"></div>
            <div class="crosshair-v"></div>
          </div>
        </div>

        <div v-if="loadingVideo" class="video-loading">加载演示源...</div>
        <div v-if="loadingZones" class="video-loading" style="bottom: 46px">加载区域...</div>
      </div>

      <div class="video-controls">
        <div class="video-controls-left">
          <el-button text class="ctrl-btn">▶</el-button>
          <el-button text class="ctrl-btn muted">■</el-button>
          <div class="progress">
            <div class="progress-bar"></div>
            <div class="progress-dot"></div>
          </div>
          <span class="live">LIVE</span>
        </div>
        <div class="video-controls-right">
          <el-button text class="ctrl-btn small" :loading="loadingVideo" @click="fetchDemoVideo">刷新演示源</el-button>
          <el-button text class="ctrl-btn small" :loading="loadingZones" @click="fetchZones">刷新区域</el-button>
          <el-button text class="ctrl-btn small" @click="toggleFullscreen">{{ isFullscreen ? '退出全屏' : 'Fullscreen' }}</el-button>
        </div>
      </div>

      <div class="events">
        <div class="events-header">
          <div class="events-title">实时事件 (Events)</div>
          <el-button text class="ctrl-btn small" :loading="loadingEvents" @click="fetchEvents">刷新</el-button>
        </div>
        <div class="events-body" v-loading="loadingEvents">
          <router-link
            v-for="e in events"
            :key="e.id"
            class="event"
            :class="levelClass(e.level)"
            :to="{ path: '/history', query: { alarmId: e.alarmId } }"
          >
            <div class="event-top">
              <span class="pill" :class="pillClass(e.level)">{{ e.type }}</span>
              <span class="event-time">{{ e.time }}</span>
            </div>
            <div class="event-content">
              <div class="event-thumb" :style="{ backgroundImage: `url('${e.thumbUrl}')` }"></div>
              <div class="event-text">
                <div class="event-name">{{ e.type === 'INTRUSION' ? '非法入侵检测' : '实时事件' }}</div>
                <div class="event-zone">{{ e.zone }}</div>
              </div>
            </div>
          </router-link>

          <div v-if="!loadingEvents && events.length === 0" class="empty">暂无实时事件</div>
        </div>
        <div class="events-footer">
          <router-link class="view-all" to="/history">查看全部告警</router-link>
        </div>
      </div>
    </div>
  </AppLayout>
</template>

<style scoped>
.dashboard {
  height: 100%;
  display: grid;
  grid-template-columns: 1fr 320px;
  grid-template-rows: 1fr 48px;
  grid-template-areas:
    'video events'
    'controls events';
  background: #000;
}

.video {
  grid-area: video;
  position: relative;
  overflow: hidden;
  background: #111;
}

.video-bg {
  position: absolute;
  inset: 0;
  background-size: cover;
  background-position: center;
  opacity: 0.9;
}

.video-player {
  position: absolute;
  inset: 0;
  width: 100%;
  height: 100%;
  object-fit: cover;
  opacity: 0.9;
}

.zone-layer {
  position: absolute;
  inset: 0;
  width: 100%;
  height: 100%;
  z-index: 2;
  pointer-events: none;
}

.zone {
  stroke-width: 2;
}

.zone-core {
  fill: rgba(239, 68, 68, 0.14);
  stroke: rgba(239, 68, 68, 0.75);
}

.zone-warning {
  fill: rgba(245, 158, 11, 0.12);
  stroke: rgba(245, 158, 11, 0.75);
}

.source-switch {
  position: absolute;
  top: 12px;
  right: 12px;
  z-index: 4;
}

.source-select {
  width: 200px;
}

.video-loading {
  position: absolute;
  left: 16px;
  bottom: 16px;
  z-index: 4;
  padding: 6px 10px;
  border-radius: 8px;
  background: rgba(0, 0, 0, 0.6);
  border: 1px solid rgba(255, 255, 255, 0.1);
  color: #cbd5e1;
  font-size: 12px;
}

.video-tag {
  position: absolute;
  top: 16px;
  left: 16px;
  display: flex;
  flex-direction: column;
  gap: 6px;
  z-index: 4;
}

.video-tag-line {
  background: rgba(0, 0, 0, 0.6);
  border: 1px solid rgba(255, 255, 255, 0.1);
  padding: 4px 8px;
  border-radius: 6px;
  font-size: 12px;
  color: #fff;
}

.video-tag-rec {
  display: inline-block;
  width: fit-content;
  background: #ef4444;
  padding: 4px 8px;
  border-radius: 6px;
  font-size: 12px;
  font-weight: 700;
  color: #fff;
}

.bbox {
  position: absolute;
  border: 2px solid;
  z-index: 5;
}
.bbox-danger {
  border-color: #ef4444;
  box-shadow: 0 0 15px rgba(239, 68, 68, 0.5);
}
.bbox-warning {
  border-color: #f59e0b;
  box-shadow: 0 0 10px rgba(245, 158, 11, 0.4);
}
.bbox-success {
  border-color: #10b981;
  box-shadow: 0 0 10px rgba(16, 185, 129, 0.4);
}
.bbox-label {
  position: absolute;
  top: -28px;
  left: 0;
  background: #ef4444;
  color: #fff;
  font-size: 10px;
  font-weight: 700;
  padding: 4px 8px;
  border-radius: 4px 4px 0 0;
}
.bbox-label-warning {
  background: #f59e0b;
  color: #111;
}
.bbox-label-success {
  background: #10b981;
}

.crosshair {
  position: absolute;
  inset: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  pointer-events: none;
  opacity: 0.3;
  z-index: 4;
}
.crosshair-box {
  width: 32px;
  height: 32px;
  border: 1px solid rgba(255, 255, 255, 0.5);
  position: relative;
}
.crosshair-h {
  position: absolute;
  top: 50%;
  left: 0;
  right: 0;
  height: 1px;
  background: rgba(255, 255, 255, 0.5);
}
.crosshair-v {
  position: absolute;
  left: 50%;
  top: 0;
  bottom: 0;
  width: 1px;
  background: rgba(255, 255, 255, 0.5);
}

.video-controls {
  grid-area: controls;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 12px;
  background: #1c252e;
  border-top: 1px solid #2a3642;
}
.video-controls-left,
.video-controls-right {
  display: flex;
  align-items: center;
  gap: 10px;
}
.ctrl-btn {
  color: #fff;
}
.ctrl-btn.muted {
  color: #9dabb9;
}
.ctrl-btn.small {
  font-size: 12px;
  color: #cbd5e1;
}
.progress {
  position: relative;
  width: 120px;
  height: 6px;
  background: #334155;
  border-radius: 999px;
}
.progress-bar {
  position: absolute;
  inset: 0;
  background: #137fec;
  border-radius: 999px;
}
.progress-dot {
  position: absolute;
  right: -2px;
  top: 50%;
  transform: translateY(-50%);
  width: 12px;
  height: 12px;
  background: #fff;
  border-radius: 999px;
}
.live {
  font-size: 12px;
  color: #cbd5e1;
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, 'Liberation Mono',
    'Courier New', monospace;
}

.events {
  grid-area: events;
  display: flex;
  flex-direction: column;
  background: #1c252e;
  border-left: 1px solid #2a3642;
}
.events-header {
  height: 52px;
  padding: 0 12px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  border-bottom: 1px solid #2a3642;
}
.events-title {
  font-size: 13px;
  font-weight: 700;
  color: #fff;
}
.events-body {
  flex: 1;
  overflow: auto;
  padding: 12px;
}
.event {
  display: block;
  padding: 12px;
  border-radius: 10px;
  border: 1px solid #2a3642;
  background: #101922;
  color: inherit;
  text-decoration: none;
}
.event + .event {
  margin-top: 12px;
}
.event-danger {
  border-color: rgba(239, 68, 68, 0.3);
}
.event-warning {
  border-color: rgba(245, 158, 11, 0.3);
}
.event-normal {
  border-color: rgba(148, 163, 184, 0.25);
}
.event-top {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 10px;
}
.pill {
  font-size: 10px;
  font-weight: 800;
  padding: 2px 8px;
  border-radius: 999px;
  border: 1px solid transparent;
}
.pill-danger {
  color: #ef4444;
  background: rgba(239, 68, 68, 0.2);
  border-color: rgba(239, 68, 68, 0.2);
}
.pill-warning {
  color: #f59e0b;
  background: rgba(245, 158, 11, 0.2);
  border-color: rgba(245, 158, 11, 0.2);
}
.pill-normal {
  color: #94a3b8;
  background: rgba(148, 163, 184, 0.12);
  border-color: rgba(148, 163, 184, 0.12);
}
.event-time {
  font-size: 12px;
  color: #94a3b8;
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, 'Liberation Mono',
    'Courier New', monospace;
}
.event-content {
  display: flex;
  gap: 10px;
}
.event-thumb {
  width: 64px;
  height: 64px;
  border-radius: 8px;
  background-size: cover;
  background-position: center;
  border: 1px solid #2a3642;
}
.event-text {
  display: flex;
  flex-direction: column;
  justify-content: center;
  gap: 6px;
}
.event-name {
  font-size: 14px;
  font-weight: 600;
  color: #fff;
}
.event-zone {
  font-size: 12px;
  color: #94a3b8;
}
.events-footer {
  padding: 12px;
  border-top: 1px solid #2a3642;
}
.view-all {
  display: block;
  text-align: center;
  padding: 8px;
  border-radius: 8px;
  background: #1f2937;
  color: #cbd5e1;
  text-decoration: none;
  font-size: 12px;
}
.empty {
  padding: 12px;
  color: #9dabb9;
}
</style>
