<template>
  <div class="product-detail-container" v-loading="loading">
    <el-row :gutter="40">
      <el-col :span="10">
        <el-card class="image-card" :body-style="{ padding: '0px' }">
          <el-image :src="product.image_url" fit="cover" class="main-image">
            <template #error>
              <div class="image-placeholder">暂无商品图片</div>
            </template>
          </el-image>
          <div class="rs-overlay" v-if="product.remote_sensing">
            <div class="rs-item">
              <span class="label">NDVI 指数</span>
              <span class="value">{{ product.remote_sensing.ndvi_index }}</span>
            </div>
            <div class="rs-item">
              <span class="label">土壤湿度</span>
              <span class="value">{{ product.remote_sensing.soil_moisture }}%</span>
            </div>
          </div>
        </el-card>
      </el-col>

      <el-col :span="14">
        <div class="info-section">
          <h1 class="product-name">{{ product.name }}</h1>
          <p class="origin-tag"><el-icon><Location /></el-icon> 产地：{{ product.origin }}</p>

          <div class="price-box">
            <span class="currency">￥</span>
            <span class="amount">{{ product.retail_price }}</span>
            <el-tag type="success" size="small" class="status-tag">溯源已存证</el-tag>
          </div>

          <el-descriptions :column="1" border class="detail-desc">
            <el-descriptions-item label="库存状态">{{ product.stock > 0 ? `充足 (${product.stock})` : '已售罄' }}</el-descriptions-item>
            <el-descriptions-item label="分类">{{ categoryMap[product.category] || product.category }}</el-descriptions-item>
            <el-descriptions-item label="上架时间">{{ product.created_at ? new Date(product.created_at).toLocaleDateString() : '' }}</el-descriptions-item>
          </el-descriptions>

          <div class="expert-section" v-if="product.remote_sensing">
            <h3 class="section-title"><el-icon><Monitor /></el-icon> AI 专家解读</h3>
            <p class="analysis-text">{{ product.remote_sensing.expert_analysis }}</p>
          </div>

          <div class="action-bar">
            <el-button
              type="primary"
              size="large"
              class="buy-btn"
              :disabled="product.stock <= 0"
              @click="handleBuy"
            >
              立即订购
            </el-button>
          </div>
        </div>
      </el-col>
    </el-row>

    <div class="comments-section mt-20">
      <el-card shadow="never">
        <template #header>
          <div class="comment-header">
            <span class="title">互动评价区</span>
            <el-radio-group v-model="sortType" size="small" @change="fetchComments">
              <el-radio-button value="time">按时间</el-radio-button>
              <el-radio-button value="heat">按热度</el-radio-button>
            </el-radio-group>
          </div>
        </template>

        <div class="comment-input-box" v-if="userRole !== 'admin'">
          <div v-if="userRole === 'retail' || userRole === 'admin'" class="rating-box">
            <span class="label">商品打分:</span>
            <el-rate v-model="newRating" :disabled="hasRated" :texts="['极差', '失望', '一般', '满意', '惊喜']" show-text />
            <span v-if="hasRated" class="rated-tip">(您已为该商品打过分，再次评论将作为追评)</span>
          </div>

          <div v-if="canComment">
            <el-input
              v-model="newCommentText"
              type="textarea"
              :rows="3"
              :placeholder="userRole === 'supplier' ? '作为商家，请回复买家的关切...' : '写下您的真实体验...'"
            />
            <div style="margin-top: 10px; text-align: right;">
              <el-button type="primary" @click="submitComment">发布评论</el-button>
            </div>
          </div>
        </div>

        <el-divider />

        <div v-if="comments.length > 0" class="comment-list">
          <div v-for="c in comments" :key="c.id" class="comment-item">
            <div class="c-avatar">{{ c.username ? c.username.charAt(0).toUpperCase() : 'U' }}</div>
            <div class="c-body">

              <div class="c-meta">
                <span class="c-name">{{ c.username }}</span>
                <el-tag v-if="c.is_seller_reply" type="danger" effect="dark" size="small" round style="margin-left:8px;">商家直复</el-tag>
                <el-rate v-if="c.rating" v-model="c.rating" disabled size="small" style="margin-left: 15px;" />
                <span class="c-time">{{ formatTime(c.created_at) }}</span>
              </div>
              <div class="c-content">{{ c.content }}</div>

              <div class="c-actions">
                <div class="vote-btns" v-if="userRole !== 'admin'">
                  <span class="action-btn" :class="{ active: c.current_user_vote === 'like' }" @click="handleVote(c, 'like')">
                    👍 {{ c.likes_count }}
                  </span>
                  <span class="action-btn" :class="{ active: c.current_user_vote === 'dislike' }" @click="handleVote(c, 'dislike')">
                    👎 {{ c.dislikes_count }}
                  </span>
                  <span class="action-btn reply-btn" v-if="canComment" @click="replyingToId = c.id">
                    💬 回复
                  </span>
                </div>

                <el-popconfirm v-if="userRole === 'admin'" title="确定要强制删除这条违规评论吗？" @confirm="deleteComment(c.id)">
                  <template #reference>
                    <el-button type="danger" link size="small">删除</el-button>
                  </template>
                </el-popconfirm>
              </div>

              <div v-if="replyingToId === c.id" class="inline-reply-box mt-20">
                <el-input v-model="inlineReplyText" placeholder="写下你的回复..." size="small" @keyup.enter="submitInlineReply(c)">
                  <template #append>
                    <el-button type="primary" @click="submitInlineReply(c)">发送</el-button>
                  </template>
                </el-input>
                <div class="inline-reply-footer">
                   <el-button link size="small" @click="replyingToId = null">取消回复</el-button>
                </div>
              </div>

              <div class="replies-container" v-if="c.replies && c.replies.length > 0">
                <div v-for="reply in c.replies" :key="reply.id" class="reply-item">
                  <div class="reply-meta">
                    <span class="c-name">{{ reply.username }}</span>
                    <el-tag v-if="reply.is_seller_reply" type="danger" size="small" style="margin-left:5px;">商家</el-tag>
                    <span class="reply-text">：{{ reply.content }}</span>
                  </div>
                  <div class="reply-actions">
                    <span class="c-time">{{ formatTime(reply.created_at) }}</span>
                    <div class="vote-btns small" v-if="userRole !== 'admin'">
                       <span class="action-btn" :class="{ active: reply.current_user_vote === 'like' }" @click="handleVote(reply, 'like')">👍 {{ reply.likes_count }}</span>
                       <span class="action-btn" :class="{ active: reply.current_user_vote === 'dislike' }" @click="handleVote(reply, 'dislike')">
                    👎 {{ reply.dislikes_count }}
                  </span>
                    </div>

                    <el-popconfirm v-if="userRole === 'admin'" title="确定删除子回复吗？" @confirm="deleteComment(reply.id)">
                      <template #reference>
                        <el-button type="danger" link size="small">删除</el-button>
                      </template>
                    </el-popconfirm>
                  </div>
                </div>
              </div>

            </div>
          </div>
        </div>
        <el-empty v-else description="暂无评价，来抢沙发吧！" />
      </el-card>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onBeforeUnmount } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Location, Monitor } from '@element-plus/icons-vue'
import request from '@/utils/request'
import dayjs from 'dayjs'

const route = useRoute()
const router = useRouter()
const productId = route.params.id

// 基础商品状态
const product = ref({})
const loading = ref(false)

// 身份与评论相关状态
const userRole = ref(localStorage.getItem('user_role') || 'retail')
// 从 localStorage 读取 user_id，如果没有则从 /user/profile/ 接口获取（备选）
// 但最简单是在登录时存储 user_id。先尝试从 localStorage 读取，若为空则通过接口获取
const currentUserId = ref(null)
const fetchCurrentUser = async () => {
  const storedId = localStorage.getItem('user_id')
  if (storedId) {
    currentUserId.value = Number(storedId)
  } else {
    try {
      const res = await request.get('/user/profile/')
      currentUserId.value = res.data.id
      localStorage.setItem('user_id', res.data.id)
    } catch (e) { console.error('获取用户ID失败', e) }
  }
}
// 在 onMounted 中调用 fetchCurrentUser()
const currentUsername = ref(localStorage.getItem('username'))

const comments = ref([])
const sortType = ref('time')
const newRating = ref(5)
const newCommentText = ref('')
let pollingTimer = null

// 楼中楼专属状态
const replyingToId = ref(null)
const inlineReplyText = ref('')

const categoryMap = {
  fruits_vegs: '生鲜果蔬',
  grains: '米面粮油',
  meat: '肉禽蛋奶',
  dry: '干货菌菇'
}

// 格式化时间
const formatTime = (t) => dayjs(t).format('YYYY-MM-DD HH:mm')

// --- 权限计算属性 ---
// 是否已打过分 (仅判断顶级评论中有无自己打分的记录)
const hasRated = computed(() => {
  return comments.value.some(c =>
    c.rating !== null &&
    !c.is_seller_reply &&
    c.username === currentUsername.value
  )
})

// 权限判断逻辑
const canComment = computed(() => {
  if (userRole.value === 'admin') return false;
  if (userRole.value === 'supplier') {
    if (!product.value) return false;
    // product.value.owner 可能是数字（外键）或对象，统一转数字比较
    const ownerId = typeof product.value.owner === 'object' ? product.value.owner.id : product.value.owner;
    return ownerId === currentUserId.value;
  }
  return true;
})

// --- 业务逻辑 ---

// 1. 获取商品详情
const fetchProductDetail = async () => {
  loading.value = true
  try {
    const res = await request.get(`/products/${productId}/`)
    product.value = res.data
  } catch (error) {
    ElMessage.error('获取商品详情失败')
  } finally {
    loading.value = false
  }
}

// 2. 购买拦截逻辑
// 完全不跳转的纯原地闭环订购逻辑
const handleBuy = async () => {
  const token = localStorage.getItem('access_token')
  if (!token) {
    ElMessage.warning('请先登录后再进行操作')
    router.push('/login')
    return
  }

  try {
    const statusRes = await request.get('/realname/status/')
    const authStatus = statusRes.data.status

    if (userRole.value !== 'admin' && authStatus !== 'approved') {
      ElMessageBox.confirm(
        '根据系统合规要求，您需要完成“实名认证”并通过审核后才能下单。是否现在前往认证？',
        '实名认证提醒',
        { confirmButtonText: '立即前往', cancelButtonText: '再看看', type: 'warning' }
      ).then(() => {
        router.push('/realname-auth')
      }).catch(() => {})
      return
    }
  } catch (err) {
    console.error('获取实名状态失败', err)
  }

  try {
    // 1. 发送请求给后端创建订单
    // 这里的参数严格对齐你后端 OrderCreateView 的接收要求（使用 product 字段名）
    await request.post('/orders/create/', {
      product: product.value.id,
      total_amount: product.value.retail_price,
      quantity: 1 // 默认在详情页快捷订购 1 斤
    })

    // 2. 核心改动：完全不调用任何 router.push 跳转
    // 弹出 Element Plus 顶端通知，提示用户去对应的“我的订单”中查看即可
    ElMessage({
      message: `已为您成功预订 1 斤 ${product.value.name}！数据已同步存证，请前往“我的订单”查看。`,
      type: 'success',
      duration: 5000 // 提示多停留一会儿，方便答辩展示
    })

    // 3. 原地异步刷新商品详情，使页面上的库存数字立刻跟着减少，视觉反馈完美无瑕
    fetchProductDetail()

  } catch (error) {
    // 捕获可能存在的库存不足等业务异常
    ElMessage.error(error.response?.data?.error || '下单失败')
  }
}

// 3. 获取评论列表 (自动包含子评论)
const fetchComments = async () => {
  try {
    const res = await request.get(`/products/${productId}/comments/?sort=${sortType.value}`)
    comments.value = res.data
  } catch (e) {
    console.error('获取评论失败', e)
  }
}

// 4. 提交主评价
const submitComment = async () => {
  if (!newCommentText.value.trim()) return ElMessage.warning('内容不能为空')
  try {
    const payload = { content: newCommentText.value }
    if (!hasRated.value && userRole.value !== 'supplier') {
      payload.rating = newRating.value
    }

    await request.post(`/products/${productId}/comments/`, payload)
    ElMessage.success('发布成功')
    newCommentText.value = ''
    fetchComments()
  } catch (e) {
    ElMessage.error(e.response?.data?.detail || '发布失败')
  }
}

// 5. 提交楼中楼回复
const submitInlineReply = async (parentComment) => {
  if (!inlineReplyText.value.trim()) return ElMessage.warning('回复内容不能为空')
  try {
    await request.post(`/products/${productId}/comments/`, {
      content: inlineReplyText.value,
      parent_id: parentComment.id // 注入父级ID
    })
    ElMessage.success('回复成功')
    inlineReplyText.value = ''
    replyingToId.value = null // 收起输入框
    fetchComments() // 刷新列表展示最新回复
  } catch (e) {
    ElMessage.error(e.response?.data?.detail || '回复失败')
  }
}

// 6. 赞与踩防抖处理
const handleVote = async (comment, action) => {
  // 前端防越权阻断
  if (userRole.value === 'admin') {
    return ElMessage.warning('管理员仅拥有合规审计权限，不可参与主观互动')
  }

  const previousVote = comment.current_user_vote
  if (action === 'like') {
    if (previousVote === 'like') { comment.likes_count--; comment.current_user_vote = null }
    else {
      comment.likes_count++; comment.current_user_vote = 'like'
      if (previousVote === 'dislike') comment.dislikes_count--
    }
  } else {
    if (previousVote === 'dislike') { comment.dislikes_count--; comment.current_user_vote = null }
    else {
      comment.dislikes_count++; comment.current_user_vote = 'dislike'
      if (previousVote === 'like') comment.likes_count--
    }
  }

  try {
    await request.post(`/comments/${comment.id}/vote/`, { action })
  } catch (e) {
    ElMessage.error('操作失败，网络可能波动')
    fetchComments()
  }
}

// 7. 管理员删除评论
const deleteComment = async (id) => {
  try {
    await request.delete(`/comments/${id}/delete/`)
    ElMessage.success('违规记录已强制清除')
    fetchComments()
  } catch (e) {
    if (e !== 'cancel') ElMessage.error('删除失败')
  }
}

// --- 生命周期钩子 ---
onMounted(() => {
  fetchCurrentUser()         // 先获取当前用户ID
  fetchProductDetail()       // 然后加载商品详情
  fetchComments()            // 加载评论
  pollingTimer = setInterval(fetchComments, 10000)
})

onBeforeUnmount(() => {
  if (pollingTimer) clearInterval(pollingTimer)
})
</script>

<style scoped>
.product-detail-container { padding: 40px; max-width: 1200px; margin: 0 auto; }
.image-card { position: relative; border-radius: 12px; overflow: hidden; border: none; box-shadow: 0 10px 30px rgba(0,0,0,0.1); }
.main-image { width: 100%; height: 450px; display: block; }
.image-placeholder { height: 450px; display: flex; justify-content: center; align-items: center; background: #f5f7fa; color: #909399; }
.rs-overlay {
  position: absolute; bottom: 0; left: 0; right: 0;
  background: rgba(0, 20, 40, 0.7); backdrop-filter: blur(5px);
  padding: 15px; display: flex; justify-content: space-around; color: #64ffda;
}
.rs-item { text-align: center; }
.rs-item .label { display: block; font-size: 12px; opacity: 0.8; }
.rs-item .value { font-size: 20px; font-weight: bold; font-family: monospace; }

.info-section { padding: 10px 0; }
.product-name { font-size: 32px; color: #303133; margin-bottom: 10px; }
.origin-tag { color: #909399; margin-bottom: 20px; display: flex; align-items: center; gap: 5px; }
.price-box { background: #fdf6ec; padding: 20px; border-radius: 8px; margin-bottom: 30px; }
.currency { font-size: 20px; color: #f56c6c; }
.amount { font-size: 36px; color: #f56c6c; font-weight: bold; margin-right: 15px; }

.expert-section { margin-top: 30px; padding: 20px; background: #f0f9eb; border-left: 4px solid #67c23a; border-radius: 4px; }
.section-title { margin-top: 0; color: #67c23a; font-size: 16px; display: flex; align-items: center; gap: 8px; }
.analysis-text { color: #606266; line-height: 1.6; font-size: 14px; margin-bottom: 0; }

.action-bar { margin-top: 40px; }
.buy-btn { width: 240px; height: 54px; font-size: 18px; font-weight: bold; letter-spacing: 2px; }

/* 评论区核心样式 */
.mt-20 { margin-top: 20px; }
.comments-section { width: 100%; margin-top: 40px; }
.comment-header { display: flex; justify-content: space-between; align-items: center; }
.comment-header .title { font-size: 18px; font-weight: bold; color: #303133; border-left: 4px solid #409EFF; padding-left: 10px; }

.comment-input-box { padding: 20px; background: #f8f9fa; border-radius: 8px; margin-bottom: 20px; border: 1px solid #ebeef5; }
.rating-box { margin-bottom: 15px; display: flex; align-items: center; gap: 10px; }
.rated-tip { font-size: 12px; color: #F56C6C; margin-left: 10px; }

.comment-list { display: flex; flex-direction: column; gap: 20px; }
.comment-item { display: flex; gap: 15px; }
.c-avatar {
  width: 44px; height: 44px; background: linear-gradient(135deg, #409EFF, #64ffda);
  color: #fff; border-radius: 50%; display: flex; align-items: center; justify-content: center;
  font-weight: bold; font-size: 18px; flex-shrink: 0; box-shadow: 0 2px 8px rgba(64,158,255,0.3);
}
.c-body { flex: 1; border-bottom: 1px solid #ebeef5; padding-bottom: 15px; }
.c-meta { display: flex; align-items: center; margin-bottom: 10px; }
.c-name { font-weight: bold; color: #303133; font-size: 15px; }
.c-time { margin-left: auto; font-size: 12px; color: #909399; }
.c-content { font-size: 14px; color: #606266; line-height: 1.6; margin-bottom: 12px; }

.c-actions { display: flex; justify-content: space-between; align-items: center; }
.vote-btns { display: flex; gap: 20px; }
.action-btn {
  cursor: pointer; color: #909399; font-size: 13px; transition: 0.3s;
  user-select: none; display: flex; align-items: center; gap: 4px;
}
.action-btn:hover { color: #409EFF; }
.action-btn.active { color: #409EFF; font-weight: bold; transform: scale(1.1); }

/* 🚀 楼中楼新增的专属样式 */
.reply-btn { margin-left: 10px; font-weight: bold; }
.inline-reply-box {
  margin-top: 15px; background: #fdfdfd; padding: 12px;
  border-radius: 6px; box-shadow: inset 0 1px 4px rgba(0,0,0,0.05); border: 1px solid #ebeef5;
}
.inline-reply-footer { text-align: right; margin-top: 8px; }
.replies-container {
  background-color: #f4f4f5; padding: 15px; border-radius: 6px;
  margin-top: 15px; border-left: 3px solid #dcdfe6;
}
.reply-item { padding: 10px 0; border-bottom: 1px dashed #e4e7ed; font-size: 13px; }
.reply-item:last-child { border-bottom: none; padding-bottom: 0; }
.reply-meta { line-height: 1.5; color: #606266; margin-bottom: 6px; }
.reply-text { color: #303133; }
.reply-actions { display: flex; justify-content: space-between; align-items: center; margin-top: 5px; width: 100%;}
.reply-actions .c-time {flex-shrink: 0; margin-right: 10px;}
.reply-actions .vote-btns {flex-shrink: 0;}
.vote-btns.small .action-btn { font-size: 12px; }
</style>
