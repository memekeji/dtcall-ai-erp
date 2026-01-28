import { createRouter, createWebHistory } from 'vue-router'

const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes: [
    {
      path: '/',
      redirect: '/projects'
    },
    {
      path: '/projects',
      name: 'projects',
      component: () => import('../views/ProjectList.vue'),
      meta: {
        title: '项目列表'
      }
    },
    {
      path: '/projects/create',
      name: 'createProject',
      component: () => import('../views/ProjectForm.vue'),
      meta: {
        title: '新建项目'
      }
    },
    {
      path: '/projects/:id',
      name: 'projectDetail',
      component: () => import('../views/ProjectDetail.vue'),
      meta: {
        title: '项目详情'
      }
    },
    {
      path: '/projects/:id/edit',
      name: 'editProject',
      component: () => import('../views/ProjectForm.vue'),
      meta: {
        title: '编辑项目'
      }
    },
    {
      path: '/tasks',
      name: 'tasks',
      component: () => import('../views/TaskList.vue'),
      meta: {
        title: '任务管理'
      }
    },
    {
      path: '/tasks/create',
      name: 'createTask',
      component: () => import('../views/TaskForm.vue'),
      meta: {
        title: '新建任务'
      }
    },
    {
      path: '/tasks/:id/edit',
      name: 'editTask',
      component: () => import('../views/TaskForm.vue'),
      meta: {
        title: '编辑任务'
      }
    },
    {
      path: '/work-hours',
      name: 'workHours',
      component: () => import('../views/WorkHourList.vue'),
      meta: {
        title: '工时管理'
      }
    },
    {
      path: '/work-hours/create',
      name: 'createWorkHour',
      component: () => import('../views/WorkHourForm.vue'),
      meta: {
        title: '新建工时记录'
      }
    },
    {
      path: '/work-hours/:id/edit',
      name: 'editWorkHour',
      component: () => import('../views/WorkHourForm.vue'),
      meta: {
        title: '编辑工时记录'
      }
    },
    {
      path: '/documents',
      name: 'documents',
      component: () => import('../views/DocumentList.vue'),
      meta: {
        title: '文档管理'
      }
    },
    {
      path: '/documents/create',
      name: 'createDocument',
      component: () => import('../views/DocumentForm.vue'),
      meta: {
        title: '上传文档'
      }
    },
    {
      path: '/documents/:id/edit',
      name: 'editDocument',
      component: () => import('../views/DocumentForm.vue'),
      meta: {
        title: '编辑文档'
      }
    },
    {
      path: '/reports',
      name: 'reports',
      component: () => import('../views/Reports.vue'),
      meta: {
        title: '报表统计'
      }
    },
    {
      path: '/gantt',
      name: 'gantt',
      component: () => import('../views/GanttChart.vue'),
      meta: {
        title: '项目甘特图'
      }
    },
    {
      path: '/kanban',
      name: 'kanban',
      component: () => import('../views/KanbanView.vue'),
      meta: {
        title: '任务看板'
      }
    }
  ]
})

// 路由守卫，设置页面标题
router.beforeEach((to, from, next) => {
  if (to.meta.title) {
    document.title = to.meta.title
  }
  next()
})

export default router
