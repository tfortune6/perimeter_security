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

export const handlers = [
  // 注意: /api/token, /api/videos*, /api/zones*, /api/config/save 等接口
  // 不在这里注册 handler，它们将通过 onUnhandledRequest: 'bypass' 自动穿透到真实后端（经 Vite 代理）。

  http.get('/api/me', async ({ request }) => {
    await sleep(200)
    if (!auth.requireAuth(request)) return fail(401, '未登录')
    return ok(db.user)
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

  // 仪表盘仍然需要 mock 的 /api/videos/demo 接口
  http.get('/api/videos/demo', async ({ request }) => {
    await sleep(180)
    if (!auth.requireAuth(request)) return fail(401, '未登录')

    if (db.videos.length && !db.videos.some((x) => x.isDemo)) {
      db.videos[0].isDemo = true
    }
    const demo = db.videos.find((x) => x.isDemo) || null
    return ok(demo)
  }),
]
