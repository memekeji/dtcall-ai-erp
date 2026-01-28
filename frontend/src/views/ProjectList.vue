<template>
  <div class="project-list-container">
    <el-card>
      <template #header>
        <div class="card-header">
          <h2>项目列表</h2>
          <el-button type="primary" @click="$router.push('/projects/create')">
            <el-icon-plus></el-icon-plus> 新建项目
          </el-button>
        </div>
      </template>
      
      <!-- 搜索和筛选区域 -->
      <el-form :inline="true" class="search-form">
        <el-form-item label="项目名称">
          <el-input
            v-model="searchForm.name"
            placeholder="请输入项目名称"
            clearable
            @keyup.enter="handleSearch"
          />
        </el-form-item>
        <el-form-item label="项目状态">
          <el-select v-model="searchForm.status" placeholder="请选择项目状态" clearable>
            <el-option label="未开始" :value="1" />
            <el-option label="进行中" :value="2" />
            <el-option label="已完成" :value="3" />
            <el-option label="已关闭" :value="4" />
            <el-option label="已暂停" :value="5" />
          </el-select>
        </el-form-item>
        <el-form-item label="优先级">
          <el-select v-model="searchForm.priority" placeholder="请选择优先级" clearable>
            <el-option label="低" :value="1" />
            <el-option label="中" :value="2" />
            <el-option label="高" :value="3" />
            <el-option label="紧急" :value="4" />
          </el-select>
        </el-form-item>
        <el-form-item>
          <el-button type="primary" @click="handleSearch">
            <el-icon-search></el-icon-search> 搜索
          </el-button>
          <el-button @click="handleReset">
            <el-icon-refresh-right></el-icon-refresh-right> 重置
          </el-button>
        </el-form-item>
      </el-form>
      
      <!-- 项目统计卡片 -->
      <el-row :gutter="16" style="margin-bottom: 20px;">
        <el-col :span="6">
          <el-card shadow="hover" class="stat-card">
            <div class="stat-content">
              <div class="stat-number">{{ totalProjects }}</div>
              <div class="stat-label">总项目数</div>
            </div>
          </el-card>
        </el-col>
        <el-col :span="6">
          <el-card shadow="hover" class="stat-card stat-active">
            <div class="stat-content">
              <div class="stat-number">{{ inProgressProjects }}</div>
              <div class="stat-label">进行中项目</div>
            </div>
          </el-card>
        </el-col>
        <el-col :span="6">
          <el-card shadow="hover" class="stat-card stat-completed">
            <div class="stat-content">
              <div class="stat-number">{{ completedProjects }}</div>
              <div class="stat-label">已完成项目</div>
            </div>
          </el-card>
        </el-col>
        <el-col :span="6">
          <el-card shadow="hover" class="stat-card stat-overdue">
            <div class="stat-content">
              <div class="stat-number">{{ overdueProjects }}</div>
              <div class="stat-label">逾期项目</div>
            </div>
          </el-card>
        </el-col>
      </el-row>
      
      <!-- 项目列表 -->
      <el-table
        v-loading="loading"
        :data="projects"
        style="width: 100%"
        border
        @selection-change="handleSelectionChange"
      >
        <el-table-column type="selection" width="55" />
        <el-table-column prop="id" label="ID" width="80" />
        <el-table-column prop="name" label="项目名称" min-width="200">
          <template #default="scope">
            <a href="javascript:void(0)" @click="handleView(scope.row)">{{ scope.row.name }}</a>
          </template>
        </el-table-column>
        <el-table-column prop="code" label="项目编号" width="150" />
        <el-table-column prop="status_display" label="状态" width="100">
          <template #default="scope">
            <el-tag :type="getStatusTagType(scope.row.status)">
              {{ scope.row.status_display }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="priority_display" label="优先级" width="80">
          <template #default="scope">
            <el-tag :type="getPriorityTagType(scope.row.priority)">
              {{ scope.row.priority_display }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="progress" label="进度" width="150">
          <template #default="scope">
            <el-progress
              :percentage="scope.row.progress"
              :stroke-width="10"
              :format="(percentage) => `${percentage}%`"
              :color="getProgressColor(scope.row.progress)"
            />
          </template>
        </el-table-column>
        <el-table-column prop="manager_name" label="项目经理" width="120" />
        <el-table-column prop="customer_name" label="关联客户" width="150" />
        <el-table-column prop="start_date" label="开始日期" width="120" />
        <el-table-column prop="end_date" label="结束日期" width="120">
          <template #default="scope">
            <span :class="{ 'overdue': scope.row.is_overdue }">
              {{ scope.row.end_date }}
            </span>
          </template>
        </el-table-column>
        <el-table-column prop="budget" label="预算" width="120">
          <template #default="scope">
            ¥{{ scope.row.budget }}
          </template>
        </el-table-column>
        <el-table-column prop="create_time" label="创建时间" width="180" />
        <el-table-column label="操作" width="200" fixed="right">
          <template #default="scope">
            <el-button type="primary" size="small" @click="handleView(scope.row)">
              <el-icon-view></el-icon-view> 查看
            </el-button>
            <el-button type="success" size="small" @click="handleEdit(scope.row)">
              <el-icon-edit></el-icon-edit> 编辑
            </el-button>
            <el-button type="danger" size="small" @click="handleDelete(scope.row)">
              <el-icon-delete></el-icon-delete> 删除
            </el-button>
          </template>
        </el-table-column>
      </el-table>
      
      <!-- 分页 -->
      <div class="pagination-container">
        <el-pagination
          v-model:current-page="pagination.currentPage"
          v-model:page-size="pagination.pageSize"
          :page-sizes="[10, 20, 50, 100]"
          layout="total, sizes, prev, pager, next, jumper"
          :total="total"
          @size-change="handleSizeChange"
          @current-change="handleCurrentChange"
        />
      </div>
    </el-card>
  </div>
</template>

<script setup>
import { ref, onMounted, computed } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import request from '../utils/request'

// 搜索表单
const searchForm = ref({
  name: '',
  status: '',
  priority: ''
})

// 分页数据
const pagination = ref({
  currentPage: 1,
  pageSize: 20
})

// 项目列表数据
const projects = ref([])
const total = ref(0)
const loading = ref(false)

// 统计数据
const totalProjects = ref(0)
const inProgressProjects = ref(0)
const completedProjects = ref(0)
const overdueProjects = ref(0)

// 选中的项目
const selectedProjects = ref([])

// 获取项目列表
const getProjects = async () => {
  loading.value = true
  try {
    const params = {
      page: pagination.value.currentPage,
      limit: pagination.value.pageSize,
      ...searchForm.value
    }
    const response = await request.get('/project/projects/', { params })
    projects.value = response.results
    total.value = response.count
    // 更新统计数据
    updateStats(response.results)
  } catch (error) {
    ElMessage.error('获取项目列表失败：' + error.message)
  } finally {
    loading.value = false
  }
}

// 更新统计数据
const updateStats = (data) => {
  totalProjects.value = data.length
  inProgressProjects.value = data.filter(item => item.status === 2).length
  completedProjects.value = data.filter(item => item.status === 3).length
  overdueProjects.value = data.filter(item => item.is_overdue).length
}

// 搜索
const handleSearch = () => {
  pagination.value.currentPage = 1
  getProjects()
}

// 重置
const handleReset = () => {
  searchForm.value = {
    name: '',
    status: '',
    priority: ''
  }
  pagination.value.currentPage = 1
  getProjects()
}

// 分页大小变化
const handleSizeChange = (size) => {
  pagination.value.pageSize = size
  getProjects()
}

// 当前页码变化
const handleCurrentChange = (current) => {
  pagination.value.currentPage = current
  getProjects()
}

// 查看项目详情
const handleView = (row) => {
  $router.push(`/projects/${row.id}`)
}

// 编辑项目
const handleEdit = (row) => {
  $router.push(`/projects/${row.id}/edit`)
}

// 删除项目
const handleDelete = (row) => {
  ElMessageBox.confirm('确定要删除这个项目吗？', '提示', {
    confirmButtonText: '确定',
    cancelButtonText: '取消',
    type: 'warning'
  }).then(async () => {
    try {
      await request.delete(`/project/projects/${row.id}/`)
      ElMessage.success('删除成功')
      getProjects()
    } catch (error) {
      ElMessage.error('删除失败：' + error.message)
    }
  }).catch(() => {
    // 取消删除
  })
}

// 选择项目
const handleSelectionChange = (selection) => {
  selectedProjects.value = selection
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
  getProjects()
})
</script>

<style scoped>
.project-list-container {
  padding: 20px;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.search-form {
  margin-bottom: 20px;
}

.stat-card {
  text-align: center;
  cursor: pointer;
  transition: all 0.3s ease;
}

.stat-card:hover {
  transform: translateY(-5px);
  box-shadow: 0 10px 20px rgba(0, 0, 0, 0.1);
}

.stat-content {
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

.stat-active {
  border-left: 4px solid #1890ff;
}

.stat-completed {
  border-left: 4px solid #52c41a;
}

.stat-overdue {
  border-left: 4px solid #ff4d4f;
}

.pagination-container {
  margin-top: 20px;
  text-align: right;
}

.overdue {
  color: #ff4d4f;
  font-weight: bold;
}
</style>
