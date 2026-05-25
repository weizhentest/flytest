<template>
  <div class="personal-center">
    <div class="page-header">
      <h2>个人中心</h2>
      <p>维护系统用户名、姓名、登录手机号、联系邮箱与账号安全信息。</p>
    </div>

    <div class="center-layout">
      <aside class="section-sidebar">
        <a-menu
          :selected-keys="[activeSection]"
          mode="vertical"
          @menu-item-click="handleSectionChange"
        >
          <a-menu-item key="profile">个人资料</a-menu-item>
          <a-menu-item key="password">修改密码</a-menu-item>
        </a-menu>
      </aside>

      <section class="section-content">
        <a-card v-if="activeSection === 'profile'" title="个人资料" class="panel-card">
          <div class="form-shell">
            <div class="avatar-editor">
              <div class="profile-avatar-preview" :title="avatarLabel">
                <img
                  v-if="profileForm.avatar_url"
                  :src="profileForm.avatar_url"
                  :alt="avatarLabel"
                  draggable="false"
                />
                <span v-else>{{ avatarInitial }}</span>
              </div>
              <div class="avatar-actions">
                <a-space>
                  <a-button size="small" :loading="avatarLoading" @click="triggerAvatarPicker">
                    上传头像
                  </a-button>
                  <a-button
                    v-if="profileForm.avatar_url"
                    size="small"
                    status="danger"
                    :loading="avatarLoading"
                    @click="handleRemoveAvatar"
                  >
                    移除头像
                  </a-button>
                </a-space>
                <div class="avatar-tip">支持 JPG、PNG、WEBP、GIF，最大 5MB。</div>
                <input
                  ref="avatarInputRef"
                  class="avatar-input"
                  type="file"
                  accept="image/jpeg,image/png,image/webp,image/gif"
                  @change="handleAvatarFileChange"
                />
              </div>
            </div>

            <template v-if="!isEditingProfile">
              <div class="profile-readonly">
                <div class="readonly-item">
                  <span class="readonly-label">系统用户名</span>
                  <div class="readonly-value-group">
                    <span class="readonly-value">{{ profileForm.username || '-' }}</span>
                    <span class="readonly-hint">支持系统用户名+密码登录</span>
                  </div>
                </div>
                <div class="readonly-item">
                  <span class="readonly-label">姓名</span>
                  <span class="readonly-value">{{ profileForm.real_name || '-' }}</span>
                </div>
                <div class="readonly-item">
                  <span class="readonly-label">联系邮箱（选填）</span>
                  <span class="readonly-value">{{ profileForm.email || '-' }}</span>
                </div>
                <div class="readonly-item">
                  <span class="readonly-label">登录手机号</span>
                  <span class="readonly-value">{{ profileForm.phone_number || '-' }}</span>
                </div>
                <div class="readonly-item">
                  <span class="readonly-label">所属组织</span>
                  <div v-if="organizations.length" class="organization-list">
                    <a-tag v-for="group in organizations" :key="group" color="arcoblue">
                      {{ group }}
                    </a-tag>
                  </div>
                  <span v-else class="readonly-value">当前未加入任何组织</span>
                </div>

                <div class="action-row">
                  <a-button type="primary" class="action-btn" @click="isEditingProfile = true">修改资料</a-button>
                </div>
              </div>
            </template>

            <a-form v-else :model="profileForm" layout="vertical" @submit.prevent>
              <a-form-item label="系统用户名">
                <a-input v-model="profileForm.username" placeholder="请输入系统用户名" />
                <div class="field-tip">
                  <span>至少 3 位，仅支持字母或字母+数字组合，且不能为纯数字。</span>
                  <span v-if="!profileForm.can_change_username && profileForm.username_next_editable_at">
                    下次可修改时间：{{ formatDateTime(profileForm.username_next_editable_at) }}
                  </span>
                  <span v-else>系统用户名每 30 天最多修改一次。</span>
                </div>
              </a-form-item>

              <a-form-item label="姓名">
                <a-input v-model="profileForm.real_name" placeholder="请输入姓名（仅支持中文）" />
                <div class="field-tip">
                  <span>姓名仅支持 2 到 20 位中文，且不能与其他用户重复。</span>
                </div>
              </a-form-item>

              <a-form-item label="联系邮箱（选填）">
                <a-input v-model="profileForm.email" placeholder="请输入联系邮箱" />
              </a-form-item>

              <a-form-item label="登录手机号">
                <a-input v-model="profileForm.phone_number" placeholder="请输入11位手机号" />
              </a-form-item>

              <a-form-item label="所属组织">
                <div v-if="organizations.length" class="organization-list">
                  <a-tag v-for="group in organizations" :key="group" color="arcoblue">
                    {{ group }}
                  </a-tag>
                </div>
                <a-typography-text v-else type="secondary">
                  当前未加入任何组织
                </a-typography-text>
              </a-form-item>

              <div class="action-row">
                <a-space>
                  <a-button type="primary" class="action-btn" :loading="profileLoading" @click="handleSaveProfile">
                    保存资料
                  </a-button>
                  <a-button
                    @click="
                      isEditingProfile = false;
                      loadProfile();
                    "
                  >
                    取消修改
                  </a-button>
                </a-space>
              </div>
            </a-form>
          </div>
        </a-card>

        <a-card v-else title="修改密码" class="panel-card">
          <div class="form-shell password-shell">
            <a-form :model="passwordForm" layout="vertical" @submit.prevent>
              <a-form-item label="当前密码">
                <a-input-password
                  v-model="passwordForm.current_password"
                  placeholder="请输入当前密码"
                />
              </a-form-item>

              <a-form-item label="新密码">
                <a-input-password
                  v-model="passwordForm.new_password"
                  placeholder="请输入新密码"
                />
              </a-form-item>

              <a-form-item label="确认新密码">
                <a-input-password
                  v-model="passwordForm.confirm_password"
                  placeholder="请再次输入新密码"
                />
              </a-form-item>

              <a-button
                type="primary"
                status="warning"
                :loading="passwordLoading"
                @click="handleChangePassword"
              >
                修改密码
              </a-button>
            </a-form>
          </div>
        </a-card>
      </section>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { Message } from '@arco-design/web-vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '@/store/authStore'
import {
  changeCurrentPassword,
  deleteCurrentAvatar,
  getCurrentProfile,
  updateCurrentProfile,
  uploadCurrentAvatar,
  type ProfileData,
} from '@/services/profileService'

const router = useRouter()
const authStore = useAuthStore()

const activeSection = ref<'profile' | 'password'>('profile')
const isEditingProfile = ref(false)
const profileLoading = ref(false)
const avatarLoading = ref(false)
const passwordLoading = ref(false)
const avatarInputRef = ref<HTMLInputElement | null>(null)

const profileForm = reactive({
  username: '',
  username_changed_at: '',
  username_next_editable_at: '',
  can_change_username: true,
  email: '',
  real_name: '',
  phone_number: '',
  avatar_url: '',
})

const organizations = ref<string[]>([])

const passwordForm = reactive({
  current_password: '',
  new_password: '',
  confirm_password: '',
})

const CHINA_MOBILE_REGEX = /^1[3-9]\d{9}$/
const CHINESE_REAL_NAME_REGEX = /^[\u4e00-\u9fff·]{2,20}$/
const SYSTEM_USERNAME_REGEX = /^(?=.*[A-Za-z])[A-Za-z0-9]{3,}$/
const MAX_AVATAR_SIZE = 5 * 1024 * 1024
const AVATAR_TYPES = ['image/jpeg', 'image/png', 'image/webp', 'image/gif']

const avatarInitial = computed(() => {
  const label = profileForm.real_name || profileForm.username || authStore.currentUser?.real_name || authStore.currentUser?.username || 'U'
  return label.slice(0, 1).toUpperCase()
})

const avatarLabel = computed(() => `${profileForm.real_name || profileForm.username || '用户'}头像`)

const formatDateTime = (value?: string | null) => {
  if (!value) {
    return '-'
  }
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) {
    return value
  }
  return date.toLocaleString('zh-CN', { hour12: false })
}

const applyProfileData = (payload: Partial<ProfileData> | null | undefined) => {
  profileForm.username = payload?.username || authStore.currentUser?.username || ''
  profileForm.username_changed_at = payload?.username_changed_at || ''
  profileForm.username_next_editable_at = payload?.username_next_editable_at || ''
  profileForm.can_change_username = payload?.can_change_username ?? true
  profileForm.email = payload?.email || authStore.currentUser?.email || ''
  profileForm.real_name = payload?.real_name || authStore.currentUser?.real_name || ''
  profileForm.phone_number = payload?.phone_number || authStore.currentUser?.phone_number || ''
  profileForm.avatar_url = payload?.avatar_url ?? authStore.currentUser?.avatar_url ?? ''
  organizations.value = payload?.groups || authStore.currentUser?.groups || []
}

const patchCurrentUser = (payload: ProfileData) => {
  authStore.setCurrentUser({
    ...(authStore.currentUser || {}),
    ...payload,
  } as any)
}

const loadProfile = async () => {
  applyProfileData(authStore.currentUser as any)
  profileLoading.value = true
  try {
    const response = await getCurrentProfile()
    if (!response.success || !response.data) {
      Message.error(response.error || '获取个人资料失败')
      return
    }

    applyProfileData(response.data)
    patchCurrentUser(response.data)
  } finally {
    profileLoading.value = false
  }
}

const handleSectionChange = (key: string) => {
  activeSection.value = key as 'profile' | 'password'
}

const triggerAvatarPicker = () => {
  avatarInputRef.value?.click()
}

const handleAvatarFileChange = async (event: Event) => {
  const input = event.target as HTMLInputElement
  const file = input.files?.[0]
  input.value = ''

  if (!file) {
    return
  }
  if (!AVATAR_TYPES.includes(file.type)) {
    Message.warning('请选择 JPG、PNG、WEBP 或 GIF 图片')
    return
  }
  if (file.size > MAX_AVATAR_SIZE) {
    Message.warning('头像图片不能超过 5MB')
    return
  }

  avatarLoading.value = true
  try {
    const response = await uploadCurrentAvatar(file)
    if (!response.success || !response.data) {
      Message.error(response.error || '头像上传失败')
      return
    }

    applyProfileData(response.data)
    patchCurrentUser(response.data)
    Message.success('头像已更新')
  } finally {
    avatarLoading.value = false
  }
}

const handleRemoveAvatar = async () => {
  avatarLoading.value = true
  try {
    const response = await deleteCurrentAvatar()
    if (!response.success || !response.data) {
      Message.error(response.error || '头像移除失败')
      return
    }

    applyProfileData(response.data)
    patchCurrentUser(response.data)
    Message.success('头像已移除')
  } finally {
    avatarLoading.value = false
  }
}

const handleSaveProfile = async () => {
  if (!profileForm.username || !SYSTEM_USERNAME_REGEX.test(profileForm.username)) {
    Message.warning('系统用户名至少 3 位，仅支持字母或字母+数字组合，且不能为纯数字')
    return
  }

  if (profileForm.real_name && !CHINESE_REAL_NAME_REGEX.test(profileForm.real_name)) {
    Message.warning('姓名仅支持2到20位中文')
    return
  }

  if (profileForm.phone_number && !CHINA_MOBILE_REGEX.test(profileForm.phone_number)) {
    Message.warning('请输入正确的11位手机号')
    return
  }

  profileLoading.value = true
  try {
    const payload: Record<string, string> = {
      username: profileForm.username,
      real_name: profileForm.real_name,
      phone_number: profileForm.phone_number,
    }
    if (profileForm.email.trim()) {
      payload.email = profileForm.email.trim()
    }

    const response = await updateCurrentProfile(payload)
    if (!response.success || !response.data) {
      Message.error(response.error || '保存个人资料失败')
      return
    }

    applyProfileData(response.data)
    patchCurrentUser(response.data)
    isEditingProfile.value = false
    Message.success('个人资料已更新')
  } finally {
    profileLoading.value = false
  }
}

const handleChangePassword = async () => {
  if (!passwordForm.current_password || !passwordForm.new_password || !passwordForm.confirm_password) {
    Message.warning('请填写完整密码信息')
    return
  }

  passwordLoading.value = true
  try {
    const response = await changeCurrentPassword(passwordForm)
    if (!response.success) {
      Message.error(response.error || '修改密码失败')
      return
    }

    Message.success('密码修改成功，请重新登录')
    authStore.logout()
    router.push('/login')
  } finally {
    passwordLoading.value = false
  }
}

onMounted(() => {
  loadProfile()
})
</script>

<style scoped>
.personal-center {
  padding: 4px;
}

.page-header {
  margin-bottom: 16px;
  padding: 18px 20px;
  border-radius: 16px;
  border: 1px solid var(--ui-panel-border);
  background:
    radial-gradient(circle at top right, rgba(var(--theme-accent-rgb), 0.08), transparent 24%),
    linear-gradient(180deg, rgba(255, 255, 255, 0.96), rgba(247, 250, 253, 0.92));
  box-shadow: var(--ui-panel-shadow);
}

.page-header h2 {
  margin: 0 0 6px;
  font-size: 22px;
  color: var(--theme-text);
}

.page-header p {
  margin: 0;
  color: var(--theme-text-secondary);
}

.center-layout {
  display: grid;
  grid-template-columns: 220px minmax(0, 1fr);
  gap: 16px;
}

.section-sidebar {
  border-radius: 16px;
  overflow: hidden;
  background: var(--ui-panel-bg);
  border: 1px solid var(--ui-panel-border);
  box-shadow: var(--ui-panel-shadow);
}

.section-content {
  min-width: 0;
}

.panel-card {
  border-radius: 16px;
  border: 1px solid var(--ui-panel-border);
  box-shadow: var(--ui-panel-shadow);
  background: var(--ui-panel-bg);
}

.form-shell {
  width: 100%;
  max-width: 520px;
  margin: 0 auto;
}

.avatar-editor {
  display: flex;
  align-items: center;
  gap: 14px;
  margin-bottom: 18px;
  padding: 12px;
  border: 1px solid var(--ui-panel-border);
  border-radius: 10px;
  background: var(--ui-panel-bg);
}

.profile-avatar-preview {
  width: 64px;
  height: 64px;
  flex: 0 0 64px;
  display: flex;
  align-items: center;
  justify-content: center;
  overflow: hidden;
  border-radius: 8px;
  border: 1px solid var(--ui-toolbar-border);
  background: linear-gradient(135deg, rgba(var(--theme-accent-rgb), 0.9), rgba(14, 165, 233, 0.92));
  color: #ffffff;
  font-size: 24px;
  font-weight: 700;
}

.profile-avatar-preview img {
  display: block;
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.avatar-actions {
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.avatar-tip {
  font-size: 12px;
  color: var(--theme-text-secondary);
}

.avatar-input {
  display: none;
}

.form-shell :deep(.arco-form-item) {
  width: 100%;
}

.password-shell {
  max-width: 420px;
}

.organization-list {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.profile-readonly {
  display: flex;
  flex-direction: column;
  gap: 18px;
}

.readonly-item {
  display: flex;
  flex-direction: column;
  gap: 6px;
  padding: 14px 16px;
  border-radius: 12px;
  border: 1px solid rgba(149, 161, 187, 0.12);
  background: linear-gradient(180deg, rgba(248, 250, 252, 0.95), rgba(255, 255, 255, 0.96));
  box-shadow: 0 8px 18px rgba(15, 23, 42, 0.03);
}

.readonly-label {
  font-size: 13px;
  color: var(--theme-text-secondary);
}

.readonly-value {
  font-size: 14px;
  color: var(--theme-text);
  word-break: break-all;
}

.readonly-value-group {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.readonly-hint,
.field-tip {
  display: flex;
  flex-direction: column;
  gap: 4px;
  margin-top: 6px;
  font-size: 12px;
  color: var(--theme-text-secondary);
}

.static-field {
  min-height: 32px;
  display: flex;
  align-items: center;
  padding: 0 2px;
  color: var(--theme-text);
  font-size: 14px;
}

.action-btn {
  min-width: 96px;
  width: auto;
  justify-content: center;
}

.action-row {
  display: flex;
  justify-content: center;
  width: 100%;
  padding-top: 4px;
}

.personal-center :deep(.arco-menu) {
  padding: 10px;
  background: transparent;
}

.personal-center :deep(.arco-menu-inner) {
  padding: 0;
}

.personal-center :deep(.arco-menu-item),
.personal-center :deep(.arco-menu-inline-header) {
  border-radius: 10px;
}

.personal-center :deep(.arco-menu-item.arco-menu-selected) {
  background: rgba(var(--theme-accent-rgb), 0.08);
  color: var(--theme-accent);
}

.personal-center :deep(.arco-card-header) {
  border-bottom-color: var(--ui-toolbar-border);
}

.personal-center :deep(.arco-card-body) {
  padding: 20px;
}

.personal-center :deep(.arco-card) {
  overflow: hidden;
}

.personal-center :deep(.arco-input-wrapper),
.personal-center :deep(.arco-input-password),
.personal-center :deep(.arco-btn) {
  border-radius: 10px;
}

@media (max-width: 900px) {
  .center-layout {
    grid-template-columns: 1fr;
  }

  .form-shell {
    max-width: none;
  }

  .avatar-editor {
    align-items: flex-start;
  }
}
</style>
