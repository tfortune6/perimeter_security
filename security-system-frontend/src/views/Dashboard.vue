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
const zoneNameById = computed(() => {
  const map = Object.create(null)
  const list = Array.isArray(zones.value) ? zones.value : []
  for (const z of list) {
    const id = z?.id ?? z?.zone_id ?? z?.zoneId
    const name = z?.name ?? z?.zone_name ?? z?.zoneName
    if (id != null && name) map[String(id)] = String(name)
  }
  return map
})
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
const isVideoEnded = ref(false)

const formatSecondsToMMSS = (seconds) => {
  const s = Math.max(0, Math.floor(Number(seconds || 0)))
  const mm = String(Math.floor(s / 60)).padStart(2, '0')
  const ss = String(s % 60).padStart(2, '0')
  return `${mm}:${ss}`
}

const formatEventTime = (ev) => {
  if (!ev) return '00:00'
  if (typeof ev.timestamp === 'string' && ev.timestamp.includes(':')) return ev.timestamp
  const t = Number(ev.timestamp ?? ev.time ?? 0)
  return formatSecondsToMMSS(t)
}

const getEventTargetType = (ev) => {
  const typeStr = String(ev?.targetType || ev?.object_type || ev?.target || '').toUpperCase()
  if (typeStr.includes('PERSON')) return 'PERSON'
  if (typeStr.includes('VEHICLE') || typeStr.includes('CAR')) return 'VEHICLE'
  return 'UNKNOWN' // or a default type
}

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
    window.__zones = zones.value // 调试用，可删除
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
    const pageSize = 100
    const maxPages = 50 // 最多拉取 5000 条，避免无限循环

    let page = 1
    const collected = []

    while (page <= maxPages) {
      const resp = await getAlarmsBySourceId(currentSourceId.value, page, pageSize)
      // axios interceptor 已解包，resp 可能是 {list,total} 或者直接是数组
      const raw = resp?.list || resp?.data?.list || resp?.data?.data?.list || resp?.data || resp
      const items = Array.isArray(raw) ? raw : []

      if (!items.length) break

      for (const it of items) {
        if (String(it?.videoId || '') === String(currentSourceId.value)) {
          collected.push(it)
        }
      }

      // 如果这一页已经不足 pageSize，认为到尾
      if (items.length < pageSize) break
      page += 1
    }

    const normalized = collected
      .map((x) => ({
        ...x,
        timestamp: Number(x.time || 0),
      }))
      .filter((x) => Number.isFinite(x.timestamp))
      .sort((a, b) => a.timestamp - b.timestamp)

    allAlarmEvents.value = normalized
    console.log('[fetchAlarmEvents] loaded events:', normalized.length)
    // 调试：暴露到 window
    window.__allAlarmEvents = normalized
  } catch (e) {
    console.error('[fetchAlarmEvents] error:', e)
    allAlarmEvents.value = []
    window.__allAlarmEvents = []
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
    let overlays = resp?.overlays || resp?.frames || resp?.data?.overlays || resp?.data?.frames || []

    // 修复：清洗/排序 timestamp，避免前几秒 timestamp=0/NaN 导致二分查找匹配失败
    overlays = Array.isArray(overlays) ? overlays : []
    overlays = overlays
      .map((f) => {
        const ts = Number(f?.timestamp)
        return { ...f, __ts: Number.isFinite(ts) ? ts : null }
      })
      .filter((f) => f.__ts !== null)
      .sort((a, b) => a.__ts - b.__ts)
      .map(({ __ts, ...rest }) => rest)

    overlayFrames.value = overlays
    overlayTimestamps.value = overlays.map((f) => Number(f.timestamp))
    overlayData.value = resp

    // 调试：打印前10个时间戳，确认从 0 开始递增
    console.log('[fetchOverlays] first10 timestamps:', overlayTimestamps.value.slice(0, 10))

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

    // loop/回退检测：currentTime 变小表示重新开始播放
    if (typeof tick.__lastT === 'number' && t + 0.05 < tick.__lastT) {
      alarmCursor.value = 0
      realtimeEvents.value = []
    }
    tick.__lastT = t

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

        // 事件去重/节流：同一 (target + severity) 在短时间窗口内只触发一次
        // 后端当前会按帧生成事件（约 0.04s 一条），这里做展示侧合并
        const key = `${String(ev?.target || '')}|${String(ev?.severity || '')}`
        const lastT = tick.__lastEventAt?.[key]
        if (!tick.__lastEventAt) tick.__lastEventAt = {}

        // 2s 内同类事件只触发一次（可按需调整）
        if (typeof lastT === 'number' && Number(ev?.timestamp || 0) - lastT < 2.0) {
          continue
        }
        tick.__lastEventAt[key] = Number(ev?.timestamp || 0)

        // 反向查找 trackId 和 zoneName
        const enrichedEv = { ...ev }
        const frameIdx = findNearestFrameIndex(t)
        if (frameIdx !== -1) {
          const frame = overlayFrames.value[frameIdx]
          const objects = Array.isArray(frame?.objects) ? frame.objects : []
          // 简单策略：找第一个在报警区的同类目标
          for (const obj of objects) {
            const objType = String(obj?.class || '').toUpperCase()
            const evType = String(ev?.target || ev?.object_type || '').toUpperCase()
            const alarmLevel = obj?.alarm_level
            const isAlarmObj = alarmLevel === 1 || alarmLevel === 2 || alarmLevel === 'CRITICAL' || alarmLevel === 'WARNING'

            if (isAlarmObj && objType.includes(evType)) {
              enrichedEv.trackId = obj.id
              // 尝试关联区域名称（优先取 overlay 自带的 zoneName，其次用 zoneId 映射）
              const zoneId = obj?.zone_id ?? obj?.zoneId ?? obj?.zone
              const zoneName = obj?.zone_name ?? obj?.zoneName
              if (zoneName) {
                enrichedEv.zoneName = String(zoneName)
              } else if (zoneId != null) {
                enrichedEv.zoneName = zoneNameById.value[String(zoneId)]
              }
              break // 找到一个就跳出
            }
          }
        }

        // 推送到右侧实时事件列表（最新在前）
        realtimeEvents.value.unshift(enrichedEv)
        if (realtimeEvents.value.length > 50) realtimeEvents.value.length = 50
        window.__realtimeEvents = realtimeEvents.value

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

const onVideoPlay = () => {
  isVideoEnded.value = false
  startRenderLoop()
}

const onVideoPause = () => {
  cancelRenderLoop()
  // 暂停时保留最后一帧绘制结果，不清空
}

const onVideoEnded = () => {
  isVideoEnded.value = true
  cancelRenderLoop()
  // ended 事件触发时，video 本身已停止在最后一帧
}

const onVideoSeeked = () => {
  // 拖动进度条时立即绘制一次
  isVideoEnded.value = false
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

  // 如果已经播完，再点播放等同于重播
  if (video.ended || isVideoEnded.value) {
    video.currentTime = 0
    alarmCursor.value = 0
    realtimeEvents.value = []
    isVideoEnded.value = false
    video.play()
    return
  }

  if (video.paused) {
    isVideoEnded.value = false
    video.play()
  } else {
    video.pause()
  }
}

const replayVideo = () => {
  const video = videoRef.value
  if (!video) return
  video.currentTime = 0
  alarmCursor.value = 0
  realtimeEvents.value = []
  isVideoEnded.value = false
  video.play()
}

watch(currentSourceId, async (val, old) => {
  if (!val || val === old) return
  try {
    await updateSystemStatus({ currentSourceId: val })
  } catch {
    // 忽略
  }

  isVideoEnded.value = false
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
          playsinline
          @play="onVideoPlay"
          @pause="onVideoPause"
          @seeked="onVideoSeeked"
          @ended="onVideoEnded"
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
          <div class="events-title">
            <span class="material-symbols-outlined events-title-ico">notifications_active</span>
            <span>实时事件 (Real-time Events)</span>
          </div>
        </div>
        <div class="events-body">
          <div v-if="!realtimeEvents.length" class="empty">暂无事件</div>
          <div v-else class="events-list">
            <div
              v-for="(ev, idx) in realtimeEvents"
              :key="ev.id || `${ev.trackId || 't'}-${idx}`"
              class="event-card"
              :class="[
                `sev-${(ev.type || ev.severity || '').toString().toLowerCase()}`,
                `tgt-${getEventTargetType(ev).toLowerCase()}`,
                { newest: idx === 0 },
              ]"
            >
              <div class="event-ico" :class="`ico-${(ev.type || ev.severity || '').toString().toLowerCase()}`">
                <span class="material-symbols-outlined">
                  {{
                    (getEventTargetType(ev) === 'PERSON' && (ev.type === 'CRITICAL' || ev.severity === 'critical'))
                      ? 'person_alert'
                      : (getEventTargetType(ev) === 'PERSON' && (ev.type === 'WARNING' || ev.severity === 'warning'))
                        ? 'person'
                        : (getEventTargetType(ev) === 'VEHICLE' && (ev.type === 'CRITICAL' || ev.severity === 'critical'))
                          ? 'no_crash'
                          : 'directions_car'
                  }}
                </span>
              </div>

              <div class="event-mid">
                <div class="event-row1">
                  <span class="event-badge" :class="`badge-${(ev.type || ev.severity || '').toString().toLowerCase()}`">
                    {{ (ev.type === 'CRITICAL' || ev.severity === 'critical') ? '非法入侵' : '预警事件' }}
                  </span>
                  <span v-if="ev.trackId" class="event-track">[{{ ev.trackId }}]</span>
                </div>
                <div class="event-row2" :title="ev.zoneName">
                  <span class="event-zone-prefix">Zone:</span>
                  <span class="event-zone-name">{{ ev.zoneName || '-' }}</span>
                </div>
              </div>

              <div class="event-time">{{ formatEventTime(ev) }}</div>
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
          <div class="classic-controls">
            <button class="classic-btn" :title="videoRef?.paused ? '播放' : '暂停'" @click="togglePlayPause">
              <span class="material-symbols-outlined">
                {{ videoRef?.paused ? 'play_arrow' : 'pause' }}
              </span>
            </button>
            <button class="classic-btn" title="重播" @click="replayVideo">
              <span class="material-symbols-outlined">replay</span>
            </button>
          </div>

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

.classic-controls {
  display: flex;
  align-items: center;
  gap: 10px;
  padding-right: 6px;
  border-right: 1px solid rgba(255, 255, 255, 0.08);
  margin-right: 4px;
}

.classic-btn {
  width: 38px;
  height: 38px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border-radius: 10px;
  background: rgba(0, 0, 0, 0.35);
  border: 1px solid rgba(255, 255, 255, 0.12);
  color: #fff;
  cursor: pointer;
  transition:
    background-color 160ms ease,
    border-color 160ms ease,
    transform 160ms ease;
}

.classic-btn:hover {
  background: rgba(255, 255, 255, 0.08);
  border-color: rgba(255, 255, 255, 0.18);
  transform: translateY(-1px);
}

.classic-btn:active {
  transform: translateY(0px);
}

.classic-btn .material-symbols-outlined {
  font-size: 22px;
  line-height: 1;
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
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 13px;
  font-weight: 700;
  color: #fff;
}

.events-title-ico {
  font-size: 18px;
  color: #137fec;
}

.events-body {
  flex: 1;
  overflow: auto;
  padding: 12px;
}

.events-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.event-card {
  display: grid;
  grid-template-columns: 38px 1fr auto;
  gap: 10px;
  align-items: center;
  border: 1px solid #2a3642;
  border-radius: 12px;
  padding: 10px;
  background: rgba(16, 25, 34, 0.35);
  transition:
    background-color 160ms ease,
    border-color 160ms ease,
    transform 160ms ease;
}

.event-card:hover {
  background: rgba(255, 255, 255, 0.06);
  border-color: rgba(255, 255, 255, 0.16);
  transform: translateY(-1px);
}

.event-card.sev-critical {
  border-color: rgba(239, 68, 68, 0.38);
}

.event-card.sev-warning {
  border-color: rgba(245, 158, 11, 0.35);
}

.event-card.newest {
  animation: eventPulse 1.6s ease-in-out 0s 2;
}

@keyframes eventPulse {
  0% {
    box-shadow: 0 0 0 rgba(239, 68, 68, 0);
    background: rgba(255, 255, 255, 0.06);
  }
  50% {
    box-shadow: 0 0 0 6px rgba(19, 127, 236, 0.12);
    background: rgba(19, 127, 236, 0.08);
  }
  100% {
    box-shadow: 0 0 0 rgba(239, 68, 68, 0);
    background: rgba(255, 255, 255, 0.06);
  }
}

.event-ico {
  width: 38px;
  height: 38px;
  border-radius: 10px;
  display: flex;
  align-items: center;
  justify-content: center;
  border: 1px solid rgba(255, 255, 255, 0.1);
  background: rgba(255, 255, 255, 0.04);
}

.event-ico .material-symbols-outlined {
  font-size: 20px;
  line-height: 1;
}

.event-ico.ico-critical {
  background: rgba(239, 68, 68, 0.14);
  border-color: rgba(239, 68, 68, 0.25);
  color: #ef4444;
}

.event-ico.ico-warning {
  background: rgba(245, 158, 11, 0.14);
  border-color: rgba(245, 158, 11, 0.25);
  color: #f59e0b;
}

.event-mid {
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.event-row1 {
  display: flex;
  align-items: center;
  gap: 8px;
  min-width: 0;
}

.event-badge {
  font-size: 10px;
  font-weight: 800;
  letter-spacing: 0.04em;
  padding: 2px 8px;
  border-radius: 999px;
  border: 1px solid rgba(255, 255, 255, 0.12);
  background: rgba(0, 0, 0, 0.18);
  color: #e2e8f0;
  max-width: 100%;
  white-space: nowrap;
}

.event-badge.badge-critical {
  color: #fca5a5;
  border-color: rgba(239, 68, 68, 0.28);
  background: rgba(239, 68, 68, 0.14);
}

.event-badge.badge-warning {
  color: #fcd34d;
  border-color: rgba(245, 158, 11, 0.28);
  background: rgba(245, 158, 11, 0.14);
}

.event-track {
  font-size: 11px;
  color: #cbd5e1;
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, 'Liberation Mono', 'Courier New', monospace;
  opacity: 0.9;
}

.event-row2 {
  display: flex;
  align-items: baseline;
  gap: 6px;
  min-width: 0;
}

.event-zone-prefix {
  font-size: 11px;
  color: #9dabb9;
}

.event-zone-name {
  font-size: 12px;
  color: #e2e8f0;
  font-weight: 600;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.event-time {
  font-size: 12px;
  font-weight: 800;
  color: #e2e8f0;
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, 'Liberation Mono', 'Courier New', monospace;
  padding-left: 10px;
}

.event-card.sev-critical .event-time {
  color: #fecaca;
}

.event-card.sev-warning .event-time {
  color: #fde68a;
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
