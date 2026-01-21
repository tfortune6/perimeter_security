import { http, HttpResponse } from 'msw'
import { auth, db, rand, sleep } from './data/db'

const ok = (data) => HttpResponse.json({ code: 0, message: 'ok', data })
const fail = (code, message, data) => HttpResponse.json({ code, message, data }, { status: 200 })

const parseUrl = (request) => new URL(request.url)

const eventTypes = [
  { type: 'INTRUSION', level: 'danger', remark: '非法入侵检测' },
  { type: 'LOITERING', level: 'warning', remark: '区域徘徊警告' },
  { type: 'CROSSING', level: 'warning', remark: '越界告警' },
  { type: 'TAMPER', level: 'danger', remark: '遮挡告警' },
  { type: 'SUSPICIOUS', level: 'warning', remark: '目标异常停留' },
]

const zones = ['Zone A - North Gate', 'Zone B - Parking', 'Zone C - Warehouse', 'Zone D - Fence']

const genLiveEvents = (limit = 8) => {
  const n = Math.max(2, Math.min(limit, 12))
  const items = []
  for (let i = 0; i < n; i++) {
    const t = rand.pick(eventTypes)
    const alarm = rand.pick(db.alarms)
    items.push({
      id: `evt-${Date.now()}-${i}-${rand.rnd(10, 99)}`,
      type: t.type,
      level: t.level,
      time: new Date().toLocaleTimeString(),
      zone: rand.pick(zones),
      sourceId: 'cam1',
      thumbUrl: alarm.thumb,
      alarmId: alarm.id,
    })
  }
  return items
}

const ensureDemoUnique = () => {
  if (!db.videos.length) return
  const demoCount = db.videos.filter((x) => x.isDemo).length
  if (demoCount !== 1) {
    db.videos.forEach((x) => (x.isDemo = false))
    db.videos[0].isDemo = true
  }
}

const ensureZoneList = (sourceId) => {
  if (!db.zonesBySource[sourceId]) db.zonesBySource[sourceId] = []
  return db.zonesBySource[sourceId]
}

const findZoneById = (zoneId) => {
  for (const sourceId in db.zonesBySource) {
    const zones = db.zonesBySource[sourceId]
    const idx = zones.findIndex((z) => z.id === zoneId)
    if (idx >= 0) {
      return { zones, idx, sourceId }
    }
  }
  return null
}

export const handlers = [
  http.post('/api/login', async ({ request }) => {
    const body = await request.json().catch(() => ({}))
    const { username, password } = body || {}

    await sleep(300)

    if (username === 'admin' && password === 'admin') {
      return ok({ token: db.token })
    }
    return fail(1001, '用户名或密码错误')
  }),

  http.get('/api/me', async ({ request }) => {
    await sleep(200)
    if (!auth.requireAuth(request)) return fail(401, '未登录')
    return ok(db.user)
  }),

  http.get('/api/system/status', async ({ request }) => {
    await sleep(150)
    if (!auth.requireAuth(request)) return fail(401, '未登录')
    return ok(db.system)
  }),

  http.put('/api/system/status', async ({ request }) => {
    await sleep(200)
    if (!auth.requireAuth(request)) return fail(401, '未登录')

    const patch = await request.json().catch(() => ({}))
    if (patch.currentSourceId) {
      db.system.currentSourceId = patch.currentSourceId
    }
    return ok(db.system)
  }),

  http.get('/api/sources', async ({ request }) => {
    await sleep(150)
    if (!auth.requireAuth(request)) return fail(401, '未登录')
    return ok(db.sources)
  }),

  http.get('/api/dashboard/events', async ({ request }) => {
    await sleep(250)
    if (!auth.requireAuth(request)) return fail(401, '未登录')

    const url = parseUrl(request)
    const limit = Number(url.searchParams.get('limit') || '8')

    return ok(genLiveEvents(limit))
  }),

  http.get('/api/dashboard/overlays', async ({ request }) => {
    await sleep(200)
    if (!auth.requireAuth(request)) return fail(401, '未登录')

    const url = parseUrl(request)
    const sourceId = url.searchParams.get('sourceId') || db.system.currentSourceId
    const overlays = db.dashboard.overlaysBySource[sourceId] || { boxes: [] }
    return ok(overlays)
  }),

  http.get('/api/zones', async ({ request }) => {
    await sleep(200)
    if (!auth.requireAuth(request)) return fail(401, '未登录')

    const url = parseUrl(request)
    const sourceId = url.searchParams.get('sourceId') || db.system.currentSourceId
    const zones = ensureZoneList(sourceId)
    return ok(zones)
  }),

  http.post('/api/zones', async ({ request }) => {
    await sleep(250)
    if (!auth.requireAuth(request)) return fail(401, '未登录')

    const url = parseUrl(request)
    const sourceId = url.searchParams.get('sourceId') || db.system.currentSourceId

    const body = await request.json().catch(() => ({}))
    const { name, type, threshold, motion, polygonPoints } = body || {}

    if (!Array.isArray(polygonPoints) || polygonPoints.length < 3) {
      return fail(400, '多边形至少需要 3 个点')
    }

    const zones = ensureZoneList(sourceId)
    const id = `zone-${Math.random().toString(16).slice(2, 8)}`

    const row = {
      id,
      name: name || '新建区域',
      type: type || 'core',
      threshold: typeof threshold === 'number' ? threshold : 3,
      motion: typeof motion === 'boolean' ? motion : true,
      polygonPoints,
    }

    zones.unshift(row)
    return ok(row)
  }),

  http.put('/api/zones/:id', async ({ request, params }) => {
    await sleep(250)
    if (!auth.requireAuth(request)) return fail(401, '未登录')

    const { id } = params
    const patch = await request.json().catch(() => ({}))

    const found = findZoneById(id)
    if (!found) return fail(404, '区域不存在')

    const { zones, idx } = found
    zones[idx] = { ...zones[idx], ...patch }
    return ok(zones[idx])
  }),

  http.delete('/api/zones/:id', async ({ request, params }) => {
    await sleep(250)
    if (!auth.requireAuth(request)) return fail(401, '未登录')

    const { id } = params
    const found = findZoneById(id)
    if (!found) return fail(404, '区域不存在')

    const { zones, idx } = found
    zones.splice(idx, 1)
    return ok(true)
  }),

  http.post('/api/config/save', async ({ request }) => {
    await sleep(350)
    if (!auth.requireAuth(request)) return fail(401, '未登录')

    const url = parseUrl(request)
    const sourceId = url.searchParams.get('sourceId') || db.system.currentSourceId

    return ok({ sourceId, savedAt: new Date().toISOString() })
  }),

  http.get('/api/alarms', async ({ request }) => {
    await sleep(350)
    if (!auth.requireAuth(request)) return fail(401, '未登录')

    const url = parseUrl(request)
    const page = Number(url.searchParams.get('page') || '1')
    const pageSize = Number(url.searchParams.get('pageSize') || '10')
    const query = (url.searchParams.get('query') || '').trim().toLowerCase()
    const level = url.searchParams.get('level') || ''

    let items = [...db.alarms]

    if (query) {
      items = items.filter(
        (a) => a.id.toLowerCase().includes(query) || (a.remark || '').toLowerCase().includes(query),
      )
    }
    if (level) {
      items = items.filter((a) => a.severity === level)
    }

    const total = items.length
    const start = (page - 1) * pageSize
    const list = items.slice(start, start + pageSize).map((a) => ({
      id: `#${a.id}`,
      thumb: a.thumb,
      time: a.time,
      target: a.target,
      severity: a.severity,
      status: a.status,
    }))

    return ok({ list, total })
  }),

  http.get('/api/alarms/:id', async ({ request, params }) => {
    await sleep(250)
    if (!auth.requireAuth(request)) return fail(401, '未登录')

    const id = String(params.id || '').replace(/^#/, '')
    const alarm = db.alarms.find((a) => a.id === id)
    if (!alarm) return fail(404, '告警不存在')
    return ok(alarm)
  }),

  http.get('/api/videos', async ({ request }) => {
    await sleep(250)
    if (!auth.requireAuth(request)) return fail(401, '未登录')

    ensureDemoUnique()

    const url = parseUrl(request)
    const keyword = (url.searchParams.get('keyword') || '').trim().toLowerCase()

    let items = [...db.videos]
    if (keyword) items = items.filter((x) => x.name.toLowerCase().includes(keyword))

    return ok(items)
  }),

  http.get('/api/videos/demo', async ({ request }) => {
    await sleep(180)
    if (!auth.requireAuth(request)) return fail(401, '未登录')

    ensureDemoUnique()
    const demo = db.videos.find((x) => x.isDemo) || null
    return ok(demo)
  }),

  http.post('/api/videos/upload', async ({ request }) => {
    await sleep(450)
    if (!auth.requireAuth(request)) return fail(401, '未登录')

    const id = `vid-${Math.random().toString(16).slice(2, 8)}`
    const name = `upload_${Date.now()}.mp4`

    const row = {
      id,
      name,
      ext: 'MP4',
      quality: rand.pick(['720p', '1080p', '2K', '4K HDR']),
      size: rand.fmtSize(rand.rnd(20, 800)),
      duration: rand.fmtDuration(rand.rnd(10, 60 * 10)),
      uploadAt: new Date().toISOString().slice(0, 16).replace('T', ' '),
      isDemo: false,
      previewUrl: 'https://interactive-examples.mdn.mozilla.net/media/cc0-videos/flower.mp4',
    }

    db.videos.unshift(row)

    // 同步到“视频源列表”，保证仪表盘/配置中心可立即看到新视频
    db.sources = db.videos.map((v) => ({ id: v.id, name: v.name }))

    // 为新视频初始化区域与 overlay 容器
    if (!db.zonesBySource[id]) db.zonesBySource[id] = []
    if (!db.dashboard.overlaysBySource[id]) db.dashboard.overlaysBySource[id] = { boxes: [] }

    return ok(row)
  }),

  http.post('/api/videos/:id/set-demo', async ({ request, params }) => {
    await sleep(250)
    if (!auth.requireAuth(request)) return fail(401, '未登录')

    const { id } = params
    const idx = db.videos.findIndex((x) => x.id === id)
    if (idx < 0) return fail(404, '视频不存在')

    db.videos.forEach((x) => (x.isDemo = false))
    db.videos[idx].isDemo = true
    return ok(db.videos[idx])
  }),

  http.delete('/api/videos/:id', async ({ request, params }) => {
    await sleep(250)
    if (!auth.requireAuth(request)) return fail(401, '未登录')

    const { id } = params
    db.videos = db.videos.filter((x) => x.id !== id)

    if (db.videos.length && !db.videos.some((x) => x.isDemo)) {
      db.videos[0].isDemo = true
    }

    return ok(true)
  }),
]
