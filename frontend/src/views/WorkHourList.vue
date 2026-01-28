<template>
  <div class="work-hour-list-container">
    <el-card>
      <template #header>
        <div class="card-header">
          <h2>工时管理</h2>
          <el-button type="primary" @click="$router.push('/work-hours/create')">
            <el-icon-plus></el-icon-plus> 新建工时记录
          </el-button>
        </div>
      </template>
      
      <!-- 搜索和筛选区域 -->
      <el-form :inline="true" class="search-form">
        <el-form-item label="任务名称">
          <el-input
            v-model="searchForm.task_name"
            placeholder="请输入任务名称"
            clearable
            @keyup.enter="handleSearch"
          />
        </el-form-item>
        <el-form-item label="工作人员">
          <el-select v-model="searchForm.user_id" placeholder="请选择工作人员" clearable>
            <!-- 这里需要动态加载用户列表 -->
            <el-option label="管理员" :value="1" />
          </el-select>
        </el-form-item>
        <el-form-item label="工作日期">
          <el-date-picker
            v-model="searchForm.work_date"
            type="daterange"
            range-separator="至"
            start-placeholder="开始日期"
            end-placeholder="结束日期"
          />
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
      
      <!-- 工时列表 -->
      <el-table
        v-loading="loading"
        :data="workHours"
        style="width: 100%"
        border
      >
        <el-table-column prop="id" label="ID" width="80" />
        <el-table-column prop="task_name" label="任务名称" min-width="200" />
        <el-table-column prop="user_name" label="工作人员" width="120" />
        <el-table-column prop="work_date" label="工作日期" width="120" />
        <el-table-column prop="hours" label="工作时长(小时)" width="150" />
        <el-table-column prop="description" label="工作内容描述" min-width="200" />
        <el-table-column prop="create_time" label="记录时间" width="180" />
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
  task_name: '',
  user_id: '',
  work_date: []
})

// 分页数据
const pagination = ref({
  currentPage: 1,
  pageSize: 20
})

// 工时列表数据
const workHours = ref([])
const total = ref(0)
const loading = ref(false)

// 获取工时列表
const getWorkHours = async () => {
  loading.value = true
  try {
    const params = {
      page: pagination.value.currentPage,
      limit: pagination.value.pageSize,
      ...searchForm.value
    }
    const response = await request.get('/project/work-hours/', { params })
    workHours.value = response.results
    total.value = response.count
  } catch (error) {
    ElMessage.error('获取工时列表失败：' + error.message)
  } finally {
    loading.value = false
  }
}

// 搜索
const handleSearch = () => {
  pagination.value.currentPage = 1
  getWorkHours()
}

// 重置
const handleReset = () => {
  searchForm.value = {
    task_name: '',
    user_id: '',
    work_date: []
  }
  pagination.value.currentPage = 1
  getWorkHours()
}

// 分页大小变化
const handleSizeChange = (size) => {
  pagination.value.pageSize = size
  getWorkHours()
}

// 当前页码变化
const handleCurrentChange = (current) => {
  pagination.value.currentPage = current
  getWorkHours()
}

// 查看工时记录详情
const handleView = (row) => {
  $router.push(`/work-hours/${row.id}`)
}

// 编辑工时记录
const handleEdit = (row) => {
  $router.push(`/work-hours/${row.id}/edit`)
}

// 删除工时记录
const handleDelete = (row) => {
  ElMessageBox.confirm('确定要删除这个工时记录吗？', '提示', {
    confirmButtonText: '确定',
    cancelButtonText: '取消',
    type: 'warning'
  }).then(async () => {
    try {
      await request.delete(`/project/work-hours/${row.id}/`)
      ElMessage.success('删除成功')
      getWorkHours()
    } catch (error) {
      ElMessage.error('删除失败：' + error.message)
    }
  }).catch(() => {
    // 取消删除
  })
}

// 初始化
onMounted(() => {
  getWorkHours()
})
</script>

<style scoped>
.work-hour-list-container {
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
</style>
