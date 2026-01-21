import http from './http'

export const getDashboardEvents = (limit = 20) => http.get('/dashboard/events', { params: { limit } })

export const getDashboardOverlays = (sourceId) => http.get('/dashboard/overlays', { params: { sourceId } })

export const getDashboardZones = (sourceId) => http.get('/zones', { params: { sourceId } })
