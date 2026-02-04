<script setup>
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { ElMessage, ElNotification } from 'element-plus'
import AppLayout from '../components/layout/AppLayout.vue'
import { getAlarmsBySourceId, getDashboardOverlays, getDashboardZones } from '../api/dashboard'
import { getVideo } from '../api/videos'
import { getSources } from '../api/config'
import { getSystemStatus, updateSystemStatus } from '../api/system'
import { getVideoFile } from '../storage/videoStore'

const fallbackBg =
  'https://lh3.googleusercontent.com/aida-public/AB6AXuCXDlvjY7G8IVkVAOOq9Pxd9fMyTbU_H28BFcZu_LIyJ6lo6-k-cu7QIk-8Gnwa3Lo8IcwA9IuUtEarNjXFa3vFvwtmxm4h8XdvzfOX-sZ9_jfh5YTpggRPEDL0m4jKD_IoluE6ye2i66nZeg2qh2I8V1C4q9Qb8UmmbvppC4K7FrAKo3957eIHIUq1Xydj9dZv163NJg5a5xQXMkJ1L8GVtsYYRGLzBycDpTclw9jICDYAdwmvwLXDr6jIBCORa3CE7gV9VKNvRvk'

const userAvatar =
  'https://lh3.googleusercontent.com/aida-public/AB6AXuBw_U7F6T6qfTV8Bm9nj4aOabzd9KgjjATZ21OkZ1YsuuKTkirUCIOJk4AsWQ4_d39X9opwjcZB32_IuWay8QEamkxgzcIBXH0_ZmsB1Xo14f9UWCBCdHNedtJ8LvDICPdrNBcb_PneogAfLsZZwFOuJlvwGxWUwcJHPBTTGyRifBlLfwa-yO2Yph0DGAQlsUVH6uK1rC2QBOFFb_T4QiX2tu4qDHmMEUnDYHzP9vP57TyVYYXe4EV0abzOA2Va3MNVtxpFLSyHNMw'

const loadingVideo = ref(false)
const videoUrl = ref('')
let objectUrl = null // 统一 File/Blob URL 释放

const zones = ref([])
const loadingZones = ref(false)

const sources = ref([])
const currentSourceId = ref('')

const videoWrapRef = ref(null)
const videoRef = ref(null)
const canvasRef = ref(null)

const overlayData = ref(null) // 后端返回的完整 JSON（含 frames）
const overlayFrames = ref([]) // overlayData.frames
const overlayTimestamps = ref([]) // 用于二分查找的时间数组（秒）

// 预处理回放事件（从后端一次性拉取 AlarmEvent）
const allAlarmEvents = ref([]) // [{ id, time, target, severity, thumb, status }]
const alarmCursor = ref(0) // 指向下一个待触发的事件
const realtimeEvents = ref([]) // 右侧面板显示的事件（按触发顺序追加）

const rafId = ref(0)
const resizeObs = ref(null)

const isFullscreen = ref(false)

const currentSourceName = computed(() => {
  const s = sources.value.find((x) => x.id === currentSourceId.value)
  return s?.name || currentSourceId.value || '-'
})

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

const initSource = async () => {
  try {
    sources.value = await getSources()
    const status = await getSystemStatus()
    currentSourceId.value = status.currentSourceId || sources.value[0]?.id || ''
  } catch {
    currentSourceId.value = ''
  }
}

const fetchZones = async () => {
  if (!currentSourceId.value) return
  loadingZones.value = true
  try {
    const resp = await getDashboardZones(currentSourceId.value)
    // axios interceptor 已解包，resp 直接是数组
    zones.value = Array.isArray(resp) ? resp : resp?.data || []
    console.log('[fetchZones] loaded zones count:', zones.value.length)
  } catch (e) {
    console.error('[fetchZones] error:', e)
    zones.value = []
  } finally {
    loadingZones.value = false
  }
}

const fetchAlarmEvents = async () => {
  allAlarmEvents.value = []
  realtimeEvents.value = []
  alarmCursor.value = 0

  if (!currentSourceId.value) return

  try {
    const resp = await getAlarmsBySourceId(currentSourceId.value, 1, 2000)
    const list = resp?.list || resp?.data?.list || []
    const items = Array.isArray(list) ? list : []

    const normalized = items
      .map((x) => ({
        ...x,
        timestamp: Number(x.time || 0),
      }))
      .filter((x) => Number.isFinite(x.timestamp))
      .sort((a, b) => a.timestamp - b.timestamp)

    allAlarmEvents.value = normalized
    console.log('[fetchAlarmEvents] loaded events:', normalized.length)
  } catch (e) {
    console.error('[fetchAlarmEvents] error:', e)
    allAlarmEvents.value = []
  }
}

const loadCurrentVideo = async () => {
  loadingVideo.value = true
  try {
    videoUrl.value = ''

    if (objectUrl) {
      URL.revokeObjectURL(objectUrl)
      objectUrl = null
    }

    if (!currentSourceId.value) {
      ElMessage.warning('暂无视频源，请去视频源管理页设置')
      return
    }

    const detail = await getVideo(currentSourceId.value)

    // 后端当前返回的可访问地址字段为 previewUrl
    if (detail?.previewUrl) {
      videoUrl.value = detail.previewUrl
      return
    }

    // fallback：尝试从本地缓存获取
    const file = await getVideoFile(detail?.id || currentSourceId.value).catch(() => null)
    if (file) {
      objectUrl = URL.createObjectURL(file)
      videoUrl.value = objectUrl
      return
    }

    ElMessage.error('该视频暂无可播放地址')
  } catch (e) {
    ElMessage.error(e?.message || '加载视频失败')
  } finally {
    loadingVideo.value = false
  }
}

const fetchOverlays = async () => {
  overlayData.value = null
  overlayFrames.value = []
  overlayTimestamps.value = []

  if (!currentSourceId.value) {
    console.warn('[fetchOverlays] no currentSourceId')
    return
  }

  try {
    console.log('[fetchOverlays] requesting overlays for sourceId:', currentSourceId.value)
    // 后端支持 video_id/sourceId，这里沿用现有调用传 sourceId
    const resp = await getDashboardOverlays(currentSourceId.value)
    console.log('[fetchOverlays] raw resp:', resp)

    // 兼容后端返回 {code:0, data:{overlays:[...]}} 结构
    // axios interceptor 已解包，所以 resp 直接是 {overlays:[...]}
    const overlays = resp?.overlays || resp?.frames || resp?.data?.overlays || resp?.data?.frames || []
    overlayFrames.value = overlays
    overlayTimestamps.value = overlays.map((f) => Number(f.timestamp || 0))
    overlayData.value = resp

    // 调试：暴露到 window
    window.__overlayFrames = overlays
    console.log('[fetchOverlays] loaded overlays count:', overlays.length)

    // 调试：暴露到 window
    window.__overlayFrames = overlays
    console.log('[fetchOverlays] loaded overlays count:', overlays.length)
  } catch (e) {
    console.error('[fetchOverlays] error:', e)
    // 202：分析未完成；其它错误提示
    const status = e?.response?.status
    if (status === 202) {
      // 静默，等待分析完成后可手动刷新/重进
      overlayData.value = null
      overlayFrames.value = []
      overlayTimestamps.value = []
    } else {
      ElMessage.error(e?.response?.data?.detail || e?.message || '加载 overlays 失败')
    }
  }
}

const ensureCanvasSize = () => {
  const canvas = canvasRef.value
  const wrap = videoWrapRef.value
  if (!canvas || !wrap) return

  const dpr = window.devicePixelRatio || 1
  const w = Math.max(1, wrap.clientWidth)
  const h = Math.max(1, wrap.clientHeight)

  const cw = Math.round(w * dpr)
  const ch = Math.round(h * dpr)

  if (canvas.width !== cw || canvas.height !== ch) {
    canvas.width = cw
    canvas.height = ch
  }

  const ctx = canvas.getContext('2d')
  if (ctx) ctx.setTransform(dpr, 0, 0, dpr, 0, 0)
}

const findNearestFrameIndex = (t) => {
  const arr = overlayTimestamps.value
  const n = arr.length
  if (!n) return -1

  // 二分查找最接近 t 的 index
  let lo = 0
  let hi = n - 1
  while (lo < hi) {
    const mid = Math.floor((lo + hi) / 2)
    if (arr[mid] < t) lo = mid + 1
    else hi = mid
  }

  const i = lo
  if (i <= 0) return 0
  if (i >= n) return n - 1

  const a = arr[i - 1]
  const b = arr[i]
  return Math.abs(t - a) <= Math.abs(t - b) ? i - 1 : i
}

const drawFrame = (frame) => {
  const canvas = canvasRef.value
  const wrap = videoWrapRef.value
  if (!canvas || !wrap) return

  const ctx = canvas.getContext('2d')
  if (!ctx) return

  const w = wrap.clientWidth
  const h = wrap.clientHeight

  ctx.clearRect(0, 0, w, h)

  // 先绘制区域框（来自配置中心），再绘制检测框
  const zs = Array.isArray(zones.value) ? zones.value : []
  for (const z of zs) {
    const pts = z?.polygonPointsNorm || z?.polygonPoints
    if (!Array.isArray(pts) || pts.length < 3) continue

    ctx.beginPath()
    for (let i = 0; i < pts.length; i++) {
      const p = pts[i]
      if (!Array.isArray(p) || p.length < 2) continue
      const px = (Number(p[0]) || 0) * w
      const py = (Number(p[1]) || 0) * h
      if (i === 0) ctx.moveTo(px, py)
      else ctx.lineTo(px, py)
    }
    ctx.closePath()

    const t = z?.type
    ctx.lineWidth = 2
    ctx.strokeStyle = t === 'warning' ? '#f59e0b' : '#ef4444'
    ctx.globalAlpha = 0.9
    ctx.stroke()
    ctx.globalAlpha = 1
  }

  const objects = Array.isArray(frame?.objects) ? frame.objects : []
  console.log('[drawFrame] objects count:', objects.length)
  for (const obj of objects) {
    const box = obj?.box_norm || obj?.box
    if (!box) continue

    const x = Number(box.x || 0) * w
    const y = Number(box.y || 0) * h
    const bw = Number(box.w || 0) * w
    const bh = Number(box.h || 0) * h

    const alarmLevel = obj?.alarm_level
    const isAlarm = alarmLevel === 1 || alarmLevel === 2 || alarmLevel === 'CRITICAL' || alarmLevel === 'WARNING'

    ctx.lineWidth = 2
    ctx.strokeStyle = obj?.color || (isAlarm ? '#ef4444' : '#22c55e')
    console.log('[drawFrame] draw rect', { x, y, bw, bh, color: ctx.strokeStyle })
    ctx.strokeRect(x, y, bw, bh)

    const label = `${obj?.id?.slice?.(0, 8) || ''} ${obj?.class || ''}`.trim()
    if (label) {
      ctx.font = '12px ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, Liberation Mono, Courier New, monospace'
      ctx.fillStyle = 'rgba(0,0,0,0.55)'
      const pad = 4
      const tw = ctx.measureText(label).width
      ctx.fillRect(x, Math.max(0, y - 18), tw + pad * 2, 18)

      ctx.fillStyle = '#fff'
      ctx.fillText(label, x + pad, Math.max(12, y - 5))
    }
  }
}

// 暴露到 window 便于调试
window.__drawFrame = drawFrame

const startRenderLoop = () => {
  cancelRenderLoop()

  const tick = () => {
    rafId.value = requestAnimationFrame(tick)

    const video = videoRef.value
    if (!video || video.paused || video.ended) return

    ensureCanvasSize()

    const frames = overlayFrames.value
    if (!frames.length) return

    const t = Number(video.currentTime || 0)
    const idx = findNearestFrameIndex(t)
    if (idx < 0) return

    const frame = frames[idx]
    drawFrame(frame)

    // 预处理回放：推进告警事件游标并触发通知/右侧列表
    const events = allAlarmEvents.value
    if (events.length) {
      while (alarmCursor.value < events.length && Number(events[alarmCursor.value]?.timestamp || 0) <= t) {
        const ev = events[alarmCursor.value]
        alarmCursor.value += 1

        // 推送到右侧实时事件列表（最新在前）
        realtimeEvents.value.unshift(ev)
        if (realtimeEvents.value.length > 50) realtimeEvents.value.length = 50

        // Notification 弹窗
        const isCritical = ev?.severity === 'critical'
        ElNotification({
          title: isCritical ? '严重告警' : '预警',
          message: `${ev?.target || 'Unknown'} @ ${Number(ev?.timestamp || 0).toFixed(2)}s`,
          type: isCritical ? 'error' : 'warning',
          duration: 3500,
        })
      }
    }
  }

  rafId.value = requestAnimationFrame(tick)
}

const cancelRenderLoop = () => {
  if (rafId.value) {
    cancelAnimationFrame(rafId.value)
    rafId.value = 0
  }
}

const onVideoPlay = () => startRenderLoop()
const onVideoPause = () => {
  cancelRenderLoop()
  // 暂停时保留最后一帧绘制结果，不清空
}
const onVideoSeeked = () => {
  // 拖动进度条时立即绘制一次
  ensureCanvasSize()
  const video = videoRef.value
  if (!video) return
  const frames = overlayFrames.value
  if (!frames.length) return

  const t = Number(video.currentTime || 0)
  const idx = findNearestFrameIndex(t)
  if (idx < 0) return
  drawFrame(frames[idx])
}

const togglePlayPause = () => {
  const video = videoRef.value
  if (!video) return
  if (video.paused) {
    video.play()
  } else {
    video.pause()
  }
}

watch(currentSourceId, async (val, old) => {
  if (!val || val === old) return
  try {
    await updateSystemStatus({ currentSourceId: val })
  } catch {
    // 忽略
  }

  await loadCurrentVideo()
  await fetchOverlays()
  await fetchZones()
  await fetchAlarmEvents()

  await nextTick()
  ensureCanvasSize()
})

onMounted(async () => {
  await initSource()
  await loadCurrentVideo()
  await fetchOverlays()
  await fetchZones()
  await fetchAlarmEvents()

  document.addEventListener('fullscreenchange', syncFullscreenState)

  await nextTick()
  ensureCanvasSize()

  // resize 监听：保持 canvas 分辨率与容器一致
  if (window.ResizeObserver) {
    resizeObs.value = new ResizeObserver(() => ensureCanvasSize())
    if (videoWrapRef.value) resizeObs.value.observe(videoWrapRef.value)
  } else {
    window.addEventListener('resize', ensureCanvasSize)
  }
})

onBeforeUnmount(() => {
  cancelRenderLoop()

  if (objectUrl) URL.revokeObjectURL(objectUrl)
  document.removeEventListener('fullscreenchange', syncFullscreenState)

  if (resizeObs.value) {
    try {
      resizeObs.value.disconnect()
    } catch {
      // ignore
    }
  } else {
    window.removeEventListener('resize', ensureCanvasSize)
  }
})
</script>

<template>
  <AppLayout title="智能周界安全平台" :avatar-url="userAvatar" user-name="Admin User" user-role="系统管理员">
    <div class="dashboard">
      <div ref="videoWrapRef" class="video">
        <div class="video-bg" :style="{ backgroundImage: `url('${fallbackBg}')` }"></div>

        <video
          v-if="videoUrl"
          ref="videoRef"
          class="video-player"
          :src="videoUrl"
          autoplay
          muted
          loop
          playsinline
          @play="onVideoPlay"
          @pause="onVideoPause"
          @seeked="onVideoSeeked"
        />

        <canvas ref="canvasRef" class="overlay-canvas" />

        <div class="video-tag">
          <div class="video-tag-line">{{ currentSourceName }}</div>
          <div class="video-tag-rec">REC ●</div>
        </div>

        <div class="source-switch">
          <el-select v-model="currentSourceId" size="small" class="source-select" :disabled="sources.length === 0">
            <el-option v-for="s in sources" :key="s.id" :label="s.name" :value="s.id" />
          </el-select>
        </div>

        <div v-if="loadingVideo" class="video-loading">加载视频...</div>
        <div v-else-if="!overlayFrames.length" class="video-loading" style="bottom: 46px">分析中或无检测数据</div>
        <div v-if="loadingZones" class="video-loading" style="bottom: 76px">加载区域...</div>

        <div class="crosshair">
          <div class="crosshair-box">
            <div class="crosshair-h"></div>
            <div class="crosshair-v"></div>
          </div>
        </div>
      </div>

      <div class="events">
        <div class="events-header">
          <div class="events-title">实时事件 (Events)</div>
        </div>
        <div class="events-body">
          <div v-if="!realtimeEvents.length" class="empty">暂无事件</div>
          <div v-else class="events-list">
            <div v-for="ev in realtimeEvents" :key="ev.id" class="event-item" :class="ev.severity">
              <div class="event-top">
                <div class="event-id">{{ ev.id }}</div>
                <div class="event-time">{{ Number(ev.timestamp || ev.time || 0).toFixed(2) }}s</div>
              </div>
              <div class="event-bottom">
                <div class="event-target">{{ ev.target }}</div>
                <div class="event-sev">{{ ev.severity }}</div>
              </div>
            </div>
          </div>
        </div>
        <div class="events-footer">
          <router-link class="view-all" to="/history">查看全部告警</router-link>
        </div>
      </div>

      <div class="video-controls">
        <div class="video-controls-left">
          <span class="live">PLAYBACK</span>
        </div>
        <div class="video-controls-right">
          <el-button text class="ctrl-btn small" @click="togglePlayPause">播放/暂停</el-button>
          <el-button text class="ctrl-btn small" @click="fetchOverlays">刷新检测结果</el-button>
          <el-button text class="ctrl-btn small" @click="toggleFullscreen">{{ isFullscreen ? '退出全屏' : 'Fullscreen' }}</el-button>
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
  opacity: 0.95;
}

.overlay-canvas {
  position: absolute;
  inset: 0;
  width: 100%;
  height: 100%;
  z-index: 3;
  pointer-events: none;
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

.ctrl-btn.small {
  font-size: 12px;
  color: #cbd5e1;
}

.live {
  font-size: 12px;
  color: #cbd5e1;
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, 'Liberation Mono', 'Courier New', monospace;
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

.events-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.event-item {
  border: 1px solid #2a3642;
  border-radius: 10px;
  padding: 10px;
  background: rgba(255, 255, 255, 0.04);
}

.event-item.critical {
  border-color: rgba(239, 68, 68, 0.65);
  background: rgba(239, 68, 68, 0.08);
}

.event-item.warning {
  border-color: rgba(245, 158, 11, 0.65);
  background: rgba(245, 158, 11, 0.08);
}

.event-top {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 6px;
}

.event-id {
  font-size: 11px;
  color: #94a3b8;
}

.event-time {
  font-size: 11px;
  color: #9ca3af;
}

.event-bottom {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.event-target {
  font-size: 13px;
  color: #e2e8f0;
  font-weight: 600;
}

.event-sev {
  font-size: 11px;
  text-transform: uppercase;
  color: #cbd5e1;
  padding: 2px 6px;
  border-radius: 999px;
  border: 1px solid rgba(255, 255, 255, 0.12);
  background: rgba(0, 0, 0, 0.15);
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
