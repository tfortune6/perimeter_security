const pad2 = (n) => String(n).padStart(2, '0')

const rnd = (min, max) => Math.floor(Math.random() * (max - min + 1)) + min
const pick = (arr) => arr[rnd(0, arr.length - 1)]

const iso = (d) => d.toISOString()
const fmtDateTime = (d) => {
  const y = d.getFullYear()
  const m = pad2(d.getMonth() + 1)
  const day = pad2(d.getDate())
  const hh = pad2(d.getHours())
  const mm = pad2(d.getMinutes())
  const ss = pad2(d.getSeconds())
  return `${y}-${m}-${day} ${hh}:${mm}:${ss}`
}

const genAlarmId = (idx) => {
  const base = 9000 + idx
  return `ALM-2023-${base}`
}

const thumbs = [
  'https://lh3.googleusercontent.com/aida-public/AB6AXuDlAPacdI5zWa0wR81vsoskMsu9-xyLUqbYrdwUTKNdUGp93qWSjdAvM_zNYfCyUv1ckS7t2MDLIA93QwRmSg9xgYtF5S-_0YtqwsjqymXiwQi-c9tNJ-j5ekwiIHQuAtCKFkvwwdHrZuWZAY3BSu8QMwb6lqSKXH7xoYHshDANneqIPyrJPmEVjpKZnswteRTb5uFFz7PNQx09tZDA_619-Qou9oKAysyMaIJdsd8HLHYT00YCSC1cj4F7x2g10y1k0h92NltRzxI',
  'https://lh3.googleusercontent.com/aida-public/AB6AXuA04rUQ6Lzn8RUwUoD_zF98oIxge71DVuK-MuaRizBpkmUluEQlPIECJihZYHN6H6uLJWUEJxybHvghOrNLLVy0IPdPfp2tO9aHW6rkbaJTDGMJacXWD-sX4Up2McELygLzvhl5VT-zcdbQ0HEnvyY8KbUR0H6K2sFwfR5YSKq5sv0kTCv5bbCL-qa2NhsGzvzOIfjmmoEtJQM0yjCaxhkgbVHUD4NvgLDtgXDJoTAdqaiUo3cqL_Pxhclh2mlEr2QvcryWFoC7UE8',
  'https://lh3.googleusercontent.com/aida-public/AB6AXuCPI0c3J9_v5UG9eOFpxocLldRTkDr2EE-Kj0ZauKvYPOSyROZHb5XdkVY46g2AD1TK60U5nZbzNzjdTFv_Lyk571JN-cdByaK0KLd2W0C3hgIr2nnAi718UeFg6iLVX69r1Kdg2RX0xB2j6-ZYdkfb36CWQwgFUvAttJqvah7xdjmAXJ7UFjJjC6MWPaz9Hz4QmsS7YZz42pHypkgp6yOA-0IsXVvV0qoEFwVTbl0MAoTA_zgWwvBay0lEteh9W0epWXodC_3hUeY',
  'https://lh3.googleusercontent.com/aida-public/AB6AXuAiPoF0W8vARTW_ChwCpxwUkpF9zDbdg1iibVBQQMBdPnW10r3dbTt09vkHpUFrxfrbQkxYrcvVrWVCFTdHhgPCoqYy92p18WhJDnZrnpktCtzvFgwmTzLla7iE8EqHyfVM3wwYcpW9nnuNkvtbcGPXnVfOZNqc9qHeERpmiLmalyZo_NbrehjgpY8TwjZog4r5XkfRhcdoQqeCBfiYQ8G7jynCFyVYjLk0l54dveWzA86TURTZ9aZ6VctrDhoh_UxH2TQcM_kEHgU',
]

const alarmZones = ['Zone A - North Gate', 'Zone B - Parking', 'Zone C - Warehouse', 'Zone D - Fence']
const targets = ['行人', '车辆', '未知目标']
const remarks = ['非法入侵检测', '区域徘徊警告', '越界告警', '遮挡告警', '目标异常停留']

const genAlarms = (count = 128) => {
  const base = new Date('2023-10-24T08:00:00')
  const items = []

  for (let i = 0; i < count; i++) {
    const id = genAlarmId(i)
    const d = new Date(base.getTime() + i * 1000 * 60 * rnd(3, 15))
    const severity = Math.random() < 0.35 ? 'critical' : 'warning'
    const status = Math.random() < 0.55 ? 'pending' : 'done'
    const zone = pick(alarmZones)
    const remark = pick(remarks)

    items.push({
      id,
      thumb: pick(thumbs),
      time: fmtDateTime(d),
      target: pick(targets),
      severity,
      status,
      remark,
      zone,
      snapshots: [],
      timeline: [
        { at: iso(d), action: '生成告警', by: 'AI引擎' },
        {
          at: iso(new Date(d.getTime() + 1000 * 60 * rnd(1, 10))),
          action: status === 'done' ? '已处理' : '等待处理',
          by: status === 'done' ? '管理员' : '系统',
        },
      ],
    })
  }

  items.sort((a, b) => (a.time < b.time ? 1 : -1))
  return items
}

const videoNames = [
  'main_gate_entrance',
  'parking_lot_cam_01',
  'warehouse_a_02',
  'north_fence_patrol',
  'east_gate',
  'dock_area',
  'perimeter_night',
]

const qualities = ['720p', '1080p', '2K', '4K HDR']
const exts = ['MP4', 'MKV', 'AVI']

const fmtDuration = (sec) => {
  const h = Math.floor(sec / 3600)
  const m = Math.floor((sec % 3600) / 60)
  const s = sec % 60
  return `${pad2(h)}:${pad2(m)}:${pad2(s)}`
}

const fmtSize = (mb) => {
  if (mb > 1024) return `${(mb / 1024).toFixed(1)} GB`
  return `${mb} MB`
}

const genVideos = (count = 30) => {
  const base = new Date('2023-10-20T10:00:00')
  const list = []

  for (let i = 0; i < count; i++) {
    const ext = pick(exts)
    const name = `${pick(videoNames)}_${pad2(rnd(1, 30))}.${ext.toLowerCase()}`
    const d = new Date(base.getTime() + i * 1000 * 60 * rnd(30, 180))
    const dur = rnd(30, 60 * 20)
    const size = rnd(50, 900)

    list.push({
      id: `vid-${pad2(i + 1)}`,
      name,
      ext,
      quality: pick(qualities),
      size: fmtSize(size),
      duration: fmtDuration(dur),
      uploadAt: fmtDateTime(d).slice(0, 16),
      isDemo: false,
      previewUrl: 'https://interactive-examples.mdn.mozilla.net/media/cc0-videos/flower.mp4',
    })
  }

  if (list.length) list[0].isDemo = true
  return list
}

const state = {
  token: 'demo-token',
  user: {
    id: 'u_admin',
    name: 'Admin User',
    role: '系统管理员',
    avatarUrl:
      'https://lh3.googleusercontent.com/aida-public/AB6AXuBw_U7F6T6qfTV8Bm9nj4aOabzd9KgjjATZ21OkZ1YsuuKTkirUCIOJk4AsWQ4_d39X9opwjcZB32_IuWay8QEamkxgzcIBXH0_ZmsB1Xo14f9UWCBCdHNedtJ8LvDICPdrNBcb_PneogAfLsZZwFOuJlvwGxWUwcJHPBTTGyRifBlLfwa-yO2Yph0DGAQlsUVH6uK1rC2QBOFFb_T4QiX2tu4qDHmMEUnDYHzP9vP57TyVYYXe4EV0abzOA2Va3MNVtxpFLSyHNMw',
  },
  system: {
    online: true,
    version: 'v2.4.1 (Stable)',
    fps: 24,
    currentSourceId: 'vid-01',
  },
  sources: [],
  zonesBySource: {
    'vid-01': [
      {
        id: 'zone-01',
        name: '仓库入口禁区',
        type: 'core',
        threshold: 3,
        motion: true,
        polygonPoints: [
          [200, 300],
          [350, 280],
          [500, 350],
          [450, 420],
          [220, 400],
        ],
      },
    ],
  },
  dashboard: {
    overlaysBySource: {
      'vid-01': {
        boxes: [
          { id: 'b1', x: 0.45, y: 0.35, w: 0.12, h: 0.35, label: 'PERSON', score: 0.98, level: 'danger' },
          { id: 'b2', x: 0.72, y: 0.4, w: 0.18, h: 0.16, label: 'VEHICLE', score: 0.85, level: 'warning' },
          { id: 'b3', x: 0.1, y: 0.72, w: 0.08, h: 0.22, label: 'PERSON', score: 0.99, level: 'success' },
        ],
      },
    },
  },
  alarms: genAlarms(128),
  videos: genVideos(30),
}

// 让“视频源/通道”与已上传视频保持一致（使用视频 id，显示视频 name）
state.sources = state.videos.map((v) => ({ id: v.id, name: v.name }))


export const db = state

export const auth = {
  requireAuth(request) {
    const h = request.headers.get('authorization') || request.headers.get('Authorization')
    const token = h?.replace(/^Bearer\s+/i, '')
    return token === db.token
  },
}

export const sleep = (ms) => new Promise((r) => setTimeout(r, ms))

export const rand = {
  rnd,
  pick,
  fmtDateTime,
  fmtDuration,
  fmtSize,
}
