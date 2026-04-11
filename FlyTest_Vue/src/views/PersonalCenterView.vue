<template>
  <div class="personal-center">
    <div class="page-header">
      <h2>个人中心</h2>
      <p>维护个人资料、所属组织与账号安全信息。</p>
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
            <template v-if="!isEditingProfile">
              <div class="profile-readonly">
                <div class="readonly-item">
                  <span class="readonly-label">用户名</span>
                  <span class="readonly-value">{{ profileForm.username || '-' }}</span>
                </div>
                <div class="readonly-item">
                  <span class="readonly-label">真实姓名</span>
                  <span class="readonly-value">{{ profileForm.real_name || '-' }}</span>
                </div>
                <div class="readonly-item">
                  <span class="readonly-label">邮箱</span>
                  <span class="readonly-value">{{ profileForm.email || '-' }}</span>
                </div>
                <div class="readonly-item">
                  <span class="readonly-label">手机号</span>
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
              <a-form-item label="用户名">
                <div class="static-field">{{ profileForm.username || '-' }}</div>
              </a-form-item>

              <a-form-item label="真实姓名">
                <a-input v-model="profileForm.real_name" placeholder="请输入真实姓名" />
              </a-form-item>

              <a-form-item label="邮箱">
                <a-input v-model="profileForm.email" placeholder="请输入邮箱" />
              </a-form-item>

              <a-form-item label="手机号">
                <a-input v-model="profileForm.phone_number" placeholder="请输入手机号" />
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
import { onMounted, reactive, ref } from 'vue'
import { Message } from '@arco-design/web-vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '@/store/authStore'
import {
  changeCurrentPassword,
  getCurrentProfile,
  updateCurrentProfile,
  type ProfileData,
} from '@/services/profileService'

const router = useRouter()
const authStore = useAuthStore()

const activeSection = ref<'profile' | 'password'>('profile')
const isEditingProfile = ref(false)
const profileLoading = ref(false)
const passwordLoading = ref(false)

const profileForm = reactive({
  username: '',
  email: '',
  real_name: '',
  phone_number: '',
})

const organizations = ref<string[]>([])

const passwordForm = reactive({
  current_password: '',
  new_password: '',
  confirm_password: '',
})

const applyProfileData = (payload: Partial<ProfileData> | null | undefined) => {
  profileForm.username = payload?.username || authStore.currentUser?.username || ''
  profileForm.email = payload?.email || authStore.currentUser?.email || ''
  profileForm.real_name = payload?.real_name || authStore.currentUser?.real_name || ''
  profileForm.phone_number = payload?.phone_number || authStore.currentUser?.phone_number || ''
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

const handleSaveProfile = async () => {
  profileLoading.value = true
  try {
    const response = await updateCurrentProfile({
      email: profileForm.email,
      real_name: profileForm.real_name,
      phone_number: profileForm.phone_number,
    })
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
  padding: 20px;
}

.page-header {
  margin-bottom: 16px;
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
  background: var(--theme-bg);
}

.section-content {
  min-width: 0;
}

.panel-card {
  border-radius: 16px;
}

.form-shell {
  width: 100%;
  max-width: 520px;
  margin: 0 auto;
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
}

@media (max-width: 900px) {
  .center-layout {
    grid-template-columns: 1fr;
  }

  .form-shell {
    max-width: none;
  }
}
</style>
