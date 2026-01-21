import http from './http'

export const getAlarms = (params) => http.get('/alarms', { params })

export const getAlarmDetail = (id) => http.get(`/alarms/${id}`)
