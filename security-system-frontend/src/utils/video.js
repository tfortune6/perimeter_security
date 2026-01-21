export function getVideoFrame(file) {
  return new Promise((resolve, reject) => {
    if (!file || !file.type.startsWith('video/')) {
      return reject(new Error('无效的视频文件'))
    }

    const video = document.createElement('video')
    const canvas = document.createElement('canvas')
    const ctx = canvas.getContext('2d')

    video.muted = true
    video.playsInline = true

    const objectUrl = URL.createObjectURL(file)

    const onError = (e) => {
      cleanup()
      reject(e)
    }

    const cleanup = () => {
      video.removeEventListener('loadeddata', onLoadedData)
      video.removeEventListener('error', onError)
      URL.revokeObjectURL(objectUrl)
      video.src = ''
    }

    const onLoadedData = () => {
      video.currentTime = 0.1 // 避免黑帧
    }

    video.addEventListener('loadeddata', onLoadedData)
    video.addEventListener('error', onError)

    video.addEventListener(
      'seeked',
      () => {
        // 延迟一帧确保绘制完成
        requestAnimationFrame(() => {
          canvas.width = video.videoWidth
          canvas.height = video.videoHeight
          ctx.drawImage(video, 0, 0, video.videoWidth, video.videoHeight)

          const frameUrl = canvas.toDataURL('image/jpeg', 0.85)
          cleanup()
          resolve(frameUrl)
        })
      },
      { once: true },
    )

    video.src = objectUrl
    video.load()
  })
}
