<template>
  <a-card class="library-panel">
    <template #title>步骤组件库</template>
    <template #extra>
      <a-space size="small">
        <a-button size="mini" @click="emit('open-import-dialog')">导入组件包</a-button>
        <a-button size="mini" type="outline" @click="emit('open-export-dialog')">导出组件包</a-button>
      </a-space>
    </template>

    <a-input-search
      v-model="componentSearchModel"
      class="component-search"
      allow-clear
      placeholder="搜索组件名称或类型"
    />
    <a-tabs v-model:active-key="paletteTabModel" lazy-load>
      <a-tab-pane key="base" title="基础组件">
        <div v-if="filteredComponents.length" class="component-grid">
          <div
            v-for="item in filteredComponents"
            :key="item.id"
            class="component-item"
            @click="emit('append-base', item)"
          >
            <div class="component-copy">
              <span class="component-name">{{ item.name }}</span>
              <span class="component-meta">{{ item.type }}</span>
            </div>
            <span class="component-tag">{{ item.category || 'base' }}</span>
          </div>
        </div>
        <a-empty v-else description="没有匹配的基础组件" />
      </a-tab-pane>

      <a-tab-pane key="custom" title="自定义组件">
        <div v-if="filteredCustomComponents.length" class="component-grid">
          <div
            v-for="item in filteredCustomComponents"
            :key="item.id"
            class="component-item component-item-custom"
            @click="emit('append-custom', item)"
          >
            <div class="component-copy">
              <span class="component-name">{{ item.name }}</span>
              <span class="component-meta">{{ item.type }} · {{ item.steps?.length || 0 }} 个子步骤</span>
            </div>
            <div class="component-actions">
              <a-button type="text" size="mini" @click.stop="emit('edit-custom', item)">编辑</a-button>
              <a-button type="text" size="mini" status="danger" @click.stop="emit('delete-custom', item)">
                删除
              </a-button>
            </div>
          </div>
        </div>
        <a-empty v-else description="暂无自定义组件" />
      </a-tab-pane>
    </a-tabs>
  </a-card>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import type { AppComponent, AppCustomComponent } from '../../types'

interface Props {
  componentSearch: string
  paletteTab: 'base' | 'custom'
  filteredComponents: AppComponent[]
  filteredCustomComponents: AppCustomComponent[]
}

const props = defineProps<Props>()

const emit = defineEmits<{
  'update:componentSearch': [value: string]
  'update:paletteTab': [value: 'base' | 'custom']
  'open-import-dialog': []
  'open-export-dialog': []
  'append-base': [component: AppComponent]
  'append-custom': [component: AppCustomComponent]
  'edit-custom': [component: AppCustomComponent]
  'delete-custom': [component: AppCustomComponent]
}>()

const componentSearchModel = computed({
  get: () => props.componentSearch,
  set: value => emit('update:componentSearch', String(value || '')),
})

const paletteTabModel = computed({
  get: () => props.paletteTab,
  set: value => emit('update:paletteTab', value),
})
</script>

<style scoped>
.library-panel {
  min-height: 560px;
  border-radius: 16px;
  border: 1px solid var(--theme-card-border);
  background: var(--theme-card-bg);
  box-shadow: var(--theme-card-shadow);
}

.component-search {
  margin-bottom: 14px;
}

.component-grid {
  display: grid;
  gap: 10px;
}

.component-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 12px 14px;
  border-radius: 14px;
  border: 1px solid rgba(var(--theme-accent-rgb), 0.16);
  background: rgba(var(--theme-accent-rgb), 0.06);
  cursor: pointer;
  transition:
    transform 0.18s ease,
    border-color 0.18s ease,
    background 0.18s ease;
}

.component-item:hover {
  transform: translateY(-1px);
  border-color: rgba(var(--theme-accent-rgb), 0.34);
  background: rgba(var(--theme-accent-rgb), 0.09);
}

.component-item-custom {
  background: rgba(var(--theme-accent-rgb), 0.1);
}

.component-copy {
  display: flex;
  flex-direction: column;
  gap: 4px;
  min-width: 0;
}

.component-name {
  font-weight: 700;
  color: var(--theme-text);
}

.component-meta,
.component-tag {
  font-size: 12px;
  color: var(--theme-text-secondary);
}

.component-actions {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  flex-shrink: 0;
}
</style>
