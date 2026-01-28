<template>
  <div class="project-form-container">
    <el-card>
      <template #header>
        <div class="card-header">
          <h2>{{ isEdit ? '编辑项目' : '新建项目' }}</h2>
        </div>
      </template>
      
      <el-form
        ref="projectFormRef"
        :model="projectForm"
        :rules="rules"
        label-width="120px"
        class="project-form"
      >
        <el-row :gutter="20">
          <el-col :span="12">
            <el-form-item label="项目名称" prop="name">
              <el-input
                v-model="projectForm.name"
                placeholder="请输入项目名称"
                clearable
              />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="项目编号" prop="code">
              <el-input
                v-model="projectForm.code"
                placeholder="请输入项目编号"
                clearable
                :disabled="isEdit"
              />
            </el-form-item>
          </el-col>
        </el-row>
        
        <el-row :gutter="20">
          <el-col :span="12">
            <el-form-item label="项目状态" prop="status">
              <el-select v-model="projectForm.status" placeholder="请选择项目状态">
                <el-option label="未开始" :value="1" />
                <el-option label="进行中" :value="2" />
                <el-option label="已完成" :value="3" />
                <el-option label="已关闭" :value="4" />
                <el-option label="已暂停" :value="5" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="优先级" prop="priority">
              <el-select v-model="projectForm.priority" placeholder="请选择优先级">
                <el-option label="低" :value="1" />
                <el-option label="中" :value="2" />
                <el-option label="高" :value="3" />
                <el-option label="紧急" :value="4" />
              </el-select>
            </el-form-item>
          </el-col>
        </el-row>
        
        <el-row :gutter="20">
          <el-col :span="12">
            <el-form-item label="项目经理" prop="manager_id">
              <el-select v-model="projectForm.manager_id" placeholder="请选择项目经理">
                <!-- 这里需要动态加载用户列表 -->
                <el-option label="管理员" :value="1" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="关联客户" prop="customer_id">
              <el-select v-model="projectForm.customer_id" placeholder="请选择关联客户">
                <!-- 这里需要动态加载客户列表 -->
                <el-option label="测试客户" :value="1" />
              </el-select>
            </el-form-item>
          </el-col>
        </el-row>
        
        <el-row :gutter="20">
          <el-col :span="12">
            <el-form-item label="开始日期" prop="start_date">
              <el-date-picker
                v-model="projectForm.start_date"
                type="date"
                placeholder="请选择开始日期"
                style="width: 100%"
              />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="结束日期" prop="end_date">
              <el-date-picker
                v-model="projectForm.end_date"
                type="date"
                placeholder="请选择结束日期"
                style="width: 100%"
              />
            </el-form-item>
          </el-col>
        </el-row>
        
        <el-row :gutter="20">
          <el-col :span="12">
            <el-form-item label="项目预算" prop="budget">
              <el-input-number
                v-model="projectForm.budget"
                placeholder="请输入项目预算"
                :min="0"
                :step="0.01"
                :precision="2"
              />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="完成进度" prop="progress">
              <el-input-number
                v-model="projectForm.progress"
                placeholder="请输入完成进度"
                :min="0"
                :max="100"
                :step="1"
              />
            </el-form-item>
          </el-col>
        </el-row>
        
        <el-form-item label="项目描述" prop="description">
          <el-input
            v-model="projectForm.description"
            type="textarea"
            placeholder="请输入项目描述"
            :rows="4"
          />
        </el-form-item>
        
        <el-form-item label="项目成员">
          <el-select
            v-model="projectForm.members_ids"
            placeholder="请选择项目成员"
            multiple
            collapse-tags
          >
            <!-- 这里需要动态加载用户列表 -->
            <el-option label="管理员" :value="1" />
          </el-select>
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
const projectFormRef = ref(null)

// 判断是否是编辑模式
const isEdit = computed(() => !!route.params.id)

// 项目表单数据
const projectForm = reactive({
  name: '',
  code: '',
  status: 1,
  priority: 2,
  manager_id: '',
  customer_id: '',
  start_date: '',
  end_date: '',
  budget: 0,
  progress: 0,
  description: '',
  members_ids: []
})

// 表单验证规则
const rules = {
  name: [
    { required: true, message: '请输入项目名称', trigger: 'blur' },
    { min: 2, max: 255, message: '项目名称长度应在 2 到 255 个字符之间', trigger: 'blur' }
  ],
  code: [
    { required: true, message: '请输入项目编号', trigger: 'blur' },
    { min: 2, max: 100, message: '项目编号长度应在 2 到 100 个字符之间', trigger: 'blur' }
  ],
  status: [
    { required: true, message: '请选择项目状态', trigger: 'change' }
  ],
  priority: [
    { required: true, message: '请选择优先级', trigger: 'change' }
  ],
  manager_id: [
    { required: true, message: '请选择项目经理', trigger: 'change' }
  ],
  start_date: [
    { required: true, message: '请选择开始日期', trigger: 'change' }
  ],
  end_date: [
    { required: true, message: '请选择结束日期', trigger: 'change' }
  ]
}

// 获取项目详情
const getProjectDetail = async () => {
  try {
    const response = await request.get(`/project/projects/${route.params.id}/`)
    // 填充表单数据
    Object.assign(projectForm, response)
    // 处理关联数据
    projectForm.manager_id = response.manager.id
    projectForm.customer_id = response.customer ? response.customer.id : ''
    projectForm.members_ids = response.members.map(member => member.id)
  } catch (error) {
    ElMessage.error('获取项目详情失败：' + error.message)
  }
}

// 提交表单
const handleSubmit = async () => {
  if (!await projectFormRef.value.validate()) {
    return
  }
  
  try {
    let response
    if (isEdit.value) {
      // 更新项目
      response = await request.put(`/project/projects/${route.params.id}/`, projectForm)
      ElMessage.success('项目更新成功')
    } else {
      // 创建项目
      response = await request.post('/project/projects/', projectForm)
      ElMessage.success('项目创建成功')
    }
    // 跳转到项目详情页或列表页
    router.push(`/projects/${response.id}`)
  } catch (error) {
    ElMessage.error(isEdit.value ? '项目更新失败：' + error.message : '项目创建失败：' + error.message)
  }
}

// 取消操作
const handleCancel = () => {
  router.back()
}

// 初始化
onMounted(() => {
  if (isEdit.value) {
    getProjectDetail()
  } else {
    // 生成默认项目编号
    const now = new Date()
    projectForm.code = `PRJ${now.getFullYear()}${(now.getMonth() + 1).toString().padStart(2, '0')}${now.getDate().toString().padStart(2, '0')}${Math.floor(1000 + Math.random() * 9000)}`
  }
})
</script>

<style scoped>
.project-form-container {
  padding: 20px;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.project-form {
  margin-top: 20px;
}

.form-actions {
  display: flex;
  gap: 10px;
}
</style>
