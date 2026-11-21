<template>
    <div class="audit-container">
      <el-card class="audit-card" shadow="never">
        <template #header>
          <div class="card-header">
            <span class="title"> YOLOv5 坏果实时识别中心</span>
            <el-tag type="danger">GPU 加速中</el-tag>
          </div>
        </template>

        <el-upload
          class="audit-uploader"
          drag
          action="http://127.0.0.1:8000/api/quality/inspect/"
          :headers="authHeaders"
          name="image"
          :on-success="handleAuditSuccess"
          :before-upload="beforeAuditUpload"
        >
          <el-icon class="el-icon--upload"><upload-filled /></el-icon>
          <div class="el-upload__text">
            将农产品实拍图拖到此处，或 <em>点击上传</em>
            <div class="el-upload__tip">支持 JPG/PNG 文件，图像将直接送往 GPU 进行 YOLOv5 坏果分析</div>
          </div>
        </el-upload>

        <transition name="el-zoom-in-top">
          <div v-if="auditResult" class="result-section">
            <el-divider content-position="left">AI 实时审计报告</el-divider>
            <el-row :gutter="40">
              <el-col :span="12">
                <div class="image-preview">
                  <p class="label">AI 视觉标注结果：</p>
                  <el-image
                    :src="auditResult.image_url"
                    fit="contain"
                    :preview-src-list="[auditResult.image_url]"
                  >
                    <template #placeholder><div class="loading">图像处理中...</div></template>
                  </el-image>
                </div>
              </el-col>
              <el-col :span="12">
                <div class="data-preview">
                  <el-statistic title="检出坏果数量" :value="auditResult.bad_count" />
                  <el-alert
                    class="mt-20"
                    title="质检日志已发布"
                    description="本次检测结果已实时同步至全网公示流，所有采购商现已可见。"
                    type="success"
                    show-icon
                    :closable="false"
                  />
                  <div class="hint-box mt-20">
                    <h4>💡 系统对策建议：</h4>
                    <p>{{ auditResult.bad_count > 0 ? '检测到瑕疵，建议联系供应商进行批次抽检或下架处理。' : '品质极佳，建议标记为“优选等级”提升竞争力。' }}</p>
                  </div>
                </div>
              </el-col>
            </el-row>
          </div>
        </transition>
      </el-card>
    </div>
  </template>

  <script setup>
  import { ref } from 'vue'
  import { UploadFilled } from '@element-plus/icons-vue'
  import { ElMessage } from 'element-plus'

  const auditResult = ref(null)
  const token = localStorage.getItem('access_token')
  const authHeaders = { Authorization: `Bearer ${token}` }

  // 上传前校验
  const beforeAuditUpload = (file) => {
    const isImg = file.type === 'image/jpeg' || file.type === 'image/png'
    if (!isImg) {
      ElMessage.error('只能上传 JPG 或 PNG 图片!')
    }
    return isImg
  }

  // 上传成功回调
  const handleAuditSuccess = (res) => {
    auditResult.value = res
    ElMessage.success('YOLOv5 推理完成，质检日志已入库')
  }
  </script>

  <style scoped>
  .audit-container { padding: 20px; background: #f5f7fa; min-height: calc(100vh - 100px); }
  .audit-card { border-radius: 12px; }
  .card-header { display: flex; justify-content: space-between; align-items: center; }
  .title { font-size: 18px; font-weight: bold; color: #303133; }
  .result-section { margin-top: 30px; }
  .image-preview .label { margin-bottom: 15px; font-size: 14px; color: #606266; }
  .image-preview .el-image { border-radius: 8px; border: 1px solid #dcdfe6; width: 100%; height: 400px; background: #000; }
  .mt-20 { margin-top: 20px; }
  .hint-box { padding: 15px; background: #f0f9eb; border-radius: 8px; color: #67c23a; }
  .hint-box h4 { margin-bottom: 8px; }
  .hint-box p { font-size: 13px; line-height: 1.5; }
  </style>
