<template>
  <div class="publish-page">
    <el-card class="publish-card">
      <template #header>
        <div class="card-header">
          <span>发布商品</span>
        </div>
      </template>

      <div class="publish-content">
        <div class="form-area">
          <el-form
            ref="formRef"
            :model="form"
            :rules="rules"
            label-width="100px"
            class="publish-form"
          >
            <el-form-item label="商品名称" prop="name">
              <el-input v-model="form.name" placeholder="请输入商品名称" />
            </el-form-item>

            <el-form-item label="商品分类" prop="category">
              <el-select v-model="form.category" placeholder="请选择商品分类" style="width: 100%">
                <el-option label="生鲜果蔬" value="fruits_vegs" />
                <el-option label="米面粮油" value="grains" />
                <el-option label="肉禽蛋奶" value="meat" />
                <el-option label="干货菌菇" value="dry" />
              </el-select>
            </el-form-item>

            <el-form-item label="商品产地" prop="origin">
              <el-input
                v-model="form.origin"
                placeholder="请输入商品产地，如：陕西省延安市洛川县"
              />
            </el-form-item>

            <el-form-item label="零售价" prop="retail_price">
              <el-input-number
                v-model="form.retail_price"
                :min="0.1"
                :step="0.1"
                :precision="2"
                style="width: 100%"
              />
            </el-form-item>

            <el-form-item label="库存" prop="stock">
              <el-input-number
                v-model="form.stock"
                :min="1"
                :step="1"
                style="width: 100%"
              />
            </el-form-item>

            <!-- 图片上传区域：支持本地上传或 URL 输入 -->
            <el-form-item label="商品图片">
              <div class="image-upload-wrapper">
                <el-upload
                  class="avatar-uploader"
                  :auto-upload="false"
                  :show-file-list="false"
                  :on-change="handleFileChange"
                  accept="image/jpeg,image/png,image/jpg"
                >
                  <img v-if="imagePreviewUrl" :src="imagePreviewUrl" class="avatar" />
                  <el-icon v-else class="avatar-uploader-icon"><Plus /></el-icon>
                </el-upload>
                <div class="image-tip">点击选择图片（支持 jpg/png，小于 2MB）</div>
                <el-input
                  v-model="form.image_url"
                  placeholder="或输入图片URL"
                  style="margin-top: 10px"
                />
              </div>
            </el-form-item>

            <el-form-item>
              <el-button type="primary" :loading="submitting" @click="handleSubmit">
                发布商品
              </el-button>
              <el-button @click="handleReset">重置</el-button>
              <el-button type="success" plain @click="goMyProducts">
                我的商品
              </el-button>
            </el-form-item>
          </el-form>
        </div>

        <div class="preview-area">
          <div class="preview-title">示例图片</div>
          <el-image
            class="example-image"
            :src="exampleImage"
            fit="cover"
            :preview-src-list="[exampleImage]"
            preview-teleported
          />
          <div class="preview-tip">
            可参考该示例图片风格；点击图片可放大预览。
          </div>
        </div>
      </div>
    </el-card>
  </div>
</template>

<script setup>
import { reactive, ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { Plus } from '@element-plus/icons-vue'
import request from '@/utils/request'

const router = useRouter()
const formRef = ref(null)
const submitting = ref(false)

// 示例图片
const exampleImage =
  'https://images.unsplash.com/photo-1567306226416-28f0efdc88ce?auto=format&fit=crop&w=800&q=80'

// 表单数据
const form = reactive({
  name: '',
  category: '',
  origin: '',
  retail_price: 1,
  stock: 100,
  image_url: ''
})

// 本地图片文件与预览
const imageFile = ref(null)
const imagePreviewUrl = ref('')

// 表单验证规则
const rules = {
  name: [{ required: true, message: '请输入商品名称', trigger: 'blur' }],
  category: [{ required: true, message: '请选择商品分类', trigger: 'change' }],
  origin: [{ required: true, message: '请输入商品产地', trigger: 'blur' }],
  retail_price: [{ required: true, message: '请输入商品价格', trigger: 'change' }],
  stock: [{ required: true, message: '请输入库存', trigger: 'change' }]
}

// 权限检查
const checkRole = () => {
  const role = localStorage.getItem('user_role')
  if (role !== 'supplier') {
    ElMessage.error('只有供应商可以发布商品')
    router.replace('/products')
  }
}

// 重置表单
const handleReset = () => {
  form.name = ''
  form.category = ''
  form.origin = ''
  form.retail_price = 1
  form.stock = 100
  form.image_url = ''
  imageFile.value = null
  imagePreviewUrl.value = ''
  formRef.value?.clearValidate()
}

const goMyProducts = () => {
  router.push('/my-products')
}

// 处理本地图片选择
const handleFileChange = (file) => {
  const isImage = file.raw.type === 'image/jpeg' || file.raw.type === 'image/png'
  const isLt2M = file.raw.size / 1024 / 1024 < 2
  if (!isImage) {
    ElMessage.error('只能上传 JPG/PNG 格式图片!')
    return false
  }
  if (!isLt2M) {
    ElMessage.error('图片大小不能超过 2MB!')
    return false
  }
  imageFile.value = file.raw
  // 生成本地预览
  if (imagePreviewUrl.value) {
    URL.revokeObjectURL(imagePreviewUrl.value)
  }
  imagePreviewUrl.value = URL.createObjectURL(file.raw)
}

// 提交商品
const handleSubmit = async () => {
  if (!formRef.value) return
  formRef.value.validate(async (valid) => {
    if (!valid) return
    submitting.value = true
    try {
      const payload = new FormData()
      payload.append('name', form.name)
      payload.append('category', form.category)
      payload.append('origin', form.origin)
      payload.append('retail_price', form.retail_price)
      payload.append('stock', form.stock)
      payload.append('image_url', form.image_url)
      if (imageFile.value) {
        payload.append('image_file', imageFile.value)
      }

      await request.post('/products/create/', payload, {
        headers: { 'Content-Type': 'multipart/form-data' },
        timeout: 20000
      })

      ElMessage.success('商品发布成功')
      router.push('/my-products')
    } catch (error) {
      if (error?.code === 'ECONNABORTED') {
        ElMessage.warning('发布请求超时，商品可能已创建，请到“我的商品”页刷新确认')
        return
      }
      ElMessage.error(
        error?.response?.data?.detail ||
        error?.response?.data?.error ||
        '商品发布失败'
      )
    } finally {
      submitting.value = false
    }
  })
}

onMounted(() => {
  checkRole()
})
</script>

<style scoped>
.publish-page {
  padding: 20px;
}

.publish-card {
  max-width: 1100px;
  margin: 0 auto;
  border-radius: 18px;
}

.card-header {
  font-size: 20px;
  font-weight: 600;
}

.publish-content {
  display: flex;
  gap: 32px;
  align-items: flex-start;
  flex-wrap: wrap;
}

.form-area {
  flex: 1;
  min-width: 420px;
}

.preview-area {
  width: 260px;
  display: flex;
  flex-direction: column;
  gap: 12px;
  padding-top: 10px;
}

.preview-title {
  font-size: 16px;
  font-weight: 600;
  color: #303133;
}

.example-image {
  width: 100%;
  height: 260px;
  border-radius: 14px;
  overflow: hidden;
  border: 1px solid #ebeef5;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.06);
}

.preview-tip {
  font-size: 13px;
  line-height: 1.6;
  color: #909399;
}

.publish-form {
  margin-top: 10px;
}

/* 图片上传样式 */
.image-upload-wrapper {
  width: 100%;
}

.avatar-uploader .avatar {
  width: 178px;
  height: 178px;
  display: block;
  object-fit: cover;
}

.avatar-uploader :deep(.el-upload) {
  border: 1px dashed #d9d9d9;
  border-radius: 6px;
  cursor: pointer;
  position: relative;
  overflow: hidden;
  transition: var(--el-transition-duration-fast);
}

.avatar-uploader :deep(.el-upload:hover) {
  border-color: var(--el-color-primary);
}

.avatar-uploader-icon {
  font-size: 28px;
  color: #8c939d;
  width: 178px;
  height: 178px;
  text-align: center;
  line-height: 178px;
}

.image-tip {
  font-size: 12px;
  color: #909399;
  margin-top: 8px;
}

@media (max-width: 900px) {
  .publish-content {
    flex-direction: column;
  }

  .preview-area {
    width: 100%;
  }

  .example-image {
    height: 220px;
  }
}
</style>
