<template>
  <a-modal
    v-model:visible="modalVisible"
    title="测试套件详情"
    width="760px"
    :footer="false"
    @cancel="handleClose"
  >
    <a-spin :loading="loading" style="width: 100%">
      <div v-if="suiteDetail" class="suite-detail-content">
        <a-descriptions :column="2" bordered>
          <a-descriptions-item label="套件名称">
            {{ suiteDetail.name }}
          </a-descriptions-item>
          <a-descriptions-item label="套件 ID">
            {{ suiteDetail.id }}
          </a-descriptions-item>
          <a-descriptions-item label="创建人">
            {{ suiteDetail.creator_detail?.username || '-' }}
          </a-descriptions-item>
          <a-descriptions-item label="测试用例数量">
            <a-tag color="blue">{{ suiteDetail.testcase_count }} 条</a-tag>
          </a-descriptions-item>
          <a-descriptions-item label="并发执行数">
            {{ suiteDetail.max_concurrent_tasks || 1 }}
          </a-descriptions-item>
          <a-descriptions-item label="创建时间">
            {{ formatDate(suiteDetail.created_at) }}
          </a-descriptions-item>
          <a-descriptions-item label="更新时间">
            {{ formatDate(suiteDetail.updated_at) }}
          </a-descriptions-item>
          <a-descriptions-item label="套件描述" :span="2">
            {{ suiteDetail.description || '暂无描述' }}
          </a-descriptions-item>
        </a-descriptions>

        <a-alert class="suite-alert" type="info" show-icon>
          测试套件中的测试用例请在测试用例 Tab 中通过“分配”进行维护。
        </a-alert>
      </div>
    </a-spin>
  </a-modal>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue';
import { Message } from '@arco-design/web-vue';
import { getTestSuiteDetail, type TestSuite } from '@/services/testSuiteService';
import { formatDate } from '@/utils/formatters';

interface Props {
  visible: boolean;
  currentProjectId: number | null;
  suiteId: number | null;
}

const props = withDefaults(defineProps<Props>(), {
  visible: false,
  currentProjectId: null,
  suiteId: null,
});

const emit = defineEmits<{
  (e: 'update:visible', visible: boolean): void;
}>();

const loading = ref(false);
const suiteDetail = ref<TestSuite | null>(null);

const modalVisible = computed({
  get: () => props.visible,
  set: (value) => emit('update:visible', value),
});

const fetchSuiteDetail = async () => {
  if (!props.currentProjectId || !props.suiteId) {
    return;
  }

  loading.value = true;
  try {
    const response = await getTestSuiteDetail(props.currentProjectId, props.suiteId);
    if (response.success && response.data) {
      suiteDetail.value = response.data;
      return;
    }

    Message.error(response.error || '获取测试套件详情失败');
    handleClose();
  } catch (error) {
    console.error('获取测试套件详情失败:', error);
    Message.error('获取测试套件详情失败');
    handleClose();
  } finally {
    loading.value = false;
  }
};

const handleClose = () => {
  suiteDetail.value = null;
  modalVisible.value = false;
};

watch(
  () => props.visible,
  (visible) => {
    if (visible) {
      void fetchSuiteDetail();
    } else {
      suiteDetail.value = null;
    }
  }
);
</script>

<style scoped>
.suite-detail-content {
  padding-top: 8px;
}

.suite-alert {
  margin-top: 16px;
}
</style>
