<script setup>
import { ref, onMounted, computed } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import request from '@/utils/request'
import { useWorkspace, money, qty, labels, dateText } from '@/stores/workspace'
import StatusBadge from '@/components/StatusBadge.vue'
import BusinessChart from '@/components/BusinessChart.vue'
const w = useWorkspace(),
  tab = ref('overview'),
  users = ref([]),
  auths = ref([]),
  search = ref(''),
  busy = ref(false),
  detail = ref(null),
  authVisible = ref(false)
const analytics = ref({
    orders: 0,
    confirmed_receipts: 0,
    confirmed_count: 0,
    completed: 0,
    issues: 0,
    refunds: 0,
    supplements: 0,
    stages: [],
  }),
  excludeDemo = ref(false),
  dates = ref([])
async function load() {
  try {
    const [u, a, s] = await Promise.all([
      request.get('/workspace/users/'),
      request.get('/admin/realname/pending/'),
      request.get('/workspace/analytics/', {
        params: {
          exclude_demo: excludeDemo.value ? '1' : '0',
          start: dates.value?.[0],
          end: dates.value?.[1],
        },
      }),
    ])
    users.value = u.data
    auths.value = a.data.results || a.data
    analytics.value = s.data
  } catch {
    ElMessage.error('运营数据获取失败')
  }
}
async function toggle(u) {
  try {
    await ElMessageBox.confirm(
      `确认${u.is_active ? '停用' : '启用'}账号 ${u.username}？`,
      '账号状态变更',
      { type: 'warning' },
    )
    users.value = await w.act('users/', { id: u.id, active: !u.is_active }, '账号状态已更新')
    await load()
  } catch {}
}
async function audit(a, approve) {
  try {
    let reason = ''
    if (!approve) {
      const r = await ElMessageBox.prompt('请说明需要补充或修正的资料', '驳回申请', {
        inputType: 'textarea',
        inputValidator: (v) => !!v?.trim() || '请填写原因',
      })
      reason = r.value
    }
    busy.value = true
    await request.post(`/admin/realname/${a.id}/${approve ? 'approve' : 'reject'}/`, { reason })
    ElMessage.success(approve ? '已通过人工审核' : '已驳回，请申请方补充资料')
    authVisible.value = false
    await load()
  } catch {
  } finally {
    busy.value = false
  }
}
const filtered = computed(() =>
  users.value.filter((u) => (u.username + (u.phone || '')).includes(search.value)),
)
const funnel = computed(() => ({
  tooltip: { trigger: 'item' },
  color: ['#1e7350', '#5b9c73', '#a2c193', '#d4dfc0'],
  series: [
    {
      type: 'funnel',
      left: '28%',
      width: '58%',
      top: 15,
      bottom: 20,
      sort: 'none',
      gap: 6,
      label: { position: 'left', color: '#31533f', fontSize: 12, formatter: '{b}  {c}' },
      labelLine: { length: 12, lineStyle: { color: '#a6baa9' } },
      data: [
        { name: '全部订单', value: analytics.value.orders },
        {
          name: '收款已确认',
          value: analytics.value.confirmed_count,
        },
        {
          name: '已发运或完成',
          value: analytics.value.stages
            .filter((o) => ['shipped', 'completed', 'issue'].includes(o.status))
            .reduce((s, o) => s + o.count, 0),
        },
        {
          name: '验收已完成',
          value: analytics.value.completed,
        },
      ],
    },
  ],
}))
onMounted(load)
</script>
<template>
  <div class="page">
    <div class="page-head">
      <div>
        <h1>运营中心</h1>
        <p>审核主体、跟进异常与查看经营结果。数据均可追溯至具体订单或记录。</p>
      </div>
      <el-button
        icon="Refresh"
        @click="
          () => {
            load()
            w.refresh()
          }
        "
        >同步运营数据</el-button
      >
    </div>
    <div class="panel">
      <div class="toolbar">
        <div class="pill-tabs">
          <button
            v-for="[id, n] in [
              ['overview', '经营概览'],
              ['users', '用户与权限'],
              ['auth', '主体资料审核'],
            ]"
            :key="id"
            :class="{ active: tab === id }"
            @click="tab = id"
          >
            {{ n }} <span v-if="id === 'auth' && auths.length">({{ auths.length }})</span>
          </button>
        </div>
        <el-input
          v-if="tab === 'users'"
          v-model="search"
          placeholder="搜索账号或联系电话"
          prefix-icon="Search"
          clearable
        />
      </div>
    </div>
    <template v-if="tab === 'overview'"
      ><div class="panel section-gap">
        <div class="panel-body decision-toolbar">
          <el-date-picker
            v-model="dates"
            type="daterange"
            value-format="YYYY-MM-DD"
            start-placeholder="开始日期"
            end-placeholder="结束日期"
            style="max-width: 330px"
            @change="load"
          /><el-switch v-model="excludeDemo" active-text="排除演示订单" @change="load" /><span
            class="small muted"
            >按完整数据库记录聚合，可核对至具体订单</span
          >
        </div>
      </div>
      <div class="metrics section-gap">
        <div class="metric">
          <div class="metric-label">已确认收款金额</div>
          <div class="metric-value">¥{{ money(analytics.confirmed_receipts) }}</div>
          <div class="metric-foot">人工核对净收款，非平台收入</div>
        </div>
        <div class="metric">
          <div class="metric-label">交易账号</div>
          <div class="metric-value">{{ users.length }}</div>
          <div class="metric-foot">含开发演示账号</div>
        </div>
        <div class="metric">
          <div class="metric-label">履约完成率</div>
          <div class="metric-value">
            {{ analytics.orders ? ((analytics.completed / analytics.orders) * 100).toFixed(1) : '0'
            }}<small>%</small>
          </div>
          <div class="metric-foot">完成订单 / 全部订单</div>
        </div>
        <div class="metric">
          <div class="metric-label">验收异常</div>
          <div class="metric-value warn">{{ analytics.issues || 0 }}</div>
          <div class="metric-foot">待双方确认处理的订单</div>
        </div>
      </div>
      <section class="panel section-gap">
        <div class="panel-body decision-toolbar">
          <span class="small"
            >已核对退款 / 折让 <b>¥{{ money(analytics.refunds) }}</b></span
          ><span class="small"
            >已核对补款 <b>¥{{ money(analytics.supplements) }}</b></span
          ><span class="small muted">{{
            w.collaboration.job
              ? '到期服务最近检查 ' + dateText(w.collaboration.job.created_at)
              : '到期服务尚无运行记录'
          }}</span>
        </div>
      </section>
      <div class="grid-equal section-gap">
        <section class="panel">
          <div class="panel-head">
            <h2>订单处理阶段</h2>
            <span class="small muted">按当前状态统计</span>
          </div>
          <BusinessChart :option="funnel" height="320px" />
        </section>
        <section class="panel">
          <div class="panel-head"><h2>运营待办</h2></div>
          <div class="panel-body">
            <router-link to="/orders?status=issue" class="list-row"
              ><div>
                <h3>验收差异与协商</h3>
                <p>核实原因、查看处理方案及确认进度</p>
              </div>
              <b class="warn">{{ w.state.stats.issues || 0 }}</b></router-link
            ><router-link to="/quality" class="list-row"
              ><div>
                <h3>待检与隔离批次</h3>
                <p>复核前不进入可售库存</p>
              </div>
              <b>{{
                w.state.batches.filter((b) => b.status !== 'released').length
              }}</b></router-link
            ><button class="audit-todo list-row" @click="tab = 'auth'">
              <div>
                <h3>主体资料待审核</h3>
                <p>人工核对提交资料，不代表官方身份核验</p>
              </div>
              <b>{{ auths.length }}</b></button
            ><router-link to="/allocation" class="list-row"
              ><div>
                <h3>供需缺口与试算</h3>
                <p>比较品种、交期和抽检证据</p>
              </div>
              <el-icon><Right /></el-icon
            ></router-link>
          </div>
        </section>
      </div>
      <div class="info-strip section-gap">
        口径说明：金额来自收款方确认的订单；尚未接入自动收款、退款或平台佣金核算。当前统计包含演示标记记录，不能作为实际营收或比赛业绩。
      </div></template
    >
    <section v-if="tab === 'users'" class="panel section-gap">
      <el-table :data="filtered"
        ><el-table-column label="账号" prop="username" min-width="170" /><el-table-column
          label="角色"
          width="140"
          ><template #default="{ row }">{{
            labels[row.role] || row.role
          }}</template></el-table-column
        ><el-table-column label="联系电话" min-width="150"
          ><template #default="{ row }">{{ row.phone || '未填写' }}</template></el-table-column
        ><el-table-column label="加入时间" min-width="150"
          ><template #default="{ row }">{{ dateText(row.date_joined) }}</template></el-table-column
        ><el-table-column label="状态" width="110"
          ><template #default="{ row }"
            ><span :class="row.is_active ? 'good' : 'danger'">{{
              row.is_active ? '正常' : '已停用'
            }}</span></template
          ></el-table-column
        ><el-table-column label="操作" width="130"
          ><template #default="{ row }"
            ><el-button
              link
              :disabled="row.id === w.state.user.id"
              :type="row.is_active ? 'danger' : 'primary'"
              @click="toggle(row)"
              >{{ row.is_active ? '停用账号' : '启用账号' }}</el-button
            ></template
          ></el-table-column
        ></el-table
      >
    </section>
    <section v-if="tab === 'auth'" class="panel section-gap">
      <el-table :data="auths"
        ><el-table-column label="申请账号" prop="username" min-width="160" /><el-table-column
          label="姓名"
          prop="real_name"
          min-width="120"
        /><el-table-column
          label="证件信息（脱敏）"
          prop="id_card_masked"
          min-width="170"
        /><el-table-column label="提交时间" min-width="150"
          ><template #default="{ row }">{{ dateText(row.submitted_at) }}</template></el-table-column
        ><el-table-column label="审核" width="130"
          ><template #default="{ row }"
            ><el-button
              link
              type="primary"
              @click="
                () => {
                  detail = row
                  authVisible = true
                }
              "
              >查看并处理</el-button
            ></template
          ></el-table-column
        ></el-table
      >
    </section>
    <el-dialog v-model="authVisible" title="主体资料人工审核" width="520px"
      ><template v-if="detail"
        ><div class="kv">
          <span>申请账号</span><b>{{ detail.username }}</b>
        </div>
        <div class="kv">
          <span>提交姓名</span><b>{{ detail.real_name }}</b>
        </div>
        <div class="kv">
          <span>脱敏证件号</span><b>{{ detail.id_card_masked }}</b>
        </div>
        <el-image
          v-if="detail.face_image_url"
          :src="detail.face_image_url"
          fit="contain"
          style="width: 100%; height: 180px; margin-top: 15px"
        />
        <div class="info-strip warning section-gap">
          仅对提交资料做人工复核，系统未接入官方实人认证或活体检测服务。
        </div></template
      ><template #footer
        ><el-button :loading="busy" @click="audit(detail, false)">要求补充资料</el-button
        ><el-button type="primary" :loading="busy" @click="audit(detail, true)"
          >人工审核通过</el-button
        ></template
      ></el-dialog
    >
  </div>
</template>
<style scoped>
.metric-value small {
  font-size: 13px;
  font-weight: 400;
}
.audit-todo {
  width: 100%;
  text-align: left;
  background: none;
  border: 0;
  border-bottom: 1px solid var(--line);
  color: inherit;
  padding-left: 0;
  padding-right: 0;
  cursor: pointer;
}
</style>
