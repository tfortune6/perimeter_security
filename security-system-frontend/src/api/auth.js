import http from './http'

export const login = (username, password) => http.post('/login', { username, password })

export const getMe = () => http.get('/me')

export const getSystemStatus = () => http.get('/system/status')
