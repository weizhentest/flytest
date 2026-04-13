<template>
  <div class="page-header">
    <div class="header-copy">
      <h3>元素管理</h3>
      <p>统一维护图片、坐标、区域等元素资源，供 APP 场景编排、步骤补全和执行复用。</p>
    </div>
    <a-space wrap class="header-actions">
      <a-input-search
        v-model="searchModel"
        placeholder="搜索元素名称或定位值"
        allow-clear
        @search="emit('search')"
      />
      <a-select
        v-model="typeFilterModel"
        allow-clear
        placeholder="元素类型"
        style="width: 140px"
        @change="emit('type-change')"
      >
        <a-option value="image">图片</a-option>
        <a-option value="pos">坐标</a-option>
        <a-option value="region">区域</a-option>
      </a-select>
      <a-button :loading="loading" @click="emit('refresh')">刷新</a-button>
      <a-button @click="emit('open-capture')">从设备截图创建</a-button>
      <a-button type="primary" @click="emit('open-create')">新增元素</a-button>
    </a-space>
  </div>
</template>

<script setup lang="ts">
interface Props {
  loading: boolean
}

defineProps<Props>()

const searchModel = defineModel<string>('search', { required: true })
const typeFilterModel = defineModel<string | undefined>('typeFilter', { required: true })

const emit = defineEmits<{
  search: []
  'type-change': []
  refresh: []
  'open-capture': []
  'open-create': []
}>()
</script>

<style scoped>
.page-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
}

.header-copy h3 {
  margin: 0;
  color: var(--theme-text);
}

.header-copy p {
  margin: 6px 0 0;
  color: var(--theme-text-secondary);
}

.header-actions {
  justify-content: flex-end;
}

@media (max-width: 960px) {
  .page-header {
    flex-direction: column;
    align-items: stretch;
  }

  .header-actions {
    justify-content: flex-start;
  }
}
</style>
