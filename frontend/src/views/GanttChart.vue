<template>
  <div class="gantt-chart-container">
    <el-card>
      <template #header>
        <div class="card-header">
          <h2>项目甘特图</h2>
          <el-select v-model="selectedProject" placeholder="选择项目" @change="loadGanttData">
            <el-option
              v-for="project in projects"
              :key="project.id"
              :label="project.name"
              :value="project.id"
            />
          </el-select>
        </div>
      </template>
      
      <!-- 甘特图容器 -->
      <div id="ganttChart" ref="ganttChartRef" style="width: 100%; height: 600px;"></div>
    </el-card>
  </div>
</template>

<script setup>
import { ref, onMounted, onUnmounted, watch } from 'vue'
import { ElMessage, ElLoading } from 'element-plus'
import * as echarts from 'echarts'
import request from '../utils/request'
import dayjs from 'dayjs'

// 组件引用
const ganttChartRef = ref(null)
let ganttChart = null

// 项目列表和选中项目
const projects = ref([])
const selectedProject = ref('')

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

// 加载甘特图数据
const loadGanttData = async () => {
  if (!selectedProject.value) return
  
  const loading = ElLoading.service({ target: '#ganttChart', text: '加载甘特图数据中...' })
  try {
    // 获取项目阶段
    const stepsResponse = await request.get('/project/project-steps/', { params: { project_id: selectedProject.value } })
    const steps = stepsResponse.results
    
    // 获取项目任务
    const tasksResponse = await request.get('/project/tasks/', { params: { project_id: selectedProject.value } })
    const tasks = tasksResponse.results
    
    // 构建甘特图数据
    const ganttData = buildGanttData(steps, tasks)
    
    // 渲染甘特图
    renderGanttChart(ganttData)
  } catch (error) {
    ElMessage.error('获取甘特图数据失败：' + error.message)
  } finally {
    loading.close()
  }
}

// 构建甘特图数据
const buildGanttData = (steps, tasks) => {
  const categories = steps.map(step => step.name)
  const data = []
  
  // 为每个阶段添加任务
  steps.forEach((step, stepIndex) => {
    const stepTasks = tasks.filter(task => task.step_id === step.id)
    
    stepTasks.forEach((task, taskIndex) => {
      if (task.start_date && task.end_date) {
        const start = dayjs(task.start_date)
        const end = dayjs(task.end_date)
        const duration = end.diff(start, 'day') + 1
        
        data.push({
          name: task.title,
          category: step.name,
          value: [
            stepIndex,
            start.valueOf(),
            end.valueOf(),
            duration,
            task.id,
            task.status_display,
            task.progress
          ],
          itemStyle: {
            color: getTaskColor(task.status, task.progress)
          }
        })
      }
    })
  })
  
  return { categories, data }
}

// 获取任务颜色
const getTaskColor = (status, progress) => {
  if (status === 3) return '#52c41a' // 已完成 - 绿色
  if (status === 5) return '#d9d9d9' // 已取消 - 灰色
  if (status === 4) return '#ff4d4f' // 已延期 - 红色
  return '#1890ff' // 进行中/未开始 - 蓝色
}

// 渲染甘特图
const renderGanttChart = (ganttData) => {
  if (!ganttChartRef.value) return
  
  // 初始化图表
  if (!ganttChart) {
    ganttChart = echarts.init(ganttChartRef.value)
  }
  
  // 图表配置
  const option = {
    tooltip: {
      formatter: function(params) {
        const task = params.data
        const start = dayjs(task.value[1]).format('YYYY-MM-DD')
        const end = dayjs(task.value[2]).format('YYYY-MM-DD')
        return `
          <div>
            <h4>${task.name}</h4>
            <p>阶段：${task.category}</p>
            <p>时间：${start} 至 ${end}</p>
            <p>状态：${task.value[5]}</p>
            <p>进度：${task.value[6]}%</p>
          </div>
        `
      }
    },
    grid: {
      left: '15%',
      right: '5%',
      top: '10%',
      bottom: '10%'
    },
    xAxis: {
      type: 'time',
      axisLabel: {
        formatter: '{yyyy}-{MM}-{dd}'
      }
    },
    yAxis: {
      type: 'category',
      data: ganttData.categories,
      axisLabel: {
        interval: 0
      }
    },
    series: [
      {
        type: 'bar',
        name: '任务',
        data: ganttData.data,
        coordinateSystem: 'cartesian2d',
        barWidth: 20,
        itemStyle: {
          borderRadius: [4, 4, 0, 0]
        },
        encode: {
          x: [1, 2],
          y: 0
        },
        label: {
          show: true,
          position: 'insideRight',
          formatter: '{@[6]}%'
        },
        emphasis: {
          focus: 'series'
        }
      }
    ]
  }
  
  // 设置图表配置
  ganttChart.setOption(option)
}

// 窗口大小变化时重绘图表
const handleResize = () => {
  if (ganttChart) {
    ganttChart.resize()
  }
}

// 生命周期钩子
onMounted(async () => {
  await loadProjects()
  window.addEventListener('resize', handleResize)
})

onUnmounted(() => {
  if (ganttChart) {
    ganttChart.dispose()
    ganttChart = null
  }
  window.removeEventListener('resize', handleResize)
})

// 监听选中项目变化
watch(selectedProject, (newVal) => {
  if (newVal) {
    loadGanttData()
  }
})
</script>

<style scoped>
.gantt-chart-container {
  padding: 20px;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
</style>