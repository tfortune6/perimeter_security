import http from './http'

export const login = async (username, password) => {
  const body = new URLSearchParams()
  body.append('username', username)
  body.append('password', password)

  // 走同源 /api 让 Vite 代理转发到后端，避免 CORS
  return http.post('/token', body, {
    headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
    // /token 返回的是标准 OAuth2：{access_token, token_type}
    transformResponse: (data) => {
      try {
        return JSON.parse(data)
      } catch {
        return data
      }
    },
  })
}
