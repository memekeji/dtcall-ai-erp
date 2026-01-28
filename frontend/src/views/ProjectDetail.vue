<template>
  <div class="project-detail-container">
    <el-card>
      <template #header>
        <div class="card-header">
          <h2>项目详情</h2>
          <el-button type="primary" @click="$router.push(`/projects/${project.id}/edit`)" v-if="project">
            <el-icon-edit></el-icon-edit> 编辑
          </el-button>
        </div>
      </template>
      
      <div v-if="loading" class="loading-container">
        <el-skeleton :rows="10" animated />
      </div>
      
      <div v-else-if="project" class="project-detail-content">
        <!-- 项目基本信息 -->
        <el-descriptions title="项目基本信息" :column="2" border>
          <el-descriptions-item label="项目名称">{{ project.name }}</el-descriptions-item>
          <el-descriptions-item label="项目编号">{{ project.code }}</el-descriptions-item>
          <el-descriptions-item label="项目状态">
            <el-tag :type="getStatusTagType(project.status)">
              {{ project.status_display }}
            </el-tag>
          </el-descriptions-item>
          <el-descriptions-item label="优先级">
            <el-tag :type="getPriorityTagType(project.priority)">
              {{ project.priority_display }}
            </el-tag>
          </el-descriptions-item>
          <el-descriptions-item label="项目经理">{{ project.manager_name }}</el-descriptions-item>
          <el-descriptions-item label="关联客户">{{ project.customer_name }}</el-descriptions-item>
          <el-descriptions-item label="开始日期">{{ project.start_date }}</el-descriptions-item>
          <el-descriptions-item label="结束日期">
            <span :class="{ 'overdue': project.is_overdue }">
              {{ project.end_date }}
            </span>
          </el-descriptions-item>
          <el-descriptions-item label="项目预算">¥{{ project.budget }}</el-descriptions-item>
          <el-descriptions-item label="实际成本">¥{{ project.actual_cost }}</el-descriptions-item>
          <el-descriptions-item label="完成进度">
            <el-progress
              :percentage="project.progress"
              :stroke-width="10"
              :format="(percentage) => `${percentage}%`"
              :color="getProgressColor(project.progress)"
            />
          </el-descriptions-item>
          <el-descriptions-item label="创建时间">{{ project.create_time }}</el-descriptions-item>
        </el-descriptions>
        
        <!-- 项目描述 -->
        <el-card shadow="hover" style="margin-top: 20px;">
          <template #header>
            <h3>项目描述</h3>
          </template>
          <div class="project-description">{{ project.description || '暂无描述' }}</div>
        </el-card>
        
        <!-- 项目成员 -->
        <el-card shadow="hover" style="margin-top: 20px;">
          <template #header>
            <h3>项目成员</h3>
          </template>
          <div class="project-members">
            <el-tag
              v-for="member in project.members"
              :key="member.id"
              type="primary"
              effect="light"
              style="margin-right: 10px; margin-bottom: 10px;"
            >
              {{ member.username }}
            </el-tag>
            <span v-if="project.members.length === 0" class="empty-text">暂无项目成员</span>
          </div>
        </el-card>
        
        <!-- 项目统计 -->
        <el-card shadow="hover" style="margin-top: 20px;">
          <template #header>
            <h3>项目统计</h3>
          </template>
          <el-row :gutter="16">
            <el-col :span="6">
              <div class="stat-item">
                <div class="stat-number">{{ projectStats.task_total }}</div>
                <div class="stat-label">总任务数</div>
              </div>
            </el-col>
            <el-col :span="6">
              <div class="stat-item">
                <div class="stat-number">{{ projectStats.task_completed }}</div>
                <div class="stat-label">已完成任务</div>
              </div>
            </el-col>
            <el-col :span="6">
              <div class="stat-item">
                <div class="stat-number">{{ projectStats.task_in_progress }}</div>
                <div class="stat-label">进行中任务</div>
              </div>
            </el-col>
            <el-col :span="6">
              <div class="stat-item">
                <div class="stat-number">{{ projectStats.total_hours }}</div>
                <div class="stat-label">总工时</div>
              </div>
            </el-col>
          </el-row>
        </el-card>
      </div>
      
      <div v-else class="empty-container">
        <el-empty description="暂无项目数据" />
      </div>
    </el-card>
  </div>
</template>

<script setup>
import { ref, onMounted, computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import request from '../utils/request'

const route = useRoute()
const router = useRouter()

const project = ref(null)
const loading = ref(false)
const projectStats = ref({
  task_total: 0,
  task_completed: 0,
  task_in_progress: 0,
  total_hours: 0
})

// 获取项目详情
const getProjectDetail = async () => {
  loading.value = true
  try {
    const response = await request.get(`/project/projects/${route.params.id}/`)
    project.value = response
    // 获取项目统计信息
    getProjectStats()
  } catch (error) {
    ElMessage.error('获取项目详情失败：' + error.message)
  } finally {
    loading.value = false
  }
}

// 获取项目统计信息
const getProjectStats = async () => {
  try {
    const response = await request.get(`/project/projects/${route.params.id}/stats/`)
    projectStats.value = response
  } catch (error) {
    ElMessage.error('获取项目统计信息失败：' + error.message)
  }
}

// 获取状态标签类型
const getStatusTagType = (status) => {
  const statusMap = {
    1: 'info',
    2: 'primary',
    3: 'success',
    4: 'danger',
    5: 'warning'
  }
  return statusMap[status] || 'default'
}

// 获取优先级标签类型
const getPriorityTagType = (priority) => {
  const priorityMap = {
    1: 'info',
    2: 'success',
    3: 'warning',
    4: 'danger'
  }
  return priorityMap[priority] || 'default'
}

// 获取进度条颜色
const getProgressColor = (progress) => {
  if (progress < 30) {
    return '#ff4d4f'
  } else if (progress < 70) {
    return '#faad14'
  } else {
    return '#52c41a'
  }
}

// 初始化
onMounted(() => {
  getProjectDetail()
})
</script>

<style scoped>
.project-detail-container {
  padding: 20px;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.loading-container {
  padding: 20px 0;
}

.project-detail-content {
  margin-top: 20px;
}

.project-description {
  line-height: 1.8;
  color: #333;
}

.project-members {
  display: flex;
  flex-wrap: wrap;
}

.stat-item {
  text-align: center;
  padding: 20px 0;
}

.stat-number {
  font-size: 28px;
  font-weight: bold;
  margin-bottom: 8px;
  color: #333;
}

.stat-label {
  font-size: 14px;
  color: #666;
}

.overdue {
  color: #ff4d4f;
  font-weight: bold;
}

.empty-container {
  text-align: center;
  padding: 50px 0;
}
</style>
