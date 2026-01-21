<script setup>
import { computed, onMounted, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import AppLayout from '../components/layout/AppLayout.vue'
import { getAlarms, getAlarmDetail } from '../api/history'

const userAvatar =
  'https://lh3.googleusercontent.com/aida-public/AB6AXuBw_U7F6T6qfTV8Bm9nj4aOabzd9KgjjATZ21OkZ1YsuuKTkirUCIOJk4AsWQ4_d39X9opwjcZB32_IuWay8QEamkxgzcIBXH0_ZmsB1Xo14f9UWCBCdHNedtJ8LvDICPdrNBcb_PneogAfLsZZwFOuJlvwGxWUwcJHPBTTGyRifBlLfwa-yO2Yph0DGAQlsUVH6uK1rC2QBOFFb_T4QiX2tu4qDHmMEUnDYHzP9vP57TyVYYXe4EV0abzOA2Va3MNVtxpFLSyHNMw'

const query = ref('')
const level = ref('')

// 给 DatePicker 使用（可能会写入 Date 对象）
const rangePicker = ref([])
// 给接口使用（永远保持 YYYY-MM-DD 字符串数组）
const range = ref([])

const loading = ref(false)
const data = ref([])

const page = ref(1)
const pageSize = ref(10)
const total = ref(0)

const shownFrom = computed(() => (total.value === 0 ? 0 : (page.value - 1) * pageSize.value + 1))
const shownTo = computed(() => Math.min(page.value * pageSize.value, total.value))

const detailVisible = ref(false)
const detailLoading = ref(false)
const detail = ref(null)

const fetchList = async () => {
  loading.value = true
  try {
    const [startDate, endDate] = Array.isArray(range.value) ? range.value : []

    const res = await getAlarms({
      page: page.value,
      pageSize: pageSize.value,
      query: query.value,
      level: level.value,
      startDate,
      endDate,
    })
    data.value = res.list
    total.value = res.total
  } catch (e) {
    ElMessage.error(e?.message || '加载失败')
  } finally {
    loading.value = false
  }
}

const onFilter = () => {
  page.value = 1
  fetchList()
}

const openDetail = async (row) => {
  const id = String(row.id || '').replace(/^#/, '')
  detailVisible.value = true
  detailLoading.value = true
  detail.value = null
  try {
    detail.value = await getAlarmDetail(id)
  } catch (e) {
    ElMessage.error(e?.message || '加载详情失败')
  } finally {
    detailLoading.value = false
  }
}

watch(
  rangePicker,
  (v) => {
    if (!Array.isArray(v) || v.length !== 2) {
      range.value = []
      return
    }

    // 如果 DatePicker 返回的是字符串（有 value-format），直接使用
    if (typeof v[0] === 'string' && typeof v[1] === 'string') {
      range.value = [v[0], v[1]]
      return
    }

    // 兜底：如果返回 Date 对象，转换成 YYYY-MM-DD
    const toYmd = (d) => {
      if (!(d instanceof Date)) return ''
      const y = d.getFullYear()
      const m = String(d.getMonth() + 1).padStart(2, '0')
      const day = String(d.getDate()).padStart(2, '0')
      return `${y}-${m}-${day}`
    }

    const a = toYmd(v[0])
    const b = toYmd(v[1])
    range.value = a && b ? [a, b] : []
  },
  { deep: true },
)

watch(page, () => fetchList())

onMounted(() => {
  fetchList()
})
</script>

<template>
  <AppLayout title="智能周界安全平台" :avatar-url="userAvatar" user-name="Admin User" user-role="系统管理员">
    <div class="history">
      <div class="wrap">
        <div class="head">
          <div>
            <div class="h1">告警历史记录</div>
            <div class="sub">查看和管理历史安全告警事件，支持多维度筛选与回溯。</div>
          </div>
          <div>
            <el-button class="btn" plain>导出报表</el-button>
          </div>
        </div>

        <div class="filters">
          <el-input v-model="query" placeholder="搜索 ID 或 备注..." class="f search" />

          <el-select v-model="level" placeholder="全部告警等级" class="f level">
            <el-option label="全部告警等级" value="" />
            <el-option label="严重 (Critical)" value="critical" />
            <el-option label="警告 (Warning)" value="warning" />
          </el-select>

          <el-date-picker
            v-model="rangePicker"
            type="daterange"
            range-separator="-"
            start-placeholder="开始日期"
            end-placeholder="结束日期"
            class="f range"
            format="YYYY-MM-DD"
            value-format="YYYY-MM-DD"
          />

          <el-button type="primary" class="btn-primary" :loading="loading" @click="onFilter">筛选结果</el-button>
        </div>

        <div class="table">
          <el-table :data="data" :border="false" size="large" v-loading="loading">
            <el-table-column prop="id" label="告警 ID" min-width="170">
              <template #default="scope">
                <span class="id">{{ scope.row.id }}</span>
              </template>
            </el-table-column>

            <el-table-column label="截图" width="140">
              <template #default="scope">
                <div class="thumb" :style="{ backgroundImage: `url('${scope.row.thumb}')` }" />
              </template>
            </el-table-column>

            <el-table-column prop="time" label="视频时间戳" min-width="170" />

            <el-table-column prop="target" label="目标类型" width="120" />

            <el-table-column label="威胁等级" width="140">
              <template #default="scope">
                <span
                  class="pill"
                  :class="scope.row.severity === 'critical' ? 'pill-critical' : 'pill-warning'"
                >
                  {{ scope.row.severity === 'critical' ? '严重' : '警告' }}
                </span>
              </template>
            </el-table-column>

            <el-table-column label="状态" width="120">
              <template #default="scope">
                <span class="pill" :class="scope.row.status === 'done' ? 'pill-done' : 'pill-pending'">
                  {{ scope.row.status === 'done' ? '已处理' : '未处理' }}
                </span>
              </template>
            </el-table-column>

            <el-table-column label="操作" width="120" align="right">
              <template #default="scope">
                <el-button type="primary" link @click="openDetail(scope.row)">查看详情</el-button>
              </template>
            </el-table-column>
          </el-table>

          <div class="table-footer">
            <div class="meta">
              显示 <span class="meta-strong">{{ shownFrom }}</span> 到 <span class="meta-strong">{{ shownTo }}</span> 条，
              共 <span class="meta-strong">{{ total }}</span> 条记录
            </div>

            <el-pagination
              v-model:current-page="page"
              v-model:page-size="pageSize"
              :total="total"
              layout="prev, pager, next"
              background
            />
          </div>
        </div>
      </div>

      <el-dialog v-model="detailVisible" width="720px" title="告警详情">
        <div v-loading="detailLoading" class="detail">
          <template v-if="detail">
            <div class="detail-row">
              <div class="k">告警ID</div>
              <div class="v">{{ detail.id }}</div>
            </div>
            <div class="detail-row">
              <div class="k">区域</div>
              <div class="v">{{ detail.zone }}</div>
            </div>
            <div class="detail-row">
              <div class="k">备注</div>
              <div class="v">{{ detail.remark }}</div>
            </div>
          </template>
          <template v-else>
            <div class="empty">暂无数据</div>
          </template>
        </div>
      </el-dialog>
    </div>
  </AppLayout>
</template>

<style scoped>
.history {
  height: 100%;
  background: #101922;
  overflow: auto;
}

.wrap {
  max-width: 1400px;
  margin: 0 auto;
  padding: 24px;
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.head {
  display: flex;
  align-items: flex-end;
  justify-content: space-between;
  gap: 16px;
}

.h1 {
  font-size: 28px;
  font-weight: 900;
  color: #fff;
}

.sub {
  margin-top: 6px;
  font-size: 13px;
  color: #9dabb9;
}

.filters {
  display: flex;
  align-items: center;
  gap: 12px;
  background: #1c2127;
  border: 1px solid #2a3642;
  border-radius: 12px;
  padding: 14px;
  width: 100%;
  box-sizing: border-box;
  overflow: hidden;
}

.filters .f {
  flex: 0 0 auto;
  min-width: 0;
}

.filters .f.search {
  flex: 1 1 auto;
  min-width: 280px;
}

.filters .f.level {
  flex: 0 0 180px;
}

.filters .f.range {
  flex: 0 0 340px;
}

.filters .btn-primary {
  flex: 0 0 120px;
  margin-left: 0;
  min-width: 120px;
}

@media (max-width: 1100px) {
  .filters {
    flex-wrap: wrap;
  }
  .filters .btn-primary {
    margin-left: 0;
  }
  .filters .f.search {
    width: 100%;
    max-width: 100%;
  }
  .filters .f.range {
    width: 100%;
  }
}

.f {
  width: 100%;
}

.btn {
  background: #1c2127;
  border-color: #2a3642;
  color: #fff;
}

.btn-primary {
  height: 40px;
}

.table {
  background: #1c2127;
  border: 1px solid #2a3642;
  border-radius: 12px;
  overflow: hidden;
}

.thumb {
  width: 96px;
  height: 56px;
  border-radius: 8px;
  border: 1px solid #2a3642;
  background-size: cover;
  background-position: center;
  opacity: 0.9;
}

.id {
  color: #fff;
  font-weight: 700;
}

.pill {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 4px 10px;
  font-size: 12px;
  font-weight: 800;
  border-radius: 999px;
  border: 1px solid transparent;
}

.pill-critical {
  color: #f87171;
  background: rgba(239, 68, 68, 0.12);
  border-color: rgba(239, 68, 68, 0.25);
}

.pill-warning {
  color: #fb923c;
  background: rgba(245, 158, 11, 0.12);
  border-color: rgba(245, 158, 11, 0.25);
}

.pill-pending {
  color: #cbd5e1;
  background: rgba(100, 116, 139, 0.2);
  border-color: rgba(148, 163, 184, 0.25);
}

.pill-done {
  color: #34d399;
  background: rgba(16, 185, 129, 0.12);
  border-color: rgba(16, 185, 129, 0.25);
}

.table-footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 12px 14px;
  border-top: 1px solid #2a3642;
}

.meta {
  font-size: 12px;
  color: #9dabb9;
}

.meta-strong {
  color: #fff;
  font-weight: 800;
}

.detail {
  min-height: 120px;
}

.detail-row {
  display: grid;
  grid-template-columns: 120px 1fr;
  gap: 10px;
  padding: 6px 0;
}

.k {
  color: #9dabb9;
}

.v {
  color: #fff;
}

.empty {
  color: #9dabb9;
}

:deep(.el-input__wrapper),
:deep(.el-select__wrapper) {
  background: #101922;
  box-shadow: 0 0 0 1px #2a3642 inset;
}

:deep(.el-input__inner) {
  color: #fff;
}

:deep(.el-range-editor.el-input__wrapper) {
  background: #101922;
}

:deep(.el-table) {
  --el-table-bg-color: #1c2127;
  --el-table-tr-bg-color: #1c2127;
  --el-table-header-bg-color: #232931;
  --el-table-border-color: #2a3642;
  --el-table-text-color: #cbd5e1;
  --el-table-header-text-color: #9dabb9;
}

:deep(.el-table th.el-table__cell) {
  font-size: 12px;
  letter-spacing: 0.06em;
}

:deep(.el-pagination.is-background .el-pager li) {
  background: #1c2127;
  border: 1px solid #2a3642;
  color: #9dabb9;
}

:deep(.el-pagination.is-background .el-pager li.is-active) {
  background: #137fec;
  border-color: #137fec;
  color: #fff;
}

:deep(.el-pagination.is-background .btn-prev),
:deep(.el-pagination.is-background .btn-next) {
  background: #1c2127;
  border: 1px solid #2a3642;
  color: #9dabb9;
}
</style>
