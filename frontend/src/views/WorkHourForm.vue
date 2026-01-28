<template>
  <div class="work-hour-form-container">
    <el-card>
      <template #header>
        <div class="card-header">
          <h2>{{ isEdit ? '编辑工时记录' : '新建工时记录' }}</h2>
        </div>
      </template>
      
      <el-form
        ref="workHourFormRef"
        :model="workHourForm"
        :rules="rules"
        label-width="120px"
        class="work-hour-form"
      >
        <el-row :gutter="20">
          <el-col :span="12">
            <el-form-item label="所属任务" prop="task_id">
              <el-select v-model="workHourForm.task_id" placeholder="请选择所属任务">
                <!-- 这里需要动态加载任务列表 -->
                <el-option label="测试任务" :value="1" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="工作人员" prop="user_id">
              <el-select v-model="workHourForm.user_id" placeholder="请选择工作人员">
                <!-- 这里需要动态加载用户列表 -->
                <el-option label="管理员" :value="1" />
              </el-select>
            </el-form-item>
          </el-col>
        </el-row>
        
        <el-row :gutter="20">
          <el-col :span="12">
            <el-form-item label="工作日期" prop="work_date">
              <el-date-picker
                v-model="workHourForm.work_date"
                type="date"
                placeholder="请选择工作日期"
                style="width: 100%"
              />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="工作时长" prop="hours">
              <el-input-number
                v-model="workHourForm.hours"
                placeholder="请输入工作时长"
                :min="0.5"
                :step="0.5"
                :precision="1"
              />
            </el-form-item>
          </el-col>
        </el-row>
        
        <el-form-item label="工作内容描述" prop="description">
          <el-input
            v-model="workHourForm.description"
            type="textarea"
            placeholder="请输入工作内容描述"
            :rows="4"
          />
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
const workHourFormRef = ref(null)

// 判断是否是编辑模式
const isEdit = computed(() => !!route.params.id)

// 工时表单数据
const workHourForm = reactive({
  task_id: '',
  user_id: '',
  work_date: '',
  hours: 0.5,
  description: ''
})

// 表单验证规则
const rules = {
  task_id: [
    { required: true, message: '请选择所属任务', trigger: 'change' }
  ],
  user_id: [
    { required: true, message: '请选择工作人员', trigger: 'change' }
  ],
  work_date: [
    { required: true, message: '请选择工作日期', trigger: 'change' }
  ],
  hours: [
    { required: true, message: '请输入工作时长', trigger: 'change' },
    { type: 'number', min: 0.5, message: '工作时长不能小于0.5小时', trigger: 'change' }
  ],
  description: [
    { required: true, message: '请输入工作内容描述', trigger: 'blur' },
    { min: 5, max: 500, message: '工作内容描述长度应在 5 到 500 个字符之间', trigger: 'blur' }
  ]
}

// 获取工时记录详情
const getWorkHourDetail = async () => {
  try {
    const response = await request.get(`/project/work-hours/${route.params.id}/`)
    // 填充表单数据
    Object.assign(workHourForm, response)
  } catch (error) {
    ElMessage.error('获取工时记录详情失败：' + error.message)
  }
}

// 提交表单
const handleSubmit = async () => {
  if (!await workHourFormRef.value.validate()) {
    return
  }
  
  try {
    let response
    if (isEdit.value) {
      // 更新工时记录
      response = await request.put(`/project/work-hours/${route.params.id}/`, workHourForm)
      ElMessage.success('工时记录更新成功')
    } else {
      // 创建工时记录
      response = await request.post('/project/work-hours/', workHourForm)
      ElMessage.success('工时记录创建成功')
    }
    // 跳转到工时列表页
    router.push('/work-hours')
  } catch (error) {
    ElMessage.error(isEdit.value ? '工时记录更新失败：' + error.message : '工时记录创建失败：' + error.message)
  }
}

// 取消操作
const handleCancel = () => {
  router.back()
}

// 初始化
onMounted(() => {
  if (isEdit.value) {
    getWorkHourDetail()
  } else {
    // 默认工作日期为今天
    workHourForm.work_date = new Date()
  }
})
</script>

<style scoped>
.work-hour-form-container {
  padding: 20px;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.work-hour-form {
  margin-top: 20px;
}

.form-actions {
  display: flex;
  gap: 10px;
}
</style>
