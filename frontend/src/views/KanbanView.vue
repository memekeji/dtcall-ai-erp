<template>
  <div class="kanban-view-container">
    <el-card>
      <template #header>
        <div class="card-header">
          <h2>任务看板</h2>
          <el-select v-model="selectedProject" placeholder="选择项目" @change="loadKanbanData">
            <el-option
              v-for="project in projects"
              :key="project.id"
              :label="project.name"
              :value="project.id"
            />
          </el-select>
        </div>
      </template>
      
      <!-- 看板容器 -->
      <div class="kanban-container">
        <el-scrollbar wrap-class="kanban-scroll-wrap">
          <div class="kanban-board">
            <!-- 未开始列 -->
            <div class="kanban-column">
              <div class="column-header status-not-started">
                <h3>未开始</h3>
                <span class="task-count">{{ notStartedTasks.length }}</span>
              </div>
              <div class="column-content">
                <draggable
                  v-model="notStartedTasks"
                  group="tasks"
                  @change="handleTaskChange"
                  item-key="id"
                >
                  <template #item="{ element }">
                    <div class="task-card" @click="handleTaskClick(element)">
                      <div class="task-header">
                        <h4 class="task-title">{{ element.title }}</h4>
                        <el-tag :type="getPriorityTagType(element.priority)">
                          {{ element.priority_display }}
                        </el-tag>
                      </div>
                      <div class="task-body">
                        <p class="task-desc">{{ element.description || '无描述' }}</p>
                      </div>
                      <div class="task-footer">
                        <span class="task-assignee">{{ element.assignee_name || '未分配' }}</span>
                        <el-progress
                          :percentage="element.progress"
                          :stroke-width="6"
                          :show-text="false"
                          :color="getProgressColor(element.progress)"
                        />
                      </div>
                    </div>
                  </template>
                </draggable>
              </div>
            </div>
            
            <!-- 进行中列 -->
            <div class="kanban-column">
              <div class="column-header status-in-progress">
                <h3>进行中</h3>
                <span class="task-count">{{ inProgressTasks.length }}</span>
              </div>
              <div class="column-content">
                <draggable
                  v-model="inProgressTasks"
                  group="tasks"
                  @change="handleTaskChange"
                  item-key="id"
                >
                  <template #item="{ element }">
                    <div class="task-card" @click="handleTaskClick(element)">
                      <div class="task-header">
                        <h4 class="task-title">{{ element.title }}</h4>
                        <el-tag :type="getPriorityTagType(element.priority)">
                          {{ element.priority_display }}
                        </el-tag>
                      </div>
                      <div class="task-body">
                        <p class="task-desc">{{ element.description || '无描述' }}</p>
                      </div>
                      <div class="task-footer">
                        <span class="task-assignee">{{ element.assignee_name || '未分配' }}</span>
                        <el-progress
                          :percentage="element.progress"
                          :stroke-width="6"
                          :show-text="false"
                          :color="getProgressColor(element.progress)"
                        />
                      </div>
                    </div>
                  </template>
                </draggable>
              </div>
            </div>
            
            <!-- 已完成列 -->
            <div class="kanban-column">
              <div class="column-header status-completed">
                <h3>已完成</h3>
                <span class="task-count">{{ completedTasks.length }}</span>
              </div>
              <div class="column-content">
                <draggable
                  v-model="completedTasks"
                  group="tasks"
                  @change="handleTaskChange"
                  item-key="id"
                >
                  <template #item="{ element }">
                    <div class="task-card" @click="handleTaskClick(element)">
                      <div class="task-header">
                        <h4 class="task-title">{{ element.title }}</h4>
                        <el-tag :type="getPriorityTagType(element.priority)">
                          {{ element.priority_display }}
                        </el-tag>
                      </div>
                      <div class="task-body">
                        <p class="task-desc">{{ element.description || '无描述' }}</p>
                      </div>
                      <div class="task-footer">
                        <span class="task-assignee">{{ element.assignee_name || '未分配' }}</span>
                        <el-progress
                          :percentage="element.progress"
                          :stroke-width="6"
                          :show-text="false"
                          :color="getProgressColor(element.progress)"
                        />
                      </div>
                    </div>
                  </template>
                </draggable>
              </div>
            </div>
            
            <!-- 已延期列 -->
            <div class="kanban-column">
              <div class="column-header status-overdue">
                <h3>已延期</h3>
                <span class="task-count">{{ overdueTasks.length }}</span>
              </div>
              <div class="column-content">
                <draggable
                  v-model="overdueTasks"
                  group="tasks"
                  @change="handleTaskChange"
                  item-key="id"
                >
                  <template #item="{ element }">
                    <div class="task-card" @click="handleTaskClick(element)">
                      <div class="task-header">
                        <h4 class="task-title">{{ element.title }}</h4>
                        <el-tag :type="getPriorityTagType(element.priority)">
                          {{ element.priority_display }}
                        </el-tag>
                      </div>
                      <div class="task-body">
                        <p class="task-desc">{{ element.description || '无描述' }}</p>
                      </div>
                      <div class="task-footer">
                        <span class="task-assignee">{{ element.assignee_name || '未分配' }}</span>
                        <el-progress
                          :percentage="element.progress"
                          :stroke-width="6"
                          :show-text="false"
                          :color="getProgressColor(element.progress)"
                        />
                      </div>
                    </div>
                  </template>
                </draggable>
              </div>
            </div>
            
            <!-- 已取消列 -->
            <div class="kanban-column">
              <div class="column-header status-canceled">
                <h3>已取消</h3>
                <span class="task-count">{{ canceledTasks.length }}</span>
              </div>
              <div class="column-content">
                <draggable
                  v-model="canceledTasks"
                  group="tasks"
                  @change="handleTaskChange"
                  item-key="id"
                >
                  <template #item="{ element }">
                    <div class="task-card" @click="handleTaskClick(element)">
                      <div class="task-header">
                        <h4 class="task-title">{{ element.title }}</h4>
                        <el-tag :type="getPriorityTagType(element.priority)">
                          {{ element.priority_display }}
                        </el-tag>
                      </div>
                      <div class="task-body">
                        <p class="task-desc">{{ element.description || '无描述' }}</p>
                      </div>
                      <div class="task-footer">
                        <span class="task-assignee">{{ element.assignee_name || '未分配' }}</span>
                        <el-progress
                          :percentage="element.progress"
                          :stroke-width="6"
                          :show-text="false"
                          :color="getProgressColor(element.progress)"
                        />
                      </div>
                    </div>
                  </template>
                </draggable>
              </div>
            </div>
          </div>
        </el-scrollbar>
      </div>
    </el-card>
  </div>
</template>

<script setup>
import { ref, onMounted, watch } from 'vue'
import { ElMessage, ElLoading } from 'element-plus'
import request from '../utils/request'
import draggable from 'vuedraggable'

// 组件引用
const projects = ref([])
const selectedProject = ref('')

// 任务分组
const notStartedTasks = ref([])
const inProgressTasks = ref([])
const completedTasks = ref([])
const overdueTasks = ref([])
const canceledTasks = ref([])

// 加载项目列表
const loadProjects = async () => {
  try {
    const response = await request.get('/project/projects/', { params: { page: 1, limit: 100 } })
    projects.value = response.results
    if (projects.value.length > 0) {
      selectedProject.value = projects.value[0].id
    }
  } catch (error) {
    ElMessage.error('获取项目列表失败：' + error.message)
  }
}

// 加载看板数据
const loadKanbanData = async () => {
  if (!selectedProject.value) return
  
  const loading = ElLoading.service({ target: '.kanban-container', text: '加载看板数据中...' })
  try {
    // 获取项目任务
    const response = await request.get('/project/tasks/', { params: { project_id: selectedProject.value } })
    const tasks = response.results
    
    // 分组任务
    groupTasks(tasks)
  } catch (error) {
    ElMessage.error('获取看板数据失败：' + error.message)
  } finally {
    loading.close()
  }
}

// 分组任务
const groupTasks = (tasks) => {
  notStartedTasks.value = tasks.filter(task => task.status === 1)
  inProgressTasks.value = tasks.filter(task => task.status === 2)
  completedTasks.value = tasks.filter(task => task.status === 3)
  overdueTasks.value = tasks.filter(task => task.status === 4)
  canceledTasks.value = tasks.filter(task => task.status === 5)
}

// 处理任务拖拽变化
const handleTaskChange = async () => {
  // 合并所有任务
  const allTasks = [
    ...notStartedTasks.value.map(task => ({ ...task, status: 1 })),
    ...inProgressTasks.value.map(task => ({ ...task, status: 2 })),
    ...completedTasks.value.map(task => ({ ...task, status: 3 })),
    ...overdueTasks.value.map(task => ({ ...task, status: 4 })),
    ...canceledTasks.value.map(task => ({ ...task, status: 5 }))
  ]
  
  // 更新任务状态
  try {
    // 这里可以批量更新，为了简化，暂时单个更新
    for (const task of allTasks) {
      await request.patch(`/project/tasks/${task.id}/`, { status: task.status })
    }
    ElMessage.success('任务状态更新成功')
  } catch (error) {
    ElMessage.error('任务状态更新失败：' + error.message)
    // 重新加载数据，恢复到之前的状态
    loadKanbanData()
  }
}

// 处理任务点击
const handleTaskClick = (task) => {
  $router.push(`/tasks/${task.id}`)
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

// 生命周期钩子
onMounted(async () => {
  await loadProjects()
})

// 监听选中项目变化
watch(selectedProject, (newVal) => {
  if (newVal) {
    loadKanbanData()
  }
})
</script>

<style scoped>
.kanban-view-container {
  padding: 20px;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.kanban-container {
  height: 700px;
  margin-top: 20px;
}

.kanban-scroll-wrap {
  height: 100%;
}

.kanban-board {
  display: flex;
  gap: 20px;
  padding: 20px 0;
  height: calc(100% - 40px);
}

.kanban-column {
  width: 300px;
  background-color: #f5f5f5;
  border-radius: 8px;
  display: flex;
  flex-direction: column;
  height: 100%;
}

.column-header {
  padding: 16px;
  border-radius: 8px 8px 0 0;
  color: white;
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.column-header h3 {
  margin: 0;
  font-size: 16px;
  font-weight: 600;
}

.status-not-started {
  background-color: #1890ff;
}

.status-in-progress {
  background-color: #faad14;
}

.status-completed {
  background-color: #52c41a;
}

.status-overdue {
  background-color: #ff4d4f;
}

.status-canceled {
  background-color: #d9d9d9;
}

.task-count {
  background-color: rgba(255, 255, 255, 0.2);
  border-radius: 12px;
  padding: 2px 8px;
  font-size: 12px;
  font-weight: 600;
}

.column-content {
  flex: 1;
  padding: 12px;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.task-card {
  background-color: white;
  border-radius: 8px;
  padding: 16px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
  cursor: pointer;
  transition: all 0.3s ease;
}

.task-card:hover {
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
  transform: translateY(-2px);
}

.task-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  margin-bottom: 12px;
}

.task-title {
  margin: 0;
  font-size: 14px;
  font-weight: 600;
  color: #333;
  flex: 1;
  margin-right: 8px;
  overflow: hidden;
  text-overflow: ellipsis;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
}

.task-body {
  margin-bottom: 12px;
}

.task-desc {
  margin: 0;
  font-size: 12px;
  color: #666;
  line-height: 1.4;
  overflow: hidden;
  text-overflow: ellipsis;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
}

.task-footer {
  display: flex;
  justify-content: space-between;
  align-items: center;
  font-size: 12px;
}

.task-assignee {
  color: #999;
  font-weight: 500;
}

/* 滚动条样式 */
.column-content::-webkit-scrollbar {
  width: 6px;
}

.column-content::-webkit-scrollbar-track {
  background: #f1f1f1;
  border-radius: 3px;
}

.column-content::-webkit-scrollbar-thumb {
  background: #ccc;
  border-radius: 3px;
}

.column-content::-webkit-scrollbar-thumb:hover {
  background: #aaa;
}
</style>