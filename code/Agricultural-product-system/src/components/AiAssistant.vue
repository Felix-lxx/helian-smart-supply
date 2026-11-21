<script setup>
import { ref, nextTick } from 'vue'
import { useRouter } from 'vue-router'
import request from '@/utils/request'
const router = useRouter(),
  visible = ref(false),
  external = ref(false),
  input = ref(''),
  busy = ref(false),
  body = ref(),
  messages = ref([
    {
      role: 'assistant',
      text: '你好，我可以整理当前工作区的订单待办，解释抽检与分货规则，并带你找到对应业务记录。',
    },
  ])
async function send(question) {
  const q = question || input.value.trim()
  if (!q || busy.value) return
  input.value = ''
  const allowExternal = external.value
  external.value = false
  messages.value.push({ role: 'user', text: q })
  busy.value = true
  try {
    const r = (
      await request.post(
        '/workspace/assistant/',
        { question: q, allow_external: allowExternal },
        { timeout: 18000 },
      )
    ).data
    messages.value.push({ role: 'assistant', text: r.answer, source: r.source, actions: r.actions })
  } catch {
    messages.value.push({
      role: 'assistant',
      text: '暂时无法读取业务摘要。可先进入订单履约或品质工作台查看原始记录，稍后再试。',
    })
  } finally {
    busy.value = false
    await nextTick()
    body.value?.scrollTo({ top: body.value.scrollHeight, behavior: 'smooth' })
  }
}
</script>
<template>
  <div class="assistant-widget">
    <button class="assistant-trigger" @click="visible = !visible" aria-label="打开业务助手">
      <el-icon><ChatDotRound /></el-icon><span>业务助手</span>
    </button>
    <section v-if="visible" class="assistant-window">
      <header>
        <div>
          <el-icon><Connection /></el-icon><b>禾链业务助手</b>
        </div>
        <button @click="visible = false" aria-label="关闭业务助手">
          <el-icon><Close /></el-icon>
        </button>
      </header>
      <div ref="body" class="assistant-body">
        <article v-for="(m, i) in messages" :key="i" :class="m.role">
          <p>{{ m.text }}</p>
          <small v-if="m.source">{{ m.source }}</small>
          <div v-if="m.actions" class="assistant-actions">
            <button
              v-for="a in m.actions"
              :key="a.route"
              @click="
                () => {
                  router.push(a.route)
                  visible = false
                }
              "
            >
              {{ a.label }} <el-icon><Right /></el-icon>
            </button>
          </div>
        </article>
        <p v-if="busy" class="thinking">正在读取与整理业务记录…</p>
      </div>
      <div class="assistant-suggestions">
        <button @click="send('当前哪些订单需要优先处理？')" :disabled="busy">查看今日待办</button
        ><button @click="send('分货试算和报价成交有什么区别？')" :disabled="busy">
          了解分货流程
        </button>
      </div>
      <label class="assistant-external"
        ><input
          type="checkbox"
          v-model="external"
          :disabled="busy"
        />本次允许将工作区统计与问题发送至 DeepSeek</label
      >
      <form class="assistant-input" @submit.prevent="send()">
        <input
          v-model="input"
          placeholder="询问订单、品质与分货…"
          :disabled="busy"
          maxlength="1500"
        /><button type="submit" :disabled="busy || !input.trim()" aria-label="发送">
          <el-icon><Top /></el-icon>
        </button>
      </form>
      <footer>默认本地摘要 · 外部解读须选择 · 不自动执行交易</footer>
    </section>
  </div>
</template>
<style scoped>
.assistant-widget {
  position: relative;
  z-index: 90;
}
.assistant-external {
  display: flex;
  gap: 7px;
  align-items: flex-start;
  margin: 8px 15px 0;
  font-size: 11px;
  color: #536f60;
  line-height: 1.7;
}
.assistant-external input {
  accent-color: #17694d;
  margin-top: 3px;
}
.assistant-trigger {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 7px 10px;
  background: #eff5f1;
  color: #245b43;
  border: 1px solid #d9e6dc;
  border-radius: 7px;
  font-size: 12px;
}
.assistant-trigger .el-icon {
  font-size: 18px;
}
.assistant-window {
  position: fixed;
  top: 78px;
  right: 24px;
  width: 390px;
  height: 550px;
  max-height: calc(100vh - 130px);
  display: flex;
  flex-direction: column;
  border: 1px solid #cfdcd0;
  border-radius: 13px;
  background: #fff;
  overflow: hidden;
  box-shadow: 0 15px 45px #22382725;
}
.assistant-window header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 17px 18px;
  background: #f0f6ed;
  border-bottom: 1px solid var(--line);
}
.assistant-window header > div {
  display: flex;
  align-items: center;
  gap: 10px;
  color: #2d5f3b;
}
.assistant-window header b {
  font-size: 13px;
  font-weight: 500;
}
.assistant-window header button {
  border: 0;
  background: none;
  color: #5f7663;
}
.assistant-body {
  flex: 1;
  overflow: auto;
  padding: 18px;
}
.assistant-body article {
  font-size: 12px;
  line-height: 1.9;
  margin-bottom: 18px;
}
.assistant-body article p {
  white-space: pre-wrap;
}
.assistant-body article.user {
  background: #edf4e9;
  padding: 10px 13px;
  border-radius: 9px;
  margin-left: 35px;
}
.assistant-body small {
  display: block;
  font-size: 10px;
  color: var(--muted);
  margin-top: 10px;
}
.assistant-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  margin-top: 12px;
}
.assistant-actions button {
  background: #fff;
  border: 1px solid var(--line);
  padding: 5px 8px;
  border-radius: 5px;
  color: #32754d;
  font-size: 10px;
}
.assistant-suggestions {
  padding: 10px 15px;
  display: flex;
  gap: 8px;
  border-top: 1px solid var(--line);
}
.assistant-suggestions button {
  border: 0;
  background: #f0f4ed;
  padding: 6px 9px;
  border-radius: 5px;
  font-size: 10px;
  color: #59735b;
}
.assistant-input {
  display: flex;
  gap: 8px;
  padding: 0 15px 10px;
}
.assistant-input input {
  min-width: 0;
  flex: 1;
  border: 1px solid #d9e3d7;
  background: #fff;
  border-radius: 7px;
  padding: 10px;
  font-size: 12px;
  outline-color: #78a47d;
}
.assistant-input button {
  border: 0;
  border-radius: 6px;
  background: #276a47;
  color: white;
  width: 35px;
}
.assistant-input button:disabled {
  opacity: 0.4;
}
.assistant-window footer {
  text-align: center;
  font-size: 9px;
  color: #849283;
  padding: 0 10px 10px;
}
.thinking {
  font-size: 12px;
  color: var(--muted);
}
@media (max-width: 600px) {
  .assistant-widget {
    position: relative;
  }
  .assistant-trigger span {
    display: none;
  }
  .assistant-trigger {
    padding: 6px;
  }
  .assistant-window {
    width: min(360px, calc(100vw - 85px));
    right: 12px;
    top: 70px;
  }
}
</style>
