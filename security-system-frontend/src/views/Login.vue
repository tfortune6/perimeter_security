<script setup>
import { reactive, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { login } from '../api/auth'

const router = useRouter()
const route = useRoute()

const loading = ref(false)

const form = reactive({
  username: 'admin',
  password: '123456',
})

const rules = {
  username: [{ required: true, message: '请输入用户名', trigger: 'blur' }],
  password: [{ required: true, message: '请输入密码', trigger: 'blur' }],
}

const formRef = ref()

const onSubmit = async () => {
  await formRef.value?.validate?.()

  loading.value = true
  try {
    const { access_token } = await login(form.username, form.password)

    // 恢复前端原有约定：token 存在 localStorage.token
    localStorage.setItem('token', access_token)

    ElMessage.success('登录成功')

    const redirect = route.query.redirect
    router.replace(typeof redirect === 'string' ? redirect : '/')
  } catch (e) {
    ElMessage.error(e?.message || '登录失败')
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <div class="page">
    <div class="card">
      <div class="title">智能周界安全平台</div>
      <div class="sub">原型演示版（真实登录 + Mock 展示）</div>

      <el-form ref="formRef" :model="form" :rules="rules" label-position="top" class="form" @submit.prevent>
        <el-form-item label="用户名" prop="username">
          <el-input v-model="form.username" size="large" autocomplete="off" />
        </el-form-item>
        <el-form-item label="密码" prop="password">
          <el-input v-model="form.password" size="large" type="password" show-password autocomplete="off" />
        </el-form-item>

        <el-button type="primary" size="large" class="btn" :loading="loading" @click="onSubmit">登录</el-button>

        <div class="tip">演示账号：admin / 123456</div>
      </el-form>
    </div>
  </div>
</template>

<style scoped>
.page {
  height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  background: radial-gradient(circle at 20% 20%, rgba(19, 127, 236, 0.25), transparent 40%),
    radial-gradient(circle at 80% 60%, rgba(16, 185, 129, 0.18), transparent 45%), #0b0e11;
}

.card {
  width: 420px;
  max-width: calc(100vw - 32px);
  background: rgba(28, 33, 39, 0.9);
  border: 1px solid #2a3642;
  border-radius: 14px;
  padding: 20px;
  box-shadow: 0 25px 90px rgba(0, 0, 0, 0.55);
}

.title {
  color: #fff;
  font-size: 20px;
  font-weight: 900;
}

.sub {
  margin-top: 6px;
  color: #9dabb9;
  font-size: 12px;
}

.form {
  margin-top: 14px;
}

.btn {
  width: 100%;
}

.tip {
  margin-top: 12px;
  color: #9dabb9;
  font-size: 12px;
  text-align: center;
}

:deep(.el-form-item__label) {
  color: #cbd5e1;
}

:deep(.el-input__wrapper) {
  background: #111418;
  box-shadow: 0 0 0 1px #2a3642 inset;
}

:deep(.el-input__inner) {
  color: #fff;
}
</style>
