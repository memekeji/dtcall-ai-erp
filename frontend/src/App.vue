<template>
  <div class="app-container">
    <el-container>
      <el-aside width="200px" class="app-aside">
        <div class="logo">
          <h2>项目管理系统</h2>
        </div>
        <el-menu
          :default-active="activeMenu"
          class="el-menu-vertical-demo"
          router
          background-color="#545c64"
          text-color="#fff"
          active-text-color="#ffd04b"
          :collapse-transition="false"
        >
          <el-menu-item index="/projects">
            <template #title>
              <el-icon><menu /></el-icon>
              <span>项目列表</span>
            </template>
          </el-menu-item>
          <el-menu-item index="/projects/create">
            <template #title>
              <el-icon><plus /></el-icon>
              <span>新建项目</span>
            </template>
          </el-menu-item>
          <el-menu-item index="/tasks">
            <template #title>
              <el-icon><list /></el-icon>
              <span>任务管理</span>
            </template>
          </el-menu-item>
          <el-menu-item index="/work-hours">
            <template #title>
              <el-icon><timer /></el-icon>
              <span>工时管理</span>
            </template>
          </el-menu-item>
          <el-menu-item index="/documents">
            <template #title>
              <el-icon><document /></el-icon>
              <span>文档管理</span>
            </template>
          </el-menu-item>
          <el-menu-item index="/gantt">
            <template #title>
              <el-icon><calendar /></el-icon>
              <span>甘特图</span>
            </template>
          </el-menu-item>
          <el-menu-item index="/kanban">
            <template #title>
              <el-icon><grid /></el-icon>
              <span>任务看板</span>
            </template>
          </el-menu-item>
          <el-menu-item index="/reports">
            <template #title>
              <el-icon><data-analysis /></el-icon>
              <span>报表统计</span>
            </template>
          </el-menu-item>
        </el-menu>
      </el-aside>
      <el-container>
        <el-header class="app-header">
          <div class="header-right">
            <el-dropdown>
              <span class="user-info">
                <el-avatar :size="32" src="https://cube.elemecdn.com/0/88/03b0d39583f48206768a7534e55bcpng.png"></el-avatar>
                <span class="username">管理员</span>
              </span>
              <template #dropdown>
                <el-dropdown-menu>
                  <el-dropdown-item>个人中心</el-dropdown-item>
                  <el-dropdown-item>退出登录</el-dropdown-item>
                </el-dropdown-menu>
              </template>
            </el-dropdown>
          </div>
        </el-header>
        <el-main class="app-main">
          <router-view v-slot="{ Component }">
            <transition name="fade" mode="out-in">
              <component :is="Component" />
            </transition>
          </router-view>
        </el-main>
      </el-container>
    </el-container>
  </div>
</template>

<script setup>
import { ref, computed } from 'vue'
import { useRoute } from 'vue-router'

const route = useRoute()
const activeMenu = computed(() => route.path)
</script>

<style scoped>
.app-container {
  width: 100%;
  height: 100vh;
  overflow: hidden;
}

.app-aside {
  background-color: #545c64;
  height: 100%;
}

.logo {
  text-align: center;
  padding: 20px 0;
  border-bottom: 1px solid #666;
}

.logo h2 {
  color: #fff;
  font-size: 18px;
  margin: 0;
}

.app-header {
  background-color: #fff;
  border-bottom: 1px solid #e6e6e6;
  display: flex;
  justify-content: flex-end;
  align-items: center;
  padding: 0 20px;
}

.header-right {
  display: flex;
  align-items: center;
}

.user-info {
  display: flex;
  align-items: center;
  cursor: pointer;
}

.username {
  margin-left: 10px;
}

.app-main {
  padding: 20px;
  overflow-y: auto;
}

.fade-enter-active,
.fade-leave-active {
  transition: opacity 0.3s ease;
}

.fade-enter-from,
.fade-leave-to {
  opacity: 0;
}
</style>
