<template>
  <div class="skills-management-view">
    <div class="page-header">
      <h2>Skills 管理</h2>
      <p class="page-description">
        管理项目的 Agent Skills。Skills 是模块化的能力扩展，包含指令和可执行脚本。
      </p>
    </div>

    <div v-if="currentProjectId" class="skills-container">
      <SkillManager :project-id="currentProjectId" :key="currentProjectId" />
    </div>
    <div v-else class="empty-state">
      <icon-apps style="font-size: 64px; color: #c0c4cc" />
      <p>请先在导航栏选择一个项目</p>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { SkillManager } from '@/features/skills'
import { useProjectStore } from '@/store/projectStore'

const projectStore = useProjectStore()
const currentProjectId = computed(() => projectStore.currentProjectId)
</script>

<style scoped>
.skills-management-view {
  padding: 24px;
}

.page-header {
  margin-bottom: 24px;
}

.page-header h2 {
  margin: 0 0 8px 0;
}

.page-description {
  color: var(--color-text-2);
  margin: 0;
}

.skills-container {
  background: var(--color-bg-2);
  border-radius: 8px;
  min-height: 400px;
}

.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 80px 0;
  color: var(--color-text-3);
}
</style>
