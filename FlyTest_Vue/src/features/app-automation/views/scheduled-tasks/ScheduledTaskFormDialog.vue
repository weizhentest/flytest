<template>
  <a-modal
    v-model:visible="visibleModel"
    :title="form.id ? '编辑定时任务' : '新建定时任务'"
    width="820px"
    @before-ok="done => emit('before-ok', done)"
  >
    <a-form :model="form" layout="vertical">
      <a-row :gutter="12">
        <a-col :span="12">
          <a-form-item field="name" label="任务名称">
            <a-input v-model="form.name" placeholder="请输入任务名称" />
          </a-form-item>
        </a-col>
        <a-col :span="12">
          <a-form-item field="status" label="初始状态">
            <a-select v-model="form.status">
              <a-option value="ACTIVE">ACTIVE</a-option>
              <a-option value="PAUSED">PAUSED</a-option>
            </a-select>
          </a-form-item>
        </a-col>
      </a-row>

      <a-form-item field="description" label="任务描述">
        <a-textarea
          v-model="form.description"
          :auto-size="{ minRows: 3, maxRows: 5 }"
          placeholder="描述任务执行目标、前置条件或业务说明"
        />
      </a-form-item>

      <a-row :gutter="12">
        <a-col :span="12">
          <a-form-item field="task_type" label="任务类型">
            <a-radio-group v-model="form.task_type" type="button">
              <a-radio value="TEST_SUITE">测试套件</a-radio>
              <a-radio value="TEST_CASE">测试用例</a-radio>
            </a-radio-group>
          </a-form-item>
        </a-col>
        <a-col :span="12">
          <a-form-item field="device_id" label="执行设备">
            <a-select v-model="form.device_id" allow-search placeholder="请选择执行设备">
              <a-option v-for="item in devices" :key="item.id" :value="item.id">
                {{ item.name || item.device_id }}
              </a-option>
            </a-select>
          </a-form-item>
        </a-col>
      </a-row>

      <a-row :gutter="12">
        <a-col :span="12">
          <a-form-item v-if="form.task_type === 'TEST_SUITE'" field="test_suite_id" label="测试套件">
            <a-select v-model="form.test_suite_id" allow-search allow-clear placeholder="请选择测试套件">
              <a-option v-for="item in suites" :key="item.id" :value="item.id">
                {{ item.name }}
              </a-option>
            </a-select>
          </a-form-item>
          <a-form-item v-else field="test_case_id" label="测试用例">
            <a-select v-model="form.test_case_id" allow-search allow-clear placeholder="请选择测试用例">
              <a-option v-for="item in testCases" :key="item.id" :value="item.id">
                {{ item.name }}
              </a-option>
            </a-select>
          </a-form-item>
        </a-col>
        <a-col :span="12">
          <a-form-item field="package_id" label="应用包">
            <a-select v-model="form.package_id" allow-search allow-clear placeholder="可选，用于指定运行包">
              <a-option v-for="item in packages" :key="item.id" :value="item.id">
                {{ item.name }}
              </a-option>
            </a-select>
          </a-form-item>
        </a-col>
      </a-row>

      <a-form-item field="trigger_type" label="触发方式">
        <a-radio-group v-model="form.trigger_type" type="button">
          <a-radio value="CRON">CRON</a-radio>
          <a-radio value="INTERVAL">INTERVAL</a-radio>
          <a-radio value="ONCE">ONCE</a-radio>
        </a-radio-group>
      </a-form-item>

      <a-row :gutter="12">
        <a-col :span="12">
          <a-form-item v-if="form.trigger_type === 'CRON'" field="cron_expression" label="Cron 表达式">
            <a-input v-model="form.cron_expression" placeholder="例如：0 0 * * *" />
          </a-form-item>
          <a-form-item v-else-if="form.trigger_type === 'INTERVAL'" field="interval_seconds" label="间隔秒数">
            <a-input-number v-model="form.interval_seconds" :min="60" :step="60" />
          </a-form-item>
          <a-form-item v-else field="execute_at" label="执行时间">
            <a-date-picker
              v-model="form.execute_at"
              show-time
              format="YYYY-MM-DD HH:mm:ss"
              value-format="YYYY-MM-DDTHH:mm:ssZ"
              placeholder="请选择一次性执行时间"
              :show-confirm-btn="false"
              style="width: 100%"
            />
          </a-form-item>
        </a-col>
        <a-col :span="12">
          <div class="helper-card">
            <strong>调度说明</strong>
            <span v-if="form.trigger_type === 'CRON'">
              常用示例：`0 0 * * *` 每天零点执行，`0 */2 * * *` 每两小时执行一次。
            </span>
            <span v-else-if="form.trigger_type === 'INTERVAL'">
              间隔任务会以秒为单位重复执行，建议不要低于 60 秒。
            </span>
            <span v-else>
              一次性任务会在执行结束后自动结算，成功进入 `COMPLETED`，失败进入 `FAILED`，且不会继续调度。
            </span>
          </div>
        </a-col>
      </a-row>

      <a-divider style="margin: 4px 0 12px">通知设置</a-divider>

      <a-row :gutter="12">
        <a-col :span="8">
          <a-form-item field="notify_on_success" label="成功通知">
            <a-switch v-model="form.notify_on_success" />
          </a-form-item>
        </a-col>
        <a-col :span="8">
          <a-form-item field="notify_on_failure" label="失败通知">
            <a-switch v-model="form.notify_on_failure" />
          </a-form-item>
        </a-col>
        <a-col :span="8">
          <a-form-item field="notification_type" label="通知类型">
            <a-select
              v-model="form.notification_type"
              allow-clear
              :disabled="!notificationsEnabled"
              placeholder="请选择通知类型"
            >
              <a-option value="email">email</a-option>
              <a-option value="webhook">webhook</a-option>
              <a-option value="both">both</a-option>
            </a-select>
          </a-form-item>
        </a-col>
      </a-row>

      <a-form-item field="notify_emails_text" label="通知邮箱">
        <a-input
          v-model="notifyEmailsTextModel"
          :disabled="!needsEmailRecipients"
          placeholder="多个邮箱可用逗号、分号或换行分隔"
        />
      </a-form-item>
    </a-form>
  </a-modal>
</template>

<script setup lang="ts">
import type {
  AppDevice,
  AppPackage,
  AppTestCase,
  AppTestSuite,
} from '../../types'

interface ScheduledTaskFormModel {
  id: number
  name: string
  description: string
  task_type: string
  trigger_type: string
  cron_expression: string
  interval_seconds: number
  execute_at: string
  device_id: number | undefined
  package_id: number | undefined
  test_suite_id: number | undefined
  test_case_id: number | undefined
  notify_on_success: boolean
  notify_on_failure: boolean
  notification_type: string
  status: string
}

interface Props {
  form: ScheduledTaskFormModel
  devices: AppDevice[]
  suites: AppTestSuite[]
  testCases: AppTestCase[]
  packages: AppPackage[]
  notificationsEnabled: boolean
  needsEmailRecipients: boolean
}

defineProps<Props>()

const visibleModel = defineModel<boolean>('visible', { required: true })
const notifyEmailsTextModel = defineModel<string>('notifyEmailsText', { required: true })

const emit = defineEmits<{
  'before-ok': [done: (closed: boolean) => void]
}>()
</script>

<style scoped>
.helper-card {
  display: flex;
  flex-direction: column;
  gap: 10px;
  min-height: 108px;
  padding: 16px;
  border-radius: 14px;
  background: rgba(var(--theme-accent-rgb), 0.06);
  border: 1px solid rgba(var(--theme-accent-rgb), 0.14);
  color: var(--theme-text-secondary);
}

.helper-card strong {
  color: var(--theme-text);
}
</style>
