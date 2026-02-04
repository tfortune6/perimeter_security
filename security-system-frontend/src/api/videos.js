import http from './http'

export const getVideos = (params) => http.get('/videos', { params })

export const getVideo = (id) => http.get(`/videos/${id}`)

export const uploadVideo = (file) => {
  const fd = new FormData()
  fd.append('file', file)
  return http.post('/videos/upload', fd, {
    headers: { 'Content-Type': 'multipart/form-data' },
  })
}

export const setDemoVideo = (id) => http.post(`/videos/${id}/set-demo`)

export const deleteVideo = (id) => http.delete(`/videos/${id}`)
