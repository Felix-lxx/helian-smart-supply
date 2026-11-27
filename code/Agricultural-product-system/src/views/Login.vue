<script setup>
import { ref, reactive } from 'vue'
import { ElMessage } from 'element-plus'
import request from '@/utils/request'
const tab = ref('login'),
  busy = ref(''),
  form = reactive({ username: '', password: '', role: 'retail' })
function enter(d) {
  for (const [k, v] of Object.entries({
    access_token: d.access,
    refresh_token: d.refresh,
    user_role: d.role,
    username: d.username,
    user_id: d.user_id,
  }))
    localStorage.setItem(k, v)
  window.location.assign('/home')
}
async function login() {
  busy.value = 'login'
  try {
    if (tab.value === 'register') {
      await request.post('/register/', form)
      ElMessage.success('注册成功，请登录')
      tab.value = 'login'
    } else enter((await request.post('/login/', form)).data)
  } catch (e) {
    ElMessage.error(
      e.response?.data?.detail || e.response?.data?.error || '请检查账号、密码和填写内容',
    )
  } finally {
    busy.value = ''
  }
}
async function demo(role) {
  busy.value = role
  try {
    enter((await request.post('/workspace/demo-login/', { role })).data)
  } catch (e) {
    ElMessage.error(e.response?.data?.detail || '演示工作区暂不可用')
  } finally {
    busy.value = ''
  }
}
</script>
<template>
  <div class="login-page">
    <section class="login-story">
      <div class="login-brand">
        <el-icon><Connection /></el-icon> 禾链智配
      </div>
      <div class="story-center">
        <div class="story-line"></div>
        <h1>好产地，<br />遇见好生意。</h1>
        <p>连接批次、品质与订单。<br />从一笔采购，到每一次可靠交付。</p>
        <div class="story-flow">
          <span>产地供给</span><el-icon><Right /></el-icon><span>品质适配</span
          ><el-icon><Right /></el-icon><span>协同交付</span>
        </div>
      </div>
      <div class="story-bottom">
        <span>果蔬产销协同工作空间</span><span>禾链智配 · 本地开发版</span>
      </div>
    </section>
    <section class="login-form-side">
      <div class="login-form">
        <span class="login-icon"
          ><el-icon><Connection /></el-icon
        ></span>
        <h2>{{ tab === 'login' ? '欢迎回到工作空间' : '创建你的工作空间' }}</h2>
        <p class="muted">让每一批货，找到合适的订单。</p>
        <div class="login-tabs">
          <button :class="{ active: tab === 'login' }" @click="tab = 'login'">账号登录</button
          ><button :class="{ active: tab === 'register' }" @click="tab = 'register'">
            注册账号
          </button>
        </div>
        <el-form label-position="top" @submit.prevent="login"
          ><el-form-item label="用户名"
            ><el-input
              v-model="form.username"
              size="large"
              placeholder="输入用户名"
              autocomplete="username" /></el-form-item
          ><el-form-item label="密码"
            ><el-input
              v-model="form.password"
              type="password"
              size="large"
              show-password
              placeholder="输入密码"
              autocomplete="current-password" /></el-form-item
          ><el-form-item v-if="tab === 'register'" label="业务身份"
            ><el-select v-model="form.role" size="large" style="width: 100%"
              ><el-option label="采购商" value="retail" /><el-option
                label="供应商"
                value="supplier" /></el-select></el-form-item
          ><el-button
            type="primary"
            native-type="submit"
            size="large"
            :loading="busy === 'login'"
            style="width: 100%; margin-top: 6px"
            >{{ tab === 'login' ? '进入工作空间' : '创建账号' }}</el-button
          ></el-form
        >
        <div class="demo-section">
          <div class="demo-heading">
            <span>体验三端协同</span><span class="demo-tag">演示数据</span>
          </div>
          <div class="demo-buttons">
            <button
              v-for="[r, name, icon] in [
                ['retail', '采购端', 'ShoppingBag'],
                ['supplier', '供应端', 'Goods'],
                ['admin', '运营端', 'Operation'],
                ['cooperative', '协作供货方', 'Connection'],
              ]"
              :key="r"
              :disabled="!!busy"
              @click="demo(r)"
            >
              <el-icon><component :is="icon" /></el-icon><b>{{ busy === r ? '连接中…' : name }}</b
              ><el-icon><Right /></el-icon>
            </button>
          </div>
          <small>仅本地开发环境可用。样例订单不代表真实交易。</small>
        </div>
      </div>
      <div class="login-legal">供需有据 · 品质可查 · 交付可追溯</div>
    </section>
  </div>
</template>
<style scoped>
.login-page {
  min-height: 100vh;
  display: grid;
  grid-template-columns: 1.05fr 1fr;
  background: #fff;
}
.login-story {
  position: relative;
  background: #173e30;
  color: #fff;
  padding: 45px 55px;
  overflow: hidden;
  display: flex;
  flex-direction: column;
}
.login-story:after {
  content: '';
  position: absolute;
  inset: 0;
  background:
    linear-gradient(180deg, #163c30a6, #14382be8),
    url('https://images.unsplash.com/photo-1500382017468-9049fed747ef?auto=format&fit=crop&w=1600&q=85')
      center/cover;
  z-index: 0;
}
.login-story > * {
  position: relative;
  z-index: 1;
}
.login-brand {
  display: flex;
  align-items: center;
  gap: 12px;
  font-size: 22px;
  font-weight: 600;
}
.login-brand .el-icon {
  background: #cae8b8;
  color: #20432d;
  width: 35px;
  height: 35px;
  border-radius: 9px;
}
.story-center {
  margin: auto 0;
  padding: 80px 0;
}
.story-center h1 {
  font-size: clamp(40px, 4.2vw, 70px);
  font-weight: 500;
  line-height: 1.4;
  letter-spacing: -2px;
}
.story-center p {
  font-size: 15px;
  line-height: 2;
  color: #d2e2d6;
  margin-top: 25px;
}
.story-line {
  width: 45px;
  height: 3px;
  background: #c7e6b4;
  margin-bottom: 32px;
}
.story-flow {
  display: flex;
  align-items: center;
  gap: 20px;
  margin-top: 55px;
  font-size: 12px;
  color: #dce9df;
}
.story-flow .el-icon {
  color: #9cbb9e;
}
.story-bottom {
  display: flex;
  justify-content: space-between;
  font-size: 10px;
  color: #b4cdbc;
  gap: 15px;
}
.login-form-side {
  padding: 40px;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
}
.login-form {
  width: min(100%, 390px);
}
.login-icon {
  width: 42px;
  height: 42px;
  background: #e9f4ec;
  color: var(--brand);
  display: grid;
  place-items: center;
  border-radius: 10px;
  font-size: 25px;
  margin-bottom: 25px;
}
.login-form h2 {
  font-size: 27px;
  margin-bottom: 10px;
  letter-spacing: -0.6px;
}
.login-form > p {
  font-size: 13px;
}
.login-tabs {
  display: flex;
  gap: 28px;
  margin: 32px 0 23px;
  border-bottom: 1px solid var(--line);
}
.login-tabs button {
  padding: 0 0 13px;
  border: 0;
  background: none;
  color: var(--muted);
  font-size: 13px;
}
.login-tabs button.active {
  border-bottom: 2px solid var(--brand);
  color: var(--brand);
  font-weight: 600;
}
.demo-section {
  margin-top: 32px;
  border-top: 1px solid var(--line);
  padding-top: 23px;
}
.demo-heading {
  display: flex;
  justify-content: space-between;
  align-items: center;
  font-size: 12px;
  color: var(--muted);
  margin-bottom: 12px;
}
.demo-buttons {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 9px;
}
.demo-buttons button {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  background: #f7f9f7;
  border: 1px solid var(--line);
  border-radius: 7px;
  padding: 13px 7px;
  flex: 1;
  color: #40594b;
}
.demo-buttons button:hover {
  background: #edf6ef;
  border-color: #9bc6ad;
}
.demo-buttons b {
  font-weight: 500;
  font-size: 12px;
}
.demo-buttons button > .el-icon:last-child {
  font-size: 10px;
}
.demo-section small {
  display: block;
  color: var(--muted);
  font-size: 10px;
  margin-top: 12px;
}
.login-legal {
  font-size: 10px;
  color: #8c9990;
  margin-top: 35px;
}
@media (max-width: 850px) {
  .login-page {
    grid-template-columns: 1fr;
  }
  .login-story {
    display: none;
  }
  .login-form-side {
    min-height: 100vh;
    padding: 30px 22px;
  }
}
</style>
