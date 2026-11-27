<script setup>
import { ref, reactive, computed, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import request from '@/utils/request'
import { useWorkspace } from '@/stores/workspace'
const w = useWorkspace(),
  companies = ref([]),
  selected = ref(null),
  dialog = ref(''),
  busy = ref(false),
  form = reactive({})
const current = computed(() => companies.value.find((c) => c.id === selected.value)),
  jobs = {
    owner: '主体负责人',
    manager: '业务管理',
    buyer: '采购岗位',
    quality: '质检岗位',
    dispatch: '交付岗位',
    viewer: '资料查看',
  }
async function load() {
  try {
    companies.value = (await request.get('/workspace/companies/')).data
    if (!selected.value) selected.value = companies.value[0]?.id
  } catch {
    ElMessage.error('企业资料暂时无法载入')
  }
}
function open(action) {
  dialog.value = action
  Object.assign(form, {
    name: '',
    kind: action === 'site' ? 'store' : w.isBuyer ? 'buyer' : 'supplier',
    coordinate_source: '人工录入',
    coordinate_system: 'WGS84',
    location_verified: false,
    address: '',
    location: '',
    contact: '',
    phone: '',
    username: '',
    job: 'viewer',
  })
}
async function save() {
  busy.value = true
  try {
    await w.act(
      'companies/',
      { ...form, action: dialog.value, company_id: selected.value },
      '企业资料已保存',
    )
    dialog.value = ''
    await load()
  } catch {
    // Operation errors are shown by the shared workspace action; dialog cancellation is intentional.
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
        <h1>企业与站点</h1>
        <p>集中维护合作主体、门店、集配点与岗位资料，为采购与交付复用准确位置。</p>
      </div>
      <el-button type="primary" icon="Plus" @click="open('create')">新增业务主体</el-button>
    </div>
    <div class="record-layout">
      <section class="panel">
        <div class="panel-head"><h2>我的业务主体</h2></div>
        <button
          v-for="c in companies"
          :key="c.id"
          class="task-list-item"
          :class="{ active: selected === c.id }"
          @click="selected = c.id"
        >
          <strong>{{ c.name }}</strong>
          <p>{{ c.sites.length }} 个站点 / {{ c.members.length }} 名成员</p>
        </button>
        <div v-if="!companies.length" class="compact-empty">先建立业务主体，再维护站点与岗位。</div>
      </section>
      <div v-if="current">
        <section class="panel">
          <div class="panel-head">
            <h2>{{ current.name }} / 站点</h2>
            <el-button
              v-if="current.owner_id === w.state.user.id"
              type="primary"
              plain
              @click="open('site')"
              >新增站点</el-button
            >
          </div>
          <div class="panel-body">
            <article v-for="s in current.sites" :key="s.id" class="site-card">
              <h3>
                <el-icon><Location /></el-icon> {{ s.name }}
              </h3>
              <p>
                {{ s.address }}<br />{{ s.contact }} {{ s.phone }}<br />{{
                  s.location || '经纬度尚未录入'
                }}
              </p>
            </article>
            <el-empty
              v-if="!current.sites.length"
              description="暂无站点，录入后可在产地网络查看"
              :image-size="60"
            />
          </div>
        </section>
        <section class="panel section-gap">
          <div class="panel-head">
            <h2>成员与岗位</h2>
            <el-button v-if="current.owner_id === w.state.user.id" plain @click="open('member')"
              >维护成员</el-button
            >
          </div>
          <el-table :data="current.members"
            ><el-table-column prop="user__username" label="成员账号" /><el-table-column label="岗位"
              ><template #default="{ row }">{{ jobs[row.job] }}</template></el-table-column
            ></el-table
          >
          <div class="panel-body">
            <p class="data-note">
              岗位资料与平台交易身份分别管理。当前账号可执行的交易操作仍由服务器权限校验；记录岗位不会授予管理员权限。
            </p>
          </div>
        </section>
      </div>
    </div>
    <el-dialog
      :model-value="!!dialog"
      :title="
        dialog === 'create' ? '新增业务主体' : dialog === 'site' ? '录入站点' : '维护成员岗位'
      "
      width="540px"
      @close="dialog = ''"
      ><el-form label-position="top"
        ><template v-if="dialog === 'member'"
          ><el-form-item label="已注册账号"><el-input v-model="form.username" /></el-form-item
          ><el-form-item label="岗位"
            ><el-select v-model="form.job"
              ><el-option
                v-for="(v, k) in jobs"
                :key="k"
                :label="v"
                :value="k"
                :disabled="k === 'owner'" /></el-select></el-form-item></template
        ><template v-else
          ><el-form-item :label="dialog === 'site' ? '站点名称' : '主体名称'"
            ><el-input v-model="form.name" /></el-form-item
          ><template v-if="dialog === 'site'"
            ><el-form-item label="站点类型"
              ><el-select v-model="form.kind"
                ><el-option label="门店" value="store" /><el-option
                  label="中央厨房"
                  value="kitchen" /><el-option label="集配中心" value="hub" /><el-option
                  label="产地"
                  value="origin" /></el-select></el-form-item
            ><el-form-item label="详细地址"><el-input v-model="form.address" /></el-form-item
            ><el-form-item label="经度,纬度 / 未知可留空"
              ><el-input v-model="form.location" placeholder="WGS84/CGCS2000 经度,纬度；未知留空"
            /></el-form-item>
            <div class="mobile-form-row">
              <el-form-item label="坐标系"
                ><el-select v-model="form.coordinate_system"
                  ><el-option label="WGS84" value="WGS84" /><el-option
                    label="CGCS2000"
                    value="CGCS2000" /></el-select></el-form-item
              ><el-form-item label="坐标来源"
                ><el-input v-model="form.coordinate_source" placeholder="例如：现场定位或人工标注"
              /></el-form-item>
            </div>
            <el-checkbox v-model="form.location_verified" :disabled="!form.location"
              >已核对坐标与实际收货点一致</el-checkbox
            >
            <div class="mobile-form-row">
              <el-form-item label="联系人"><el-input v-model="form.contact" /></el-form-item
              ><el-form-item label="电话"
                ><el-input v-model="form.phone"
              /></el-form-item></div></template></template></el-form
      ><template #footer
        ><el-button @click="dialog = ''">取消</el-button
        ><el-button type="primary" :loading="busy" @click="save">保存资料</el-button></template
      ></el-dialog
    >
  </div>
</template>
