<template>
  <div class="task-form-container">
    <el-card>
      <template #header>
        <div class="card-header">
          <h2>{{ isEdit ? '编辑任务' : '新建任务' }}</h2>
        </div>
      </template>
      
      <el-form
        ref="taskFormRef"
        :model="taskForm"
        :rules="rules"
        label-width="120px"
        class="task-form"
      >
        <el-row :gutter="20">
          <el-col :span="12">
            <el-form-item label="任务标题" prop="title">
              <el-input
                v-model="taskForm.title"
                placeholder="请输入任务标题"
                clearable
              />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="任务状态" prop="status">
              <el-select v-model="taskForm.status" placeholder="请选择任务状态">
                <el-option label="未开始" :value="1" />
                <el-option label="进行中" :value="2" />
                <el-option label="已完成" :value="3" />
                <el-option label="已延期" :value="4" />
                <el-option label="已取消" :value="5" />
              </el-select>
            </el-form-item>
          </el-col>
        </el-row>
        
        <el-row :gutter="20">
          <el-col :span="12">
            <el-form-item label="优先级" prop="priority">
              <el-select v-model="taskForm.priority" placeholder="请选择优先级">
                <el-option label="低" :value="1" />
                <el-option label="中" :value="2" />
                <el-option label="高" :value="3" />
                <el-option label="紧急" :value="4" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="所属项目" prop="project_id">
              <el-select v-model="taskForm.project_id" placeholder="请选择所属项目">
                <!-- 这里需要动态加载项目列表 -->
                <el-option label="测试项目" :value="1" />
              </el-select>
            </el-form-item>
          </el-col>
        </el-row>
        
        <el-row :gutter="20">
          <el-col :span="12">
            <el-form-item label="负责人" prop="assignee_id">
              <el-select v-model="taskForm.assignee_id" placeholder="请选择负责人">
                <!-- 这里需要动态加载用户列表 -->
                <el-option label="管理员" :value="1" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="预估工时" prop="estimated_hours">
              <el-input-number
                v-model="taskForm.estimated_hours"
                placeholder="请输入预估工时"
                :min="0"
                :step="1"
              />
            </el-form-item>
          </el-col>
        </el-row>
        
        <el-row :gutter="20">
          <el-col :span="12">
            <el-form-item label="开始日期" prop="start_date">
              <el-date-picker
                v-model="taskForm.start_date"
                type="date"
                placeholder="请选择开始日期"
                style="width: 100%"
              />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="结束日期" prop="end_date">
              <el-date-picker
                v-model="taskForm.end_date"
                type="date"
                placeholder="请选择结束日期"
                style="width: 100%"
              />
            </el-form-item>
          </el-col>
        </el-row>
        
        <el-form-item label="任务描述" prop="description">
          <el-input
            v-model="taskForm.description"
            type="textarea"
            placeholder="请输入任务描述"
            :rows="4"
          />
        </el-form-item>
        
        <el-form-item label="参与人员">
          <el-select
            v-model="taskForm.participants_ids"
            placeholder="请选择参与人员"
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
const taskFormRef = ref(null)

// 判断是否是编辑模式
const isEdit = computed(() => !!route.params.id)

// 任务表单数据
const taskForm = reactive({
  title: '',
  status: 1,
  priority: 2,
  project_id: '',
  assignee_id: '',
  estimated_hours: 0,
  actual_hours: 0,
  start_date: '',
  end_date: '',
  progress: 0,
  description: '',
  participants_ids: []
})

// 表单验证规则
const rules = {
  title: [
    { required: true, message: '请输入任务标题', trigger: 'blur' },
    { min: 2, max: 255, message: '任务标题长度应在 2 到 255 个字符之间', trigger: 'blur' }
  ],
  status: [
    { required: true, message: '请选择任务状态', trigger: 'change' }
  ],
  priority: [
    { required: true, message: '请选择优先级', trigger: 'change' }
  ],
  project_id: [
    { required: true, message: '请选择所属项目', trigger: 'change' }
  ],
  assignee_id: [
    { required: true, message: '请选择负责人', trigger: 'change' }
  ],
  start_date: [
    { required: true, message: '请选择开始日期', trigger: 'change' }
  ],
  end_date: [
    { required: true, message: '请选择结束日期', trigger: 'change' }
  ]
}

// 获取任务详情
const getTaskDetail = async () => {
  try {
    const response = await request.get(`/project/tasks/${route.params.id}/`)
    // 填充表单数据
    Object.assign(taskForm, response)
    // 处理关联数据
    taskForm.assignee_id = response.assignee.id
    taskForm.project_id = response.project.id
    taskForm.participants_ids = response.participants.map(participant => participant.id)
  } catch (error) {
    ElMessage.error('获取任务详情失败：' + error.message)
  }
}

// 提交表单
const handleSubmit = async () => {
  if (!await taskFormRef.value.validate()) {
    return
  }
  
  try {
    let response
    if (isEdit.value) {
      // 更新任务
      response = await request.put(`/project/tasks/${route.params.id}/`, taskForm)
      ElMessage.success('任务更新成功')
    } else {
      // 创建任务
      response = await request.post('/project/tasks/', taskForm)
      ElMessage.success('任务创建成功')
    }
    // 跳转到任务列表页
    router.push('/tasks')
  } catch (error) {
    ElMessage.error(isEdit.value ? '任务更新失败：' + error.message : '任务创建失败：' + error.message)
  }
}

// 取消操作
const handleCancel = () => {
  router.back()
}

// 初始化
onMounted(() => {
  if (isEdit.value) {
    getTaskDetail()
  }
})
</script>

<style scoped>
.task-form-container {
  padding: 20px;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.task-form {
  margin-top: 20px;
}

.form-actions {
  display: flex;
  gap: 10px;
}
</style>
