import { createRouter, createWebHistory } from 'vue-router'

const routes = [
  {
    path: '/login',
    component: () => import('./views/Login.vue'),
    meta: { title: '智能周界安全平台 - 登录', public: true },
  },
  {
    path: '/',
    component: () => import('./views/Dashboard.vue'),
    meta: { title: '智能周界安全平台 - 仪表盘' },
  },
  {
    path: '/config',
    component: () => import('./views/Config.vue'),
    meta: { title: '智能周界安全平台 - 配置中心' },
  },
  {
    path: '/history',
    component: () => import('./views/History.vue'),
    meta: { title: '智能周界安全平台 - 报警记录' },
  },
  {
    path: '/sources',
    component: () => import('./views/Sources.vue'),
    meta: { title: '智能周界安全平台 - 视频源管理' },
  },
]

const router = createRouter({
  history: createWebHistory(),
  routes,
})

router.beforeEach((to, from, next) => {
  document.title = to.meta.title || '智能周界安全平台'

  if (to.meta.public) {
    next()
    return
  }

  const token = localStorage.getItem('token')
  if (!token) {
    next({ path: '/login', query: { redirect: to.fullPath } })
    return
  }

  next()
})

export default router
