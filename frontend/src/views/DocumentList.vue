<template>
  <div class="document-list-container">
    <el-card>
      <template #header>
        <div class="card-header">
          <h2>文档管理</h2>
          <el-button type="primary" @click="$router.push('/documents/create')">
            <el-icon-plus></el-icon-plus> 上传文档
          </el-button>
        </div>
      </template>
      
      <!-- 搜索和筛选区域 -->
      <el-form :inline="true" class="search-form">
        <el-form-item label="文档标题">
          <el-input
            v-model="searchForm.title"
            placeholder="请输入文档标题"
            clearable
            @keyup.enter="handleSearch"
          />
        </el-form-item>
        <el-form-item label="所属项目">
          <el-select v-model="searchForm.project_id" placeholder="请选择所属项目" clearable>
            <!-- 这里需要动态加载项目列表 -->
            <el-option label="测试项目" :value="1" />
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
      
      <!-- 文档列表 -->
      <el-table
        v-loading="loading"
        :data="documents"
        style="width: 100%"
        border
      >
        <el-table-column prop="id" label="ID" width="80" />
        <el-table-column prop="title" label="文档标题" min-width="200" />
        <el-table-column prop="project_name" label="所属项目" width="150" />
        <el-table-column prop="creator_name" label="上传人" width="120" />
        <el-table-column prop="file_path" label="文件路径" min-width="200" />
        <el-table-column prop="create_time" label="上传时间" width="180" />
        <el-table-column label="操作" width="150" fixed="right">
          <template #default="scope">
            <el-button type="primary" size="small" @click="handleView(scope.row)">
              <el-icon-view></el-icon-view> 查看
            </el-button>
            <el-button type="success" size="small" @click="handleEdit(scope.row)">
              <el-icon-edit></el-icon-edit> 编辑
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
import { ElMessage } from 'element-plus'
import request from '../utils/request'

// 搜索表单
const searchForm = ref({
  title: '',
  project_id: ''
})

// 分页数据
const pagination = ref({
  currentPage: 1,
  pageSize: 20
})

// 文档列表数据
const documents = ref([])
const total = ref(0)
const loading = ref(false)

// 获取文档列表
const getDocuments = async () => {
  loading.value = true
  try {
    const params = {
      page: pagination.value.currentPage,
      limit: pagination.value.pageSize,
      ...searchForm.value
    }
    const response = await request.get('/project/project-documents/', { params })
    documents.value = response.results
    total.value = response.count
  } catch (error) {
    ElMessage.error('获取文档列表失败：' + error.message)
  } finally {
    loading.value = false
  }
}

// 搜索
const handleSearch = () => {
  pagination.value.currentPage = 1
  getDocuments()
}

// 重置
const handleReset = () => {
  searchForm.value = {
    title: '',
    project_id: ''
  }
  pagination.value.currentPage = 1
  getDocuments()
}

// 分页大小变化
const handleSizeChange = (size) => {
  pagination.value.pageSize = size
  getDocuments()
}

// 当前页码变化
const handleCurrentChange = (current) => {
  pagination.value.currentPage = current
  getDocuments()
}

// 查看文档详情
const handleView = (row) => {
  console.log('View document:', row)
  // 跳转到文档详情页
}

// 编辑文档
const handleEdit = (row) => {
  console.log('Edit document:', row)
  // 跳转到文档编辑页
  // $router.push(`/documents/${row.id}/edit`)
}

// 初始化
onMounted(() => {
  getDocuments()
})
</script>

<style scoped>
.document-list-container {
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
