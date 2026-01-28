<template>
  <div class="task-list-container">
    <el-card>
      <template #header>
        <div class="card-header">
          <h2>任务管理</h2>
          <el-button type="primary" @click="$router.push('/tasks/create')">
            <el-icon-plus></el-icon-plus> 新建任务
          </el-button>
        </div>
      </template>
      
      <!-- 搜索和筛选区域 -->
      <el-form :inline="true" class="search-form">
        <el-form-item label="任务标题">
          <el-input
            v-model="searchForm.title"
            placeholder="请输入任务标题"
            clearable
            @keyup.enter="handleSearch"
          />
        </el-form-item>
        <el-form-item label="任务状态">
          <el-select v-model="searchForm.status" placeholder="请选择任务状态" clearable>
            <el-option label="未开始" :value="1" />
            <el-option label="进行中" :value="2" />
            <el-option label="已完成" :value="3" />
            <el-option label="已延期" :value="4" />
            <el-option label="已取消" :value="5" />
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
      
      <!-- 任务列表 -->
      <el-table
        v-loading="loading"
        :data="tasks"
        style="width: 100%"
        border
      >
        <el-table-column type="selection" width="55" />
        <el-table-column prop="id" label="ID" width="80" />
        <el-table-column prop="title" label="任务标题" min-width="200" />
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
        <el-table-column prop="assignee_name" label="负责人" width="120" />
        <el-table-column prop="start_date" label="开始日期" width="120" />
        <el-table-column prop="end_date" label="结束日期" width="120">
          <template #default="scope">
            <span :class="{ 'overdue': scope.row.is_overdue }">
              {{ scope.row.end_date }}
            </span>
          </template>
        </el-table-column>
        <el-table-column prop="estimated_hours" label="预估工时" width="120" />
        <el-table-column prop="actual_hours" label="实际工时" width="120" />
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
import { ref, reactive, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import request from '../utils/request'

// 搜索表单
const searchForm = ref({
  title: '',
  status: '',
  priority: ''
})

// 分页数据
const pagination = ref({
  currentPage: 1,
  pageSize: 20
})

// 任务列表数据
const tasks = ref([])
const total = ref(0)
const loading = ref(false)

// 获取任务列表
const getTasks = async () => {
  loading.value = true
  try {
    const params = {
      page: pagination.value.currentPage,
      limit: pagination.value.pageSize,
      ...searchForm.value
    }
    const response = await request.get('/project/tasks/', { params })
    tasks.value = response.results
    total.value = response.count
  } catch (error) {
    ElMessage.error('获取任务列表失败：' + error.message)
  } finally {
    loading.value = false
  }
}

// 搜索
const handleSearch = () => {
  pagination.value.currentPage = 1
  getTasks()
}

// 重置
const handleReset = () => {
  searchForm.value = {
    title: '',
    status: '',
    priority: ''
  }
  pagination.value.currentPage = 1
  getTasks()
}

// 分页大小变化
const handleSizeChange = (size) => {
  pagination.value.pageSize = size
  getTasks()
}

// 当前页码变化
const handleCurrentChange = (current) => {
  pagination.value.currentPage = current
  getTasks()
}

// 查看任务详情
const handleView = (row) => {
  $router.push(`/tasks/${row.id}`)
}

// 编辑任务
const handleEdit = (row) => {
  $router.push(`/tasks/${row.id}/edit`)
}

// 删除任务
const handleDelete = (row) => {
  ElMessageBox.confirm('确定要删除这个任务吗？', '提示', {
    confirmButtonText: '确定',
    cancelButtonText: '取消',
    type: 'warning'
  }).then(async () => {
    try {
      await request.delete(`/project/tasks/${row.id}/`)
      ElMessage.success('删除成功')
      getTasks()
    } catch (error) {
      ElMessage.error('删除失败：' + error.message)
    }
  }).catch(() => {
    // 取消删除
  })
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
  getTasks()
})
</script>

<style scoped>
.task-list-container {
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

.pagination-container {
  margin-top: 20px;
  text-align: right;
}

.overdue {
  color: #ff4d4f;
  font-weight: bold;
}
</style>
