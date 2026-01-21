import http from './http'

export const getSystemStatus = () => http.get('/system/status')

export const updateSystemStatus = (patch) => http.put('/system/status', patch)
