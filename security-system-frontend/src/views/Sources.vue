<script setup>
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import AppLayout from '../components/layout/AppLayout.vue'
import { deleteVideo, getVideos, setDemoVideo, uploadVideo } from '../api/videos'
import { deleteVideoFile, putVideoFile } from '../storage/videoStore'

const userAvatar =
  'https://lh3.googleusercontent.com/aida-public/AB6AXuBw_U7F6T6qfTV8Bm9nj4aOabzd9KgjjATZ21OkZ1YsuuKTkirUCIOJk4AsWQ4_d39X9opwjcZB32_IuWay8QEamkxgzcIBXH0_ZmsB1Xo14f9UWCBCdHNedtJ8LvDICPdrNBcb_PneogAfLsZZwFOuJlvwGxWUwcJHPBTTGyRifBlLfwa-yO2Yph0DGAQlsUVH6uK1rC2QBOFFb_T4QiX2tu4qDHmMEUnDYHzP9vP57TyVYYXe4EV0abzOA2Va3MNVtxpFLSyHNMw'

const keyword = ref('')
const list = ref([])
const loading = ref(false)

const previewVisible = ref(false)
const previewUrl = ref('')
const previewTitle = ref('')

const localPreviewMap = new Map()

const filtered = computed(() => {
  const k = keyword.value.trim().toLowerCase()
  if (!k) return list.value
  return list.value.filter((x) => x.name.toLowerCase().includes(k))
})

const fetchList = async () => {
  loading.value = true
  try {
    list.value = await getVideos({ keyword: keyword.value })
  } catch (e) {
    ElMessage.error(e?.message || '加载失败')
  } finally {
    loading.value = false
  }
}

const onUploadChange = async (uploadFile) => {
  const file = uploadFile?.raw
  if (!file) return

  // 检查 AVI 格式并拒绝
  if (file.type === 'video/x-msvideo' || file.name.toLowerCase().endsWith('.avi')) {
    ElMessage.error('不支持 AVI 格式，请上传 MP4 或 WebM 格式的视频。')
    // 从 el-upload 的文件列表中移除，避免 UI 显示“已选择”
    uploadFile.status = 'fail'
    return
  }

  const objectUrl = URL.createObjectURL(file)

  try {
    loading.value = true
    const row = await uploadVideo(file)

    if (row?.id) {
      await putVideoFile(row.id, file)
      localPreviewMap.set(row.id, objectUrl)
    }

    ElMessage.success('上传成功')
    await fetchList()
  } catch (e) {
    URL.revokeObjectURL(objectUrl)
    ElMessage.error(e?.message || '上传失败')
  } finally {
    loading.value = false
  }
}

const setDemo = async (row) => {
  try {
    loading.value = true
    await setDemoVideo(row.id)
    ElMessage.success('已设为演示源')
    await fetchList()
  } catch (e) {
    ElMessage.error(e?.message || '操作失败')
  } finally {
    loading.value = false
  }
}

const remove = async (row) => {
  try {
    loading.value = true
    await deleteVideo(row.id)
    await deleteVideoFile(row.id)

    const url = localPreviewMap.get(row.id)
    if (url) {
      URL.revokeObjectURL(url)
      localPreviewMap.delete(row.id)
    }

    ElMessage.success('已删除')
    await fetchList()
  } catch (e) {
    ElMessage.error(e?.message || '删除失败')
  } finally {
    loading.value = false
  }
}

const openPreview = (row) => {
  const localUrl = localPreviewMap.get(row.id)
  previewUrl.value = localUrl || row.previewUrl
  previewVisible.value = true
  previewTitle.value = row.name
}

watch(keyword, () => {
  fetchList()
})

watch(previewVisible, (v) => {
  if (!v) {
    previewUrl.value = ''
    previewTitle.value = ''
  }
})

onMounted(() => {
  fetchList()
})

onBeforeUnmount(() => {
  for (const url of localPreviewMap.values()) {
    URL.revokeObjectURL(url)
  }
  localPreviewMap.clear()
})
</script>

<template>
  <AppLayout title="智能周界安全平台" :avatar-url="userAvatar" user-name="Admin User" user-role="系统管理员">
    <div class="sources">
      <div class="wrap">
        <div class="head">
          <div>
            <div class="h1">视频源管理</div>
            <div class="sub">管理系统视频输入源及演示素材，支持批量上传与预览。</div>
          </div>
          <div class="actions">
            <el-button plain class="btn">操作日志</el-button>
          </div>
        </div>

        <div class="upload" :class="loading ? 'is-loading' : ''">
          <el-upload
            drag
            multiple
            action="#"
            :auto-upload="false"
            :on-change="onUploadChange"
            :disabled="loading"
            class="u"
          >
            <div class="upload-inner">
              <div class="upload-ico">⬆</div>
              <div class="upload-title">点击或拖拽上传视频</div>
              <div class="upload-sub">
                支持 MP4, WebM 格式，单文件最大 500MB。<br />
                AVI 格式无法预览，建议转码后上传。
              </div>
              <div class="upload-btn">选择文件</div>
            </div>
          </el-upload>
        </div>

        <div class="panel">
          <div class="panel-head">
            <div class="panel-title">
              已上传视频
              <span class="count">{{ filtered.length }}</span>
            </div>

            <div class="panel-tools">
              <el-input v-model="keyword" placeholder="搜索文件名..." class="search" clearable />
              <el-button plain class="btn">筛选</el-button>
            </div>
          </div>

          <el-table :data="filtered" size="large" class="table" v-loading="loading">
            <el-table-column prop="name" label="文件名" min-width="320">
              <template #default="scope">
                <div class="file">
                  <div class="file-ico" :class="scope.row.isDemo ? 'file-ico-demo' : ''">▶</div>
                  <div class="file-meta">
                    <div class="file-name">
                      {{ scope.row.name }}
                      <span v-if="scope.row.isDemo" class="pulse" />
                    </div>
                    <div class="file-sub">
                      <span class="tag">{{ scope.row.ext }}</span>
                      <span>{{ scope.row.quality }}</span>
                    </div>
                  </div>
                </div>
              </template>
            </el-table-column>

            <el-table-column prop="size" label="文件大小" width="130" />
            <el-table-column prop="duration" label="时长" width="130" />
            <el-table-column prop="uploadAt" label="上传时间" width="170" />

            <el-table-column label="操作" width="260" align="right">
              <template #default="scope">
                <div class="ops">
                  <el-button type="primary" link @click="openPreview(scope.row)">预览</el-button>

                  <template v-if="scope.row.isDemo">
                    <span class="demo">当前演示源</span>
                  </template>
                  <template v-else>
                    <el-button type="primary" link @click="setDemo(scope.row)">设为演示源</el-button>
                  </template>

                  <el-button type="danger" link @click="remove(scope.row)">删除</el-button>
                </div>
              </template>
            </el-table-column>
          </el-table>
        </div>
      </div>

      <el-dialog v-model="previewVisible" :title="previewTitle" width="860px">
        <div class="player">
          <video v-if="previewUrl" :src="previewUrl" controls playsinline class="video" />
          <div v-else class="empty">暂无预览资源</div>
        </div>
      </el-dialog>
    </div>
  </AppLayout>
</template>

<style scoped>
.sources {
  height: 100%;
  background: #101922;
  overflow: auto;
}

.wrap {
  max-width: 1280px;
  margin: 0 auto;
  padding: 24px;
  display: flex;
  flex-direction: column;
  gap: 18px;
}

.head {
  display: flex;
  align-items: flex-end;
  justify-content: space-between;
  gap: 16px;
}

.h1 {
  font-size: 24px;
  font-weight: 900;
  color: #fff;
}

.sub {
  margin-top: 6px;
  font-size: 13px;
  color: #9dabb9;
}

.actions {
  display: flex;
  gap: 10px;
}

.btn {
  background: #111418;
  border-color: #2a3642;
  color: #cbd5e1;
}

.upload {
  border: 2px dashed #3b4754;
  border-radius: 14px;
  background: rgba(22, 27, 34, 0.5);
  overflow: hidden;
}

.upload.is-loading {
  opacity: 0.8;
}

.u :deep(.el-upload-dragger) {
  width: 100%;
  border: 0;
  background: transparent;
}

.upload-inner {
  padding: 44px 16px;
  text-align: center;
}

.upload-ico {
  width: 56px;
  height: 56px;
  margin: 0 auto 14px;
  border-radius: 999px;
  background: #1e293b;
  color: #9dabb9;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 24px;
}

.upload-title {
  font-size: 18px;
  font-weight: 900;
  color: #fff;
}

.upload-sub {
  margin-top: 8px;
  font-size: 13px;
  color: #9dabb9;
  line-height: 1.5;
}

.upload-btn {
  margin: 18px auto 0;
  width: fit-content;
  background: #137fec;
  color: #fff;
  font-weight: 900;
  padding: 10px 18px;
  border-radius: 10px;
}

.panel {
  border: 1px solid #2a3642;
  border-radius: 14px;
  background: #111418;
  overflow: hidden;
}

.panel-head {
  padding: 10px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  background: #111418;
}

.panel-title {
  display: flex;
  align-items: center;
  gap: 10px;
  color: #fff;
  font-weight: 900;
  padding: 0 8px;
}

.count {
  font-size: 12px;
  color: #137fec;
  background: rgba(19, 127, 236, 0.1);
  border: 1px solid rgba(19, 127, 236, 0.25);
  padding: 2px 8px;
  border-radius: 999px;
}

.panel-tools {
  display: flex;
  align-items: center;
  gap: 10px;
  width: 420px;
  max-width: 100%;
}

.search {
  flex: 1;
}

.file {
  display: flex;
  align-items: center;
  gap: 12px;
}

.file-ico {
  width: 40px;
  height: 40px;
  border-radius: 10px;
  border: 1px solid #2a3642;
  background: #1e293b;
  color: #9dabb9;
  display: flex;
  align-items: center;
  justify-content: center;
  flex: 0 0 auto;
}

.file-ico-demo {
  background: rgba(19, 127, 236, 0.2);
  border-color: rgba(19, 127, 236, 0.3);
  color: #137fec;
}

.file-name {
  color: #fff;
  font-weight: 800;
  display: flex;
  align-items: center;
  gap: 8px;
}

.pulse {
  width: 8px;
  height: 8px;
  border-radius: 999px;
  background: #22c55e;
  display: inline-block;
  animation: pulse 1.2s infinite;
}

@keyframes pulse {
  0% {
    transform: scale(0.9);
    opacity: 0.7;
  }
  70% {
    transform: scale(1.2);
    opacity: 1;
  }
  100% {
    transform: scale(0.9);
    opacity: 0.7;
  }
}

.file-sub {
  margin-top: 2px;
  font-size: 12px;
  color: #9dabb9;
  display: flex;
  gap: 8px;
}

.tag {
  background: #283039;
  color: #9dabb9;
  border-radius: 6px;
  padding: 1px 6px;
  font-size: 10px;
}

.ops {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  justify-content: flex-end;
}

.demo {
  height: 28px;
  display: inline-flex;
  align-items: center;
  padding: 0 10px;
  border-radius: 10px;
  color: #34d399;
  background: rgba(16, 185, 129, 0.12);
  border: 1px solid rgba(16, 185, 129, 0.25);
  font-size: 12px;
  font-weight: 800;
}

.player {
  background: #0b0e11;
  border: 1px solid #2a3642;
  border-radius: 12px;
  overflow: hidden;
}

.video {
  width: 100%;
  height: auto;
  display: block;
  background: #000;
}

.empty {
  padding: 24px;
  color: #9dabb9;
}

:deep(.el-input__wrapper) {
  background: #1e293b;
  box-shadow: 0 0 0 1px #2a3642 inset;
}

:deep(.el-input__inner) {
  color: #fff;
}

:deep(.el-table) {
  --el-table-bg-color: #111418;
  --el-table-tr-bg-color: #111418;
  --el-table-header-bg-color: #1e293b;
  --el-table-border-color: #2a3642;
  --el-table-text-color: #cbd5e1;
  --el-table-header-text-color: #9dabb9;
}
</style>
