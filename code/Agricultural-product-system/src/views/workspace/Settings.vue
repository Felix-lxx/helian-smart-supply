<script setup>
import { ref, reactive, onMounted } from 'vue'
import request from '@/utils/request'
import { useWorkspace, labels, dateText } from '@/stores/workspace'
import StatusBadge from '@/components/StatusBadge.vue'
import { ElMessage, ElMessageBox } from 'element-plus'
const w = useWorkspace(),
  tab = ref('profile'),
  profile = reactive({ phone: '', motto: '' }),
  addresses = ref([]),
  auth = ref({ status: 'unverified' }),
  identity = reactive({ real_name: '', id_card_no: '' }),
  addr = reactive({ receiver_name: '', receiver_phone: '', detail_address: '', is_default: false }),
  addrDialog = ref(false),
  editId = ref(null),
  busy = ref(false)
async function load() {
  try {
    const [p, a, r] = await Promise.all([
      request.get('/user/profile/'),
      request.get('/addresses/'),
      request.get('/realname/status/'),
    ])
    Object.assign(profile, p.data)
    addresses.value = a.data.results || a.data
    auth.value = r.data
  } catch {
    ElMessage.error('账户资料获取失败')
  }
}
async function saveProfile() {
  busy.value = true
  try {
    await request.patch('/user/profile/', { phone: profile.phone || null, motto: profile.motto })
    await w.refresh(true)
    ElMessage.success('账户资料已保存')
  } catch {
    ElMessage.error('保存失败，请检查手机号是否重复或格式正确')
  } finally {
    busy.value = false
  }
}
function edit(a) {
  editId.value = a?.id || null
  Object.assign(
    addr,
    { receiver_name: '', receiver_phone: '', detail_address: '', is_default: false },
    a || {},
  )
  addrDialog.value = true
}
async function saveAddress() {
  if (!addr.receiver_name || !addr.receiver_phone || !addr.detail_address)
    return ElMessage.warning('请补全收货信息')
  busy.value = true
  try {
    if (editId.value) await request.patch(`/addresses/${editId.value}/`, addr)
    else await request.post('/addresses/', addr)
    await load()
    addrDialog.value = false
    ElMessage.success('收货地址已保存')
  } catch {
    ElMessage.error('保存地址失败')
  } finally {
    busy.value = false
  }
}
async function remove(a) {
  try {
    await ElMessageBox.confirm('只删除地址簿记录，不影响历史订单收货快照。', '删除收货地址')
    await request.delete(`/addresses/${a.id}/`)
    await load()
  } catch {}
}
async function submitIdentity() {
  busy.value = true
  try {
    await request.post('/realname/submit/', identity)
    identity.id_card_no = ''
    await load()
    ElMessage.success('资料已提交人工审核')
  } catch (e) {
    ElMessage.error(e.response?.data?.error || '提交失败，请检查姓名和证件号')
  } finally {
    busy.value = false
  }
}
onMounted(load)
</script>
<template>
  <div class="page">
    <div class="page-head">
      <div>
        <h1>账户与设置</h1>
        <p>管理联系资料、常用地址和主体审核记录。</p>
      </div>
      <span class="status-badge released"><i></i>{{ labels[w.role] }}</span>
    </div>
    <section class="panel">
      <div class="toolbar">
        <div class="pill-tabs">
          <button
            v-for="[id, n] in [
              ['profile', '账户资料'],
              ['addresses', '收货地址'],
              ...(!w.isAdmin ? [['identity', '主体资料审核']] : []),
            ]"
            :key="id"
            :class="{ active: tab === id }"
            @click="tab = id"
          >
            {{ n }}
          </button>
        </div>
      </div>
      <div class="settings-body" v-if="tab === 'profile'">
        <div class="profile-heading">
          <span>{{ w.state.user.username?.slice(0, 1)?.toUpperCase() }}</span>
          <div>
            <h2>{{ w.state.user.username }}</h2>
            <p>
              {{ labels[w.role] }} ·
              {{ w.state.user.username?.startsWith('demo_') ? '本地演示工作区' : '业务工作区' }}
            </p>
          </div>
        </div>
        <el-form label-position="top"
          ><el-form-item label="联系手机号"
            ><el-input
              v-model="profile.phone"
              maxlength="11"
              placeholder="用于供需沟通与收货联系" /></el-form-item
          ><el-form-item label="业务介绍"
            ><el-input
              v-model="profile.motto"
              maxlength="100"
              placeholder="介绍你的采购或供货需求" /></el-form-item
          ><el-button type="primary" :loading="busy" @click="saveProfile"
            >保存资料</el-button
          ></el-form
        >
        <div class="info-strip section-gap">
          角色与账号权限由平台管理，不能通过修改个人资料自行提升。
        </div>
      </div>
      <div v-if="tab === 'addresses'" class="panel-body">
        <div class="row-actions" style="margin-bottom: 18px">
          <el-button type="primary" icon="Plus" @click="edit()">新增收货地址</el-button>
        </div>
        <div class="address-grid">
          <article v-for="a in addresses" :key="a.id" class="address-card">
            <div class="row-actions">
              <h3>{{ a.receiver_name }}</h3>
              <span v-if="a.is_default" class="status-badge released">默认地址</span>
            </div>
            <p>{{ a.receiver_phone }}</p>
            <p>{{ a.detail_address }}</p>
            <div class="row-actions">
              <el-button link type="primary" @click="edit(a)">编辑</el-button
              ><el-button link type="danger" @click="remove(a)">删除</el-button>
            </div>
          </article>
        </div>
        <el-empty v-if="!addresses.length" description="还没有收货地址" :image-size="80" />
      </div>
      <div v-if="tab === 'identity'" class="settings-body">
        <div class="info-strip warning">
          此处为主体资料人工审核，未接入官方实人认证和活体检测。系统不会生成虚拟照片或自动宣称身份核实成功。
        </div>
        <div class="kv section-gap">
          <span>当前进度</span
          ><b>{{
            {
              unverified: '尚未提交',
              pending: '待人工审核',
              approved: '人工审核通过',
              rejected: '需补充资料',
            }[auth.status] || auth.status
          }}</b>
        </div>
        <div v-if="auth.reject_reason" class="info-strip warning section-gap">
          补充要求：{{ auth.reject_reason }}
        </div>
        <template v-if="['unverified', 'rejected'].includes(auth.status)"
          ><el-form label-position="top" class="section-gap"
            ><el-form-item label="提交姓名"
              ><el-input v-model="identity.real_name" maxlength="50" /></el-form-item
            ><el-form-item label="证件号码"
              ><el-input
                v-model="identity.id_card_no"
                maxlength="18"
                placeholder="用于提交人工审核，保存后仅展示脱敏信息" /></el-form-item
            ><el-button type="primary" :loading="busy" @click="submitIdentity"
              >提交人工审核</el-button
            ></el-form
          ></template
        ><template v-else
          ><div class="kv">
            <span>姓名</span><b>{{ auth.real_name }}</b>
          </div>
          <div class="kv">
            <span>证件信息</span><b>{{ auth.id_card_masked }}</b>
          </div>
          <div class="kv">
            <span>审核时间</span><b>{{ dateText(auth.reviewed_at) }}</b>
          </div></template
        >
      </div>
    </section>
    <el-dialog v-model="addrDialog" :title="editId ? '编辑收货地址' : '新增收货地址'" width="500px"
      ><el-form label-position="top"
        ><el-form-item label="收货联系人"><el-input v-model="addr.receiver_name" /></el-form-item
        ><el-form-item label="联系电话"><el-input v-model="addr.receiver_phone" /></el-form-item
        ><el-form-item label="详细地址"
          ><el-input v-model="addr.detail_address" type="textarea" :rows="3" /></el-form-item
        ><el-checkbox v-model="addr.is_default">设为默认收货地址</el-checkbox></el-form
      ><template #footer
        ><el-button @click="addrDialog = false">取消</el-button
        ><el-button type="primary" :loading="busy" @click="saveAddress"
          >保存地址</el-button
        ></template
      ></el-dialog
    >
  </div>
</template>
<style scoped>
.settings-body {
  max-width: 610px;
  padding: 30px;
}
.profile-heading {
  display: flex;
  align-items: center;
  gap: 18px;
  margin-bottom: 30px;
}
.profile-heading > span {
  width: 60px;
  height: 60px;
  border-radius: 14px;
  display: grid;
  place-items: center;
  background: #e5eee1;
  color: #3c6c3e;
  font-size: 27px;
}
.profile-heading p {
  font-size: 12px;
  color: var(--muted);
  margin-top: 10px;
}
.address-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 18px;
}
.address-card {
  border: 1px solid var(--line);
  padding: 22px;
  border-radius: 9px;
}
.address-card p {
  font-size: 12px;
  color: var(--muted);
  margin: 14px 0;
  line-height: 1.8;
}
@media (max-width: 1050px) {
  .address-grid {
    grid-template-columns: 1fr 1fr;
  }
}
@media (max-width: 700px) {
  .settings-body {
    padding: 20px;
  }
  .address-grid {
    grid-template-columns: 1fr;
  }
}
</style>
