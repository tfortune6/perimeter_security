<script setup>
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import AppLayout from '../components/layout/AppLayout.vue'
import { createZone, deleteZone, getZones, saveConfig, updateZone } from '../api/config'
import { getVideos } from '../api/videos'
import { getVideoFile } from '../storage/videoStore'
import { getVideoFrame } from '../utils/video'

const userAvatar =
  'https://lh3.googleusercontent.com/aida-public/AB6AXuBw_U7F6T6qfTV8Bm9nj4aOabzd9KgjjATZ21OkZ1YsuuKTkirUCIOJk4AsWQ4_d39X9opwjcZB32_IuWay8QEamkxgzcIBXH0_ZmsB1Xo14f9UWCBCdHNedtJ8LvDICPdrNBcb_PneogAfLsZZwFOuJlvwGxWUwcJHPBTTGyRifBlLfwa-yO2Yph0DGAQlsUVH6uK1rC2QBOFFb_T4QiX2tu4qDHmMEUnDYHzP9vP57TyVYYXe4EV0abzOA2Va3MNVtxpFLSyHNMw'

const defaultImg =
  'https://lh3.googleusercontent.com/aida-public/AB6AXuDRoR9tDCtLtIyspSbEqNzjzmAqB2svNgpWgMPcTvDehkxeiH613hcz4J8e-awzXfg7qOpXS8-R5rAQ1X9GsSqVJvLtNkEtR7BjR5Umz0z8yS3VldNPCAD_kftSHyo6pz_dQqAv5-8GO8DPuvMmSb6_PuxLBwJYZbdrBM5i7iAUa1upSmvLsJMrtKfb8OW97L_Br9haoABfo-X_gH1zJ3uBbysBZCPR0rzgLetIrqJcO8Ky8-a1PbpelpoyWeLVW3YINjwZmz6Zx34'

const loading = ref(false)
const frameLoading = ref(false)

const videoSources = ref([])
const currentVideoId = ref('')
const stageBg = ref(defaultImg)

const zones = ref([])
const selectedZoneId = ref('')

const selectedZone = computed(() => zones.value.find((z) => z.id === selectedZoneId.value) || null)

const zoneName = ref('')
const zoneType = ref('core')
const threshold = ref(3)
const motion = ref(true)

// --- 绘制/编辑工具状态 ---
const drawing = ref(false)
const draftPoints = ref([]) // [ [x,y], ... ] viewBox坐标系(0..800,0..450)

const dragging = ref(null) // { mode: 'draft'|'zone', index: number }
const selectedZonePoints = ref([]) // 选中区域可编辑点（本地态）
const editHistory = ref([]) // 栈：保存 polygonPoints 的快照，用于撤回

const CLOSE_DIST = 12 // “重合闭合”阈值（viewBox像素）

const draftPointsStr = computed(() => {
  if (!draftPoints.value.length) return ''
  return draftPoints.value.map(([x, y]) => `${x},${y}`).join(' ')
})

const syncFormFromZone = (z) => {
  if (!z) return
  zoneName.value = z.name || ''
  zoneType.value = z.type || 'core'
  threshold.value = Number(z.threshold ?? 3)
  motion.value = Boolean(z.motion)
}

const loadSelectedZonePoints = () => {
  const z = selectedZone.value
  if (!z?.polygonPoints?.length) {
    selectedZonePoints.value = []
    editHistory.value = []
    return
  }
  selectedZonePoints.value = z.polygonPoints.map((p) => [p[0], p[1]])
  editHistory.value = [selectedZonePoints.value.map((p) => [p[0], p[1]])]
}

const fetchVideoSources = async () => {
  const list = await getVideos()
  videoSources.value = list
  if (!currentVideoId.value && list.length) {
    currentVideoId.value = list[0].id
  }
}

const fetchZones = async () => {
  if (!currentVideoId.value) return
  zones.value = await getZones(currentVideoId.value)
  if (!selectedZoneId.value && zones.value.length) {
    selectedZoneId.value = zones.value[0].id
  }
}

const updateStageBackground = async () => {
  if (!currentVideoId.value) {
    stageBg.value = defaultImg
    return
  }

  frameLoading.value = true
  try {
    const file = await getVideoFile(currentVideoId.value)
    if (file) {
      stageBg.value = await getVideoFrame(file)
    } else {
      stageBg.value = defaultImg
    }
  } catch (e) {
    stageBg.value = defaultImg
    ElMessage.error('加载视频帧失败')
  } finally {
    frameLoading.value = false
  }
}

watch(selectedZone, (z) => {
  syncFormFromZone(z)
  loadSelectedZonePoints()
})

watch(currentVideoId, async () => {
  selectedZoneId.value = ''
  drawing.value = false
  draftPoints.value = []
  dragging.value = null
  selectedZonePoints.value = []
  editHistory.value = []
  await fetchZones()
  await updateStageBackground()
})

const apply = async () => {
  if (!selectedZone.value) return
  loading.value = true
  try {
    await updateZone(selectedZone.value.id, {
      name: zoneName.value,
      type: zoneType.value,
      threshold: threshold.value,
      motion: motion.value,
      polygonPoints: selectedZonePoints.value.length ? selectedZonePoints.value : selectedZone.value.polygonPoints,
    })
    ElMessage.success('已应用更改')
    await fetchZones()
  } catch (e) {
    ElMessage.error(e?.message || '应用失败')
  } finally {
    loading.value = false
  }
}

const reset = () => {
  syncFormFromZone(selectedZone.value)
  loadSelectedZonePoints()
}

const save = async () => {
  if (!currentVideoId.value) return
  loading.value = true
  try {
    await saveConfig(currentVideoId.value)
    ElMessage.success('保存成功（演示）')
  } catch (e) {
    ElMessage.error(e?.message || '保存失败')
  } finally {
    loading.value = false
  }
}

const startDraw = () => {
  drawing.value = true
  draftPoints.value = []
  dragging.value = null
  ElMessage.info('绘制模式：点击添加点；拖拽点调整；最后一个点拖到第一个点上自动闭合；Ctrl+Z 撤回；ESC/右键取消')
}

const cancelDraw = () => {
  drawing.value = false
  draftPoints.value = []
  dragging.value = null
}

const dist = (a, b) => {
  const dx = a[0] - b[0]
  const dy = a[1] - b[1]
  return Math.sqrt(dx * dx + dy * dy)
}

const clamp = (v, min, max) => Math.max(min, Math.min(max, v))

const getStagePoint = (ev) => {
  const rect = ev.currentTarget.getBoundingClientRect()
  const x = (ev.clientX - rect.left) / rect.width
  const y = (ev.clientY - rect.top) / rect.height

  return {
    x: clamp(Math.round(x * 800), 0, 800),
    y: clamp(Math.round(y * 450), 0, 450),
  }
}

const onStageClick = (ev) => {
  // 绘制模式下，添加点
  if (drawing.value) {
    if (dragging.value) return

    const { x, y } = getStagePoint(ev)

    if (draftPoints.value.length >= 3) {
      const first = draftPoints.value[0]
      if (dist([x, y], first) <= CLOSE_DIST) {
        finishDraw()
        return
      }
    }

    draftPoints.value = [...draftPoints.value, [x, y]]
    return
  }

  // 非绘制模式下，点击空白处取消选中
  selectedZoneId.value = ''
}

const finishDraw = async () => {
  if (!drawing.value) return
  if (draftPoints.value.length < 3) {
    ElMessage.warning('至少需要 3 个点才能生成多边形')
    return
  }
  if (!currentVideoId.value) {
    ElMessage.error('未选择视频源')
    return
  }

  loading.value = true
  try {
    const row = await createZone(currentVideoId.value, {
      name: '新建区域',
      type: 'core',
      threshold: 3,
      motion: true,
      polygonPoints: draftPoints.value,
    })

    ElMessage.success('区域已创建')
    drawing.value = false
    draftPoints.value = []
    dragging.value = null

    await fetchZones()
    selectedZoneId.value = row.id
  } catch (e) {
    ElMessage.error(e?.message || '创建失败')
  } finally {
    loading.value = false
  }
}

const onStageDblClick = () => {
  finishDraw()
}

const onStageContextMenu = (ev) => {
  if (!drawing.value) return
  ev.preventDefault()
  cancelDraw()
  ElMessage.info('已取消绘制')
}

const onPolygonClick = (zoneId) => {
  selectedZoneId.value = zoneId
}

const removeSelected = async () => {
  if (!selectedZoneId.value) {
    ElMessage.warning('请先选择一个区域')
    return
  }

  loading.value = true
  try {
    await deleteZone(selectedZoneId.value)
    ElMessage.success('已删除选中区域')

    selectedZoneId.value = ''
    await fetchZones()

    if (zones.value.length) {
      selectedZoneId.value = zones.value[0].id
    }
  } catch (e) {
    ElMessage.error(e?.message || '删除失败')
  } finally {
    loading.value = false
  }
}

const pushEditHistory = () => {
  const snap = selectedZonePoints.value.map((p) => [p[0], p[1]])
  editHistory.value.push(snap)
  if (editHistory.value.length > 30) editHistory.value.shift()
}

const undo = () => {
  if (drawing.value) {
    if (draftPoints.value.length) {
      draftPoints.value = draftPoints.value.slice(0, -1)
    }
    return
  }

  if (editHistory.value.length <= 1) return
  editHistory.value.pop()
  const prev = editHistory.value[editHistory.value.length - 1]
  selectedZonePoints.value = prev.map((p) => [p[0], p[1]])
}

const onKeyDown = (e) => {
  if (e.key === 'Escape') {
    if (drawing.value) {
      cancelDraw()
      return
    }
    dragging.value = null
    return
  }

  if ((e.ctrlKey || e.metaKey) && (e.key === 'z' || e.key === 'Z')) {
    e.preventDefault()
    undo()
  }
}

const onPointMouseDown = (mode, index, ev) => {
  if (mode === 'zone') {
    pushEditHistory()
  }
  dragging.value = { mode, index }

  document.body.style.userSelect = 'none'
  ev?.preventDefault?.()
}

const onStageMouseMove = (ev) => {
  if (!dragging.value) return

  const rect = ev.currentTarget.getBoundingClientRect()
  const x = (ev.clientX - rect.left) / rect.width
  const y = (ev.clientY - rect.top) / rect.height
  const px = clamp(Math.round(x * 800), 0, 800)
  const py = clamp(Math.round(y * 450), 0, 450)

  if (dragging.value.mode === 'draft') {
    const i = dragging.value.index
    const next = draftPoints.value.map((p) => [p[0], p[1]])
    next[i] = [px, py]
    draftPoints.value = next

    if (i === next.length - 1 && next.length >= 3) {
      const first = next[0]
      if (dist(next[i], first) <= CLOSE_DIST) {
        finishDraw()
      }
    }

    return
  }

  if (dragging.value.mode === 'zone') {
    const i = dragging.value.index
    const next = selectedZonePoints.value.map((p) => [p[0], p[1]])
    next[i] = [px, py]
    selectedZonePoints.value = next

    const idx = zones.value.findIndex((z) => z.id === selectedZoneId.value)
    if (idx >= 0) {
      const z = zones.value[idx]
      zones.value.splice(idx, 1, { ...z, polygonPoints: next })
    }
  }
}

const onStageMouseUp = () => {
  dragging.value = null
  document.body.style.userSelect = ''
}

const zoneClass = (z) => {
  const classes = ['zone']
  if (z.type === 'warning') classes.push('zone-warning')
  else classes.push('zone-core')
  if (z.id === selectedZoneId.value) classes.push('zone-selected')
  return classes.join(' ')
}

const vertexClass = () => {
  const z = selectedZone.value
  if (z?.type === 'warning') return 'vertex vertex-warning'
  return 'vertex vertex-core'
}

onMounted(async () => {
  window.addEventListener('keydown', onKeyDown)

  loading.value = true
  try {
    await fetchVideoSources()
    await fetchZones()
    await updateStageBackground()
  } catch (e) {
    ElMessage.error(e?.message || '初始化失败')
  } finally {
    loading.value = false
  }
})

onBeforeUnmount(() => {
  window.removeEventListener('keydown', onKeyDown)
})
</script>

<template>
  <AppLayout title="智能周界安全平台" :avatar-url="userAvatar" user-name="Admin User" user-role="系统管理员">
    <div class="config">
      <aside class="toolbar" v-loading="loading">
        <div class="card">
          <div class="label">视频源选择</div>
          <el-select v-model="currentVideoId" class="w" size="large" :disabled="loading">
            <el-option v-for="opt in videoSources" :key="opt.id" :label="opt.name" :value="opt.id" />
          </el-select>
        </div>

        <div class="card">
          <div class="label">区域选择</div>
          <el-select v-model="selectedZoneId" class="w" size="large" :disabled="loading || zones.length === 0">
            <el-option v-for="z in zones" :key="z.id" :label="z.name" :value="z.id" />
          </el-select>
        </div>

        <div class="divider" />

        <div class="card">
          <div class="label tiny">绘图工具</div>
          <el-button type="primary" plain size="large" class="w btn-primary" :disabled="loading" @click="startDraw">
            绘制多边形
          </el-button>
          <el-button plain size="large" class="w" :disabled="loading" @click="undo">撤回一步</el-button>
          <el-button type="danger" plain size="large" class="w" :disabled="loading" @click="removeSelected">
            删除选中区域
          </el-button>
        </div>

        <div class="spacer" />

        <el-button type="primary" size="large" class="w save" :loading="loading" @click="save">保存配置</el-button>
      </aside>

      <section class="canvas">
        <div class="rec">REC • 1920x1080 • 30FPS</div>

        <div
          class="stage"
          :class="drawing ? 'drawing' : ''"
          @click="onStageClick"
          @dblclick="onStageDblClick"
          @contextmenu="onStageContextMenu"
          @mousemove="onStageMouseMove"
          @mouseup="onStageMouseUp"
          @mouseleave="onStageMouseUp"
        >
          <img class="stage-img" :src="stageBg" alt="Security feed" />

          <svg class="stage-svg" viewBox="0 0 800 450">
            <polygon
              v-for="z in zones"
              :key="z.id"
              :points="z.polygonPoints.map(([x, y]) => `${x},${y}`).join(' ')"
              :class="zoneClass(z)"
              @click.stop="onPolygonClick(z.id)"
            />

            <circle
              v-for="(p, idx) in selectedZonePoints"
              :key="`zp-${idx}`"
              :cx="p[0]"
              :cy="p[1]"
              r="6"
              :class="vertexClass()"
              @mousedown.stop="(e) => onPointMouseDown('zone', idx, e)"
            />

            <polyline v-if="drawing && draftPoints.length" :points="draftPointsStr" class="draft" />

            <circle
              v-for="(p, idx) in draftPoints"
              :key="`p-${idx}`"
              :cx="p[0]"
              :cy="p[1]"
              r="6"
              class="draft-point"
              @mousedown.stop="(e) => onPointMouseDown('draft', idx, e)"
            />

            <circle
              v-if="drawing && draftPoints.length"
              :cx="draftPoints[0][0]"
              :cy="draftPoints[0][1]"
              r="7"
              class="start-point"
            />
          </svg>

          <div v-if="frameLoading" class="stage-loading">加载视频帧...</div>

          <div class="hint">
            绘制：点击添加点；拖拽点调整；末点靠近起点自动闭合；Ctrl+Z 撤回；ESC/右键取消
            <br />
            编辑：拖拽白点修改；Ctrl+Z 撤回；点击“应用更改”保存
          </div>
        </div>
      </section>

      <aside class="props">
        <div class="props-head">
          <div class="props-title">区域属性</div>
          <div class="props-id">ID: {{ selectedZoneId || '-' }}</div>
        </div>

        <div class="props-body" v-loading="loading">
          <template v-if="selectedZone">
            <div class="field">
              <div class="label tiny">区域名称</div>
              <el-input v-model="zoneName" size="large" />
            </div>

            <div class="field">
              <div class="label tiny">区域类型</div>
              <el-radio-group v-model="zoneType" class="zone-types">
                <el-radio-button label="core">核心区域</el-radio-button>
                <el-radio-button label="warning">预警区域</el-radio-button>
              </el-radio-group>
            </div>

            <div class="field">
              <div class="row">
                <div class="label tiny">触发时间阈值</div>
                <div class="val">{{ Number(threshold).toFixed(1) }} 秒</div>
              </div>
              <el-slider v-model="threshold" :min="0" :max="10" :step="0.5" />
            </div>

            <div class="divider" />

            <div class="row switch-row">
              <div class="label">启用移动侦测</div>
              <el-switch v-model="motion" />
            </div>
          </template>
          <template v-else>
            <div class="empty">暂无区域数据</div>
          </template>
        </div>

        <div class="props-foot">
          <el-button size="large" class="w" plain :disabled="!selectedZone || loading" @click="reset">重置</el-button>
          <el-button size="large" class="w" type="primary" :disabled="!selectedZone" :loading="loading" @click="apply">
            应用更改
          </el-button>
        </div>
      </aside>
    </div>
  </AppLayout>
</template>

<style scoped>
.config {
  height: 100%;
  display: grid;
  grid-template-columns: 288px 1fr 320px;
  background: #0b0e11;
}

.toolbar {
  border-right: 1px solid #2a3642;
  background: #1c2127;
  padding: 16px;
  display: flex;
  flex-direction: column;
  gap: 14px;
  overflow: auto;
}

.canvas {
  position: relative;
  overflow: hidden;
  background: #0b0e11;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 18px;
}

.canvas::before {
  content: '';
  position: absolute;
  inset: 0;
  opacity: 0.5;
  background-size: 40px 40px;
  background-image: linear-gradient(to right, #232a34 1px, transparent 1px),
    linear-gradient(to bottom, #232a34 1px, transparent 1px);
}

.rec {
  position: absolute;
  top: 16px;
  left: 16px;
  z-index: 2;
  padding: 6px 10px;
  border-radius: 8px;
  background: rgba(0, 0, 0, 0.7);
  border: 1px solid rgba(255, 255, 255, 0.1);
  color: #fff;
  font-size: 12px;
}

.stage {
  position: relative;
  z-index: 1;
  width: min(960px, 100%);
  aspect-ratio: 16 / 9;
  border-radius: 12px;
  overflow: hidden;
  border: 1px solid #2a3642;
  box-shadow: 0 20px 60px rgba(0, 0, 0, 0.45);
}

.stage.drawing {
  outline: 2px dashed rgba(59, 130, 246, 0.55);
  outline-offset: -2px;
}

.stage-img {
  width: 100%;
  height: 100%;
  object-fit: cover;
  opacity: 0.8;
}

.stage-loading {
  position: absolute;
  inset: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  background: rgba(0, 0, 0, 0.6);
  color: #fff;
  z-index: 2;
}

.stage-svg {
  position: absolute;
  inset: 0;
  width: 100%;
  height: 100%;
}

.zone {
  stroke-width: 2;
  cursor: pointer;
}

.zone-core {
  fill: rgba(239, 68, 68, 0.18);
  stroke: rgba(239, 68, 68, 0.9);
}

.zone-warning {
  fill: rgba(245, 158, 11, 0.16);
  stroke: rgba(245, 158, 11, 0.9);
}

.zone:hover {
  filter: brightness(1.15);
}

.zone-selected {
  stroke: rgba(19, 127, 236, 0.95) !important;
  fill: rgba(19, 127, 236, 0.18) !important;
}

.vertex {
  fill: #ffffff;
  stroke-width: 2;
  cursor: grab;
}

.vertex:active {
  cursor: grabbing;
}

.vertex-core {
  stroke: rgba(239, 68, 68, 0.95);
}

.vertex-warning {
  stroke: rgba(245, 158, 11, 0.95);
}

.draft {
  fill: none;
  stroke: rgba(59, 130, 246, 0.9);
  stroke-width: 2;
  stroke-dasharray: 6 6;
}

.draft-point {
  fill: #ffffff;
  stroke: rgba(59, 130, 246, 0.9);
  stroke-width: 2;
  cursor: grab;
}

.draft-point:active {
  cursor: grabbing;
}

.start-point {
  fill: rgba(59, 130, 246, 0.05);
  stroke: rgba(59, 130, 246, 0.9);
  stroke-width: 2;
}

.hint {
  position: absolute;
  left: 50%;
  bottom: 16px;
  transform: translateX(-50%);
  padding: 10px 16px;
  border-radius: 999px;
  background: rgba(0, 0, 0, 0.6);
  color: rgba(255, 255, 255, 0.9);
  font-size: 12px;
  opacity: 0;
  transition: opacity 0.2s ease;
  text-align: center;
  line-height: 1.4;
}

.stage:hover .hint {
  opacity: 1;
}

.props {
  border-left: 1px solid #2a3642;
  background: #1c2127;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.props-head {
  padding: 16px;
  border-bottom: 1px solid #2a3642;
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.props-title {
  font-size: 14px;
  font-weight: 800;
  color: #fff;
}

.props-id {
  font-size: 12px;
  color: #9dabb9;
  border: 1px solid #2a3642;
  padding: 4px 8px;
  border-radius: 8px;
  background: #111418;
}

.props-body {
  padding: 16px;
  display: flex;
  flex-direction: column;
  gap: 18px;
  overflow: auto;
}

.props-foot {
  margin-top: auto;
  padding: 16px;
  border-top: 1px solid #2a3642;
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 12px;
}

.card {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.field {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
}

.switch-row {
  padding: 8px 0;
}

.label {
  color: #fff;
  font-size: 13px;
  font-weight: 700;
}

.label.tiny {
  color: #9dabb9;
  font-size: 11px;
  font-weight: 800;
  letter-spacing: 0.08em;
  text-transform: uppercase;
}

.val {
  font-size: 13px;
  font-weight: 800;
  color: #137fec;
  background: rgba(19, 127, 236, 0.1);
  padding: 3px 8px;
  border-radius: 8px;
}

.divider {
  height: 1px;
  background: #2a3642;
}

.spacer {
  flex: 1 1 auto;
}

.w {
  width: 100%;
}

.empty {
  color: #9dabb9;
}

.zone-types :deep(.el-radio-button__inner) {
  background: #111418;
  border-color: #2a3642;
  color: #cbd5e1;
}

.zone-types :deep(.is-active .el-radio-button__inner) {
  background: rgba(19, 127, 236, 0.15);
  border-color: rgba(19, 127, 236, 0.8);
  color: #fff;
}

:deep(.el-input__wrapper),
:deep(.el-select__wrapper) {
  background: #111418;
  box-shadow: 0 0 0 1px #2a3642 inset;
}

:deep(.el-input__inner) {
  color: #fff;
}

:deep(.el-slider__runway) {
  background: #111418;
}

.card .el-button + .el-button {
  margin-left: 0;
}
</style>
