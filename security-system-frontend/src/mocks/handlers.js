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


]
