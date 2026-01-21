import http from './http'

export const getSources = () => http.get('/sources')

export const getZones = (sourceId) => http.get('/zones', { params: { sourceId } })

export const createZone = (sourceId, payload) => http.post('/zones', payload, { params: { sourceId } })

export const updateZone = (id, patch) => http.put(`/zones/${id}`, patch)

export const deleteZone = (id) => http.delete(`/zones/${id}`)

export const saveConfig = (sourceId) => http.post('/config/save', null, { params: { sourceId } })
