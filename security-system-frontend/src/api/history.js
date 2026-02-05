import http from './http'

export const getAlarms = (params) => http.get('/alarms', { params })

export const getAlarmDetail = (id) => http.get(`/alarms/${id}`)

export const getUnreadAlarmCount = () => http.get('/alarms/unread/count')

export const markAllAlarmsRead = () => http.post('/alarms/mark-all-read')
