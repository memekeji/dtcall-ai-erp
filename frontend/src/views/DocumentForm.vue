<template>
  <div class="document-form-container">
    <el-card>
      <template #header>
        <div class="card-header">
          <h2>{{ isEdit ? '编辑文档' : '上传文档' }}</h2>
        </div>
      </template>
      
      <el-form
        ref="documentFormRef"
        :model="documentForm"
        :rules="rules"
        label-width="120px"
        class="document-form"
        enctype="multipart/form-data"
      >
        <el-row :gutter="20">
          <el-col :span="12">
            <el-form-item label="文档标题" prop="title">
              <el-input
                v-model="documentForm.title"
                placeholder="请输入文档标题"
                clearable
              />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="所属项目" prop="project_id">
              <el-select v-model="documentForm.project_id" placeholder="请选择所属项目">
                <!-- 这里需要动态加载项目列表 -->
                <el-option label="测试项目" :value="1" />
              </el-select>
            </el-form-item>
          </el-col>
        </el-row>
        
        <el-form-item label="文档内容" prop="content">
          <el-input
            v-model="documentForm.content"
            type="textarea"
            placeholder="请输入文档内容"
            :rows="4"
          />
        </el-form-item>
        
        <el-form-item label="上传文件" prop="file">
          <el-upload
            v-model:file-list="fileList"
            :auto-upload="false"
            :limit="1"
            :on-exceed="handleExceed"
            :on-change="handleFileChange"
            accept=".doc,.docx,.pdf,.txt,.xls,.xlsx,.ppt,.pptx"
          >
            <el-button type="primary">
              <el-icon-upload></el-icon-upload> 选择文件
            </el-button>
            <template #tip>
              <div class="el-upload__tip">
                支持上传.doc,.docx,.pdf,.txt,.xls,.xlsx,.ppt,.pptx文件
              </div>
            </template>
          </el-upload>
        </el-form-item>
        
        <el-form-item>
          <div class="form-actions">
            <el-button type="primary" @click="handleSubmit">
              <el-icon-check></el-icon-check> 提交
            </el-button>
            <el-button @click="handleCancel">
              <el-icon-close></el-icon-close> 取消
            </el-button>
          </div>
        </el-form-item>
      </el-form>
    </el-card>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted, computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import request from '../utils/request'

const route = useRoute()
const router = useRouter()
const documentFormRef = ref(null)
const fileList = ref([])

// 判断是否是编辑模式
const isEdit = computed(() => !!route.params.id)

// 文档表单数据
const documentForm = reactive({
  title: '',
  content: '',
  project_id: '',
  file_path: ''
})

// 表单验证规则
const rules = {
  title: [
    { required: true, message: '请输入文档标题', trigger: 'blur' },
    { min: 2, max: 255, message: '文档标题长度应在 2 到 255 个字符之间', trigger: 'blur' }
  ],
  project_id: [
    { required: true, message: '请选择所属项目', trigger: 'change' }
  ],
  file: [
    { required: !isEdit.value, message: '请上传文件', trigger: 'change' }
  ]
}

// 获取文档详情
const getDocumentDetail = async () => {
  try {
    const response = await request.get(`/project/project-documents/${route.params.id}/`)
    // 填充表单数据
    Object.assign(documentForm, response)
    // 处理文件列表
    if (response.file_path) {
      fileList.value = [{
        name: response.title,
        url: response.file_path
      }]
    }
  } catch (error) {
    ElMessage.error('获取文档详情失败：' + error.message)
  }
}

// 提交表单
const handleSubmit = async () => {
  if (!await documentFormRef.value.validate()) {
    return
  }
  
  try {
    const formData = new FormData()
    formData.append('title', documentForm.title)
    formData.append('content', documentForm.content)
    formData.append('project_id', documentForm.project_id)
    
    // 处理文件上传
    if (fileList.value.length > 0 && fileList.value[0].raw) {
      formData.append('file', fileList.value[0].raw)
    }
    
    let response
    if (isEdit.value) {
      // 更新文档
      response = await request.put(`/project/project-documents/${route.params.id}/`, formData, {
        headers: {
          'Content-Type': 'multipart/form-data'
        }
      })
      ElMessage.success('文档更新成功')
    } else {
      // 创建文档
      response = await request.post('/project/project-documents/', formData, {
        headers: {
          'Content-Type': 'multipart/form-data'
        }
      })
      ElMessage.success('文档上传成功')
    }
    // 跳转到文档列表页
    router.push('/documents')
  } catch (error) {
    ElMessage.error(isEdit.value ? '文档更新失败：' + error.message : '文档上传失败：' + error.message)
  }
}

// 取消操作
const handleCancel = () => {
  router.back()
}

// 文件超出数量限制
const handleExceed = (files, fileList) => {
  ElMessage.warning('最多只能上传一个文件')
}

// 文件选择变化
const handleFileChange = (file, fileList) => {
  // 处理文件选择变化
  console.log('File change:', file, fileList)
}

// 初始化
onMounted(() => {
  if (isEdit.value) {
    getDocumentDetail()
  }
})
</script>

<style scoped>
.document-form-container {
  padding: 20px;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.document-form {
  margin-top: 20px;
}

.form-actions {
  display: flex;
  gap: 10px;
}
</style>
