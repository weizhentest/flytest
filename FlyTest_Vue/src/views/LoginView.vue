<template>
  <div class="login-page">
    <canvas ref="canvasRef" class="starry-canvas" />

    <div class="content-layer">
      <div class="brand-area">
        <img :src="brandLogoUrl" alt="Logo" class="brand-logo" />
        <h1 class="brand-title">FlyTest</h1>
        <p class="brand-subtitle">AI智能测试平台</p>
        <div class="brand-tags" role="list" aria-label="平台能力标签">
          <div v-for="tag in featureTags" :key="tag.label" class="tag-item" role="listitem">
            <button
              type="button"
              class="tag"
              :aria-label="`${tag.label}：${tag.description}`"
            >
              {{ tag.label }}
            </button>
            <div class="tag-tooltip" role="tooltip">
              <strong>{{ tag.label }}</strong>
              <p>{{ tag.description }}</p>
            </div>
          </div>
        </div>
      </div>

      <button
        ref="launcherButtonRef"
        type="button"
        class="login-launcher"
        aria-label="打开登录弹窗"
        @click="openLoginDialog"
      >
        <span class="launcher-aura" />
        <span class="launcher-icon" aria-hidden="true">
          <img
            v-if="!fingerprintImageLoadFailed && currentFingerprintAsset"
            :src="currentFingerprintAsset"
            alt=""
            class="launcher-fingerprint-img"
            @error="handleFingerprintAssetError"
          />
          <svg v-else xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="1.8" stroke="currentColor">
            <path stroke-linecap="round" stroke-linejoin="round" d="M16.5 10.5V7.875a4.5 4.5 0 00-9 0V10.5m9 0h.75A2.25 2.25 0 0119.5 12.75v5.625a2.25 2.25 0 01-2.25 2.25h-10.5a2.25 2.25 0 01-2.25-2.25V12.75A2.25 2.25 0 016.75 10.5h.75" />
          </svg>
        </span>
        <span class="launcher-copy">
          <strong>账号登录</strong>
          <span>请输入系统用户名或手机号登录</span>
        </span>
      </button>
    </div>

    <Transition name="login-dialog">
      <div v-if="loginDialogVisible" class="login-overlay" @click.self="closeLoginDialog">
        <div
          ref="loginDialogRef"
          class="login-card"
          role="dialog"
          aria-modal="true"
          aria-labelledby="login-title"
          aria-describedby="login-description"
          @keydown="handleDialogKeydown"
        >
          <button type="button" class="dialog-close" aria-label="关闭登录弹窗" @click="closeLoginDialog">
            <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="1.5" stroke="currentColor">
              <path stroke-linecap="round" stroke-linejoin="round" d="M6 18 18 6M6 6l12 12" />
            </svg>
          </button>

          <div class="card-header">
            <h2 id="login-title">欢迎回来</h2>
            <p id="login-description">请输入系统用户名或手机号登录</p>
          </div>

          <form class="login-form" @submit.prevent="handleLogin">
            <div class="input-wrapper">
              <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="1.5" stroke="currentColor" class="input-icon">
                <path stroke-linecap="round" stroke-linejoin="round" d="M15.75 6a3.75 3.75 0 11-7.5 0 3.75 3.75 0 017.5 0zM4.501 20.118a7.5 7.5 0 0114.998 0A17.933 17.933 0 0112 21.75c-2.676 0-5.216-.584-7.499-1.632z" />
              </svg>
              <input
                ref="usernameInputRef"
                v-model="username"
                type="text"
                required
                autocomplete="username"
                placeholder="请输入系统用户名或手机号"
                class="form-input"
              />
            </div>

            <div class="input-wrapper">
              <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="1.5" stroke="currentColor" class="input-icon">
                <path stroke-linecap="round" stroke-linejoin="round" d="M16.5 10.5V6.75a4.5 4.5 0 10-9 0v3.75m-.75 11.25h10.5a2.25 2.25 0 002.25-2.25v-6.75a2.25 2.25 0 00-2.25-2.25H6.75a2.25 2.25 0 00-2.25 2.25v6.75a2.25 2.25 0 002.25 2.25z" />
              </svg>
              <input
                v-model="password"
                :type="showPassword ? 'text' : 'password'"
                required
                autocomplete="current-password"
                placeholder="请输入密码"
                class="form-input"
              />
              <button
                v-if="!showPassword"
                class="toggle-icon"
                type="button"
                aria-label="显示密码"
                :aria-pressed="showPassword"
                @click="showPassword = true"
              >
                <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="1.5" stroke="currentColor">
                  <path stroke-linecap="round" stroke-linejoin="round" d="M2.036 12.322a1.012 1.012 0 010-.639C3.423 7.51 7.36 4.5 12 4.5c4.638 0 8.573 3.007 9.963 7.178.07.207.07.431 0 .639C20.577 16.49 16.64 19.5 12 19.5c-4.638 0-8.573-3.007-9.963-7.178z" />
                  <path stroke-linecap="round" stroke-linejoin="round" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
                </svg>
              </button>
              <button
                v-else
                class="toggle-icon"
                type="button"
                aria-label="隐藏密码"
                :aria-pressed="showPassword"
                @click="showPassword = false"
              >
                <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="1.5" stroke="currentColor">
                  <path stroke-linecap="round" stroke-linejoin="round" d="M3.98 8.223A10.477 10.477 0 001.934 12C3.226 16.338 7.244 19.5 12 19.5c.993 0 1.953-.138 2.863-.395M6.228 6.228A10.45 10.45 0 0112 4.5c4.756 0 8.773 3.162 10.065 7.498a10.523 10.523 0 01-4.293 5.774M6.228 6.228L3 3m3.228 3.228l3.65 3.65m7.894 7.894L21 21m-3.228-3.228l-3.65-3.65m0 0a3 3 0 10-4.243-4.243m4.242 4.242L9.88 9.88" />
                </svg>
              </button>
            </div>

            <label class="remember-me">
              <input v-model="rememberMe" type="checkbox" />
              <span>记住我</span>
            </label>

            <button type="submit" class="login-btn" :disabled="isLoading">
              <template v-if="!isLoading">登录</template>
              <template v-else>
                <svg class="spinner" viewBox="0 0 24 24" fill="none">
                  <circle cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4" opacity="0.25" />
                  <path fill="currentColor" opacity="0.75" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
                </svg>
                登录中...
              </template>
            </button>

            <div v-if="errorMessage" class="error-msg">
              <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="1.5" stroke="currentColor" class="error-icon">
                <path stroke-linecap="round" stroke-linejoin="round" d="M12 9v3.75m9-.75a9 9 0 11-18 0 9 9 0 0118 0zm-9 3.75h.008v.008H12v-.008z" />
              </svg>
              {{ errorMessage }}
            </div>

            <p class="register-link">
              还没有账号?
              <router-link to="/register">立即注册</router-link>
            </p>
          </form>
        </div>
      </div>
    </Transition>

    <footer class="page-copyright">
      <span>Copyright © {{ currentYear }} FlyTest AI智能测试平台 版权所有 · 开发与维护：魏振 · 66674094@qq.com</span>
    </footer>
  </div>
</template>

<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { Message } from '@arco-design/web-vue'
import { useRouter } from 'vue-router'
import { useStarryBackground } from '@/composables/useStarryBackground'
import { useAuthStore } from '@/store/authStore'
import { brandLogoUrl } from '@/utils/assetUrl'

interface FeatureTag {
  label: string
  description: string
}

const canvasRef = ref<HTMLCanvasElement | null>(null)
const usernameInputRef = ref<HTMLInputElement | null>(null)
const launcherButtonRef = ref<HTMLButtonElement | null>(null)
const loginDialogRef = ref<HTMLDivElement | null>(null)
const username = ref('')
const password = ref('')
const rememberMe = ref(false)
const showPassword = ref(false)
const loginDialogVisible = ref(false)
const previousFocusedElement = ref<HTMLElement | null>(null)
const previousBodyOverflow = ref('')
const currentYear = new Date().getFullYear()
const fingerprintAssetCandidates = ['/login-fingerprint.svg', '/login-fingerprint.png'] as const
const currentFingerprintAssetIndex = ref(0)
const fingerprintImageLoadFailed = ref(false)
const featureTags: FeatureTag[] = [
  {
    label: 'AI生成用例',
    description: '借助 AI 理解需求与业务上下文，自动扩展测试场景并生成结构化用例，提升覆盖深度与编写效率。',
  },
  {
    label: 'RAG知识库',
    description: '通过 AI 结合检索增强能力吸收文档与历史经验，为测试生成、分析与问答提供更精准的知识支撑。',
  },
  {
    label: 'openclaw',
    description: '将 openclaw 作为 AI 能力延展接入平台，增强复杂任务理解、操作推理与自动化协同能力。',
  },
  {
    label: 'Skills技能库',
    description: '把高频测试经验沉淀成可复用的 AI 技能单元，让模型在不同项目中持续扩展可执行能力。',
  },
  {
          label: 'AI接口自动化',
    description: '由 AI 辅助解析接口语义、补全断言与生成调用链，帮助团队快速扩展 API 自动化覆盖。',
  },
  {
    label: 'UI自动化',
    description: '让 AI 理解页面结构与用户路径，自动扩展 UI 交互场景，提升前端回归测试的生成与执行效率。',
  },
  {
    label: 'APP自动化',
    description: '借助 AI 对移动端流程、控件与操作链路的理解，持续扩展 APP 自动化测试场景与执行能力。',
  },
  {
    label: 'AI渗透测试',
    description: '利用 AI 扩展安全测试思路，辅助识别潜在攻击面、风险路径与薄弱环节，提升渗透测试效率。',
  },
  {
    label: 'LangGraph',
    description: '通过 LangGraph 编排多阶段 AI 工作流，把生成、分析、执行与反馈串成可持续扩展的智能链路。',
  },
]


useStarryBackground(canvasRef)

const router = useRouter()
const authStore = useAuthStore()
const isLoading = computed(() => authStore.getIsLoading)
const errorMessage = computed(() => authStore.getLoginError)
const currentFingerprintAsset = computed(() => fingerprintAssetCandidates[currentFingerprintAssetIndex.value] ?? null)

const focusableSelector = [
  'button:not([disabled])',
  'input:not([disabled])',
  'a[href]',
  '[tabindex]:not([tabindex="-1"])',
].join(',')

const focusUsernameInput = async () => {
  await nextTick()
  usernameInputRef.value?.focus()
}

const handleFingerprintAssetError = () => {
  if (currentFingerprintAssetIndex.value < fingerprintAssetCandidates.length - 1) {
    currentFingerprintAssetIndex.value += 1
    return
  }

  fingerprintImageLoadFailed.value = true
}

const openLoginDialog = async () => {
  previousFocusedElement.value = document.activeElement instanceof HTMLElement ? document.activeElement : launcherButtonRef.value
  loginDialogVisible.value = true
  await focusUsernameInput()
}

const closeLoginDialog = () => {
  if (isLoading.value) {
    return
  }
  loginDialogVisible.value = false
  showPassword.value = false
  nextTick(() => {
    const target = previousFocusedElement.value ?? launcherButtonRef.value
    target?.focus()
  })
}

const handleWindowKeydown = (event: KeyboardEvent) => {
  if (event.key === 'Escape' && loginDialogVisible.value) {
    closeLoginDialog()
  }
}

const handleDialogKeydown = (event: KeyboardEvent) => {
  if (event.key !== 'Tab') {
    return
  }

  const focusableElements = loginDialogRef.value?.querySelectorAll<HTMLElement>(focusableSelector)
  if (!focusableElements || focusableElements.length === 0) {
    event.preventDefault()
    return
  }

  const firstElement = focusableElements[0]
  const lastElement = focusableElements[focusableElements.length - 1]
  const activeElement = document.activeElement

  if (event.shiftKey && activeElement === firstElement) {
    event.preventDefault()
    lastElement.focus()
    return
  }

  if (!event.shiftKey && activeElement === lastElement) {
    event.preventDefault()
    firstElement.focus()
  }
}

const handleLogin = async () => {
  if (!username.value || !password.value) {
    Message.warning('请输入系统用户名或手机号和密码')
    return
  }

  const success = await authStore.login(username.value, password.value, rememberMe.value)
  if (success) {
    Message.success('登录成功')
    if (rememberMe.value) {
      localStorage.setItem('rememberedUsername', username.value)
    } else {
      localStorage.removeItem('rememberedUsername')
    }
    loginDialogVisible.value = false
    await router.push({ name: 'Dashboard' })
  }
}

watch(loginDialogVisible, (visible) => {
  if (visible) {
    previousBodyOverflow.value = document.body.style.overflow
    document.body.style.overflow = 'hidden'
    return
  }

  document.body.style.overflow = previousBodyOverflow.value
})

onMounted(() => {
  authStore.checkAuthStatus()
  if (authStore.isLoggedIn) {
    router.push({ name: 'Dashboard' })
  }
  const saved = localStorage.getItem('rememberedUsername')
  if (saved) {
    username.value = saved
    rememberMe.value = true
  }
})

watch(loginDialogVisible, (visible) => {
  if (visible) {
    window.addEventListener('keydown', handleWindowKeydown)
    return
  }

  window.removeEventListener('keydown', handleWindowKeydown)
})

onBeforeUnmount(() => {
  window.removeEventListener('keydown', handleWindowKeydown)
  document.body.style.overflow = previousBodyOverflow.value
})
</script>

<style scoped>
.login-page {
  position: relative;
  min-height: 100vh;
  overflow: hidden;
  background: radial-gradient(ellipse at 20% 50%, #0a1628 0%, #020810 100%);
}

.starry-canvas,
.login-overlay {
  position: absolute;
  inset: 0;
}

.starry-canvas {
  z-index: 0;
}

.content-layer {
  position: relative;
  z-index: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 36px;
  min-height: 100vh;
  padding: 12px 20px 110px;
}

.brand-area {
  text-align: center;
  animation: fade-in-down 0.8s ease-out;
}

.brand-logo {
  width: 72px;
  height: 72px;
  margin-bottom: 16px;
  filter: drop-shadow(0 0 20px rgba(100, 180, 255, 0.4));
}

.brand-title {
  margin: 0 0 8px;
  color: #fff;
  font-size: 42px;
  font-weight: 800;
  letter-spacing: -0.5px;
  text-shadow: 0 0 30px rgba(100, 180, 255, 0.3);
}

.brand-subtitle {
  margin: 0 0 20px;
  color: rgba(180, 210, 255, 0.8);
  font-size: 16px;
  font-weight: 400;
  letter-spacing: 2px;
}

.brand-tags {
  display: flex;
  flex-wrap: wrap;
  justify-content: center;
  gap: 12px;
}

.tag-item {
  position: relative;
  display: inline-flex;
}

.tag {
  padding: 8px 20px;
  border: 1px solid rgba(100, 180, 255, 0.15);
  border-radius: 999px;
  background: rgba(100, 180, 255, 0.08);
  backdrop-filter: blur(4px);
  color: rgba(180, 210, 255, 0.85);
  font-size: 14px;
  font-weight: 600;
  letter-spacing: 0.02em;
  cursor: default;
  transition: transform 0.24s ease, border-color 0.24s ease, background-color 0.24s ease, color 0.24s ease;
}

.tag:hover,
.tag-item:focus-within .tag {
  transform: translateY(-1px);
  border-color: rgba(124, 190, 255, 0.34);
  background: rgba(100, 180, 255, 0.14);
  color: rgba(232, 243, 255, 0.96);
}

.tag-tooltip {
  position: absolute;
  left: 50%;
  top: calc(100% + 12px);
  z-index: 3;
  width: min(280px, calc(100vw - 48px));
  padding: 14px 16px;
  border: 1px solid rgba(100, 180, 255, 0.15);
  border-radius: 16px;
  background: linear-gradient(180deg, rgba(8, 18, 34, 0.9), rgba(10, 22, 40, 0.92));
  box-shadow: 0 16px 40px rgba(0, 0, 0, 0.32);
  backdrop-filter: blur(18px);
  color: rgba(218, 231, 255, 0.94);
  text-align: left;
  opacity: 0;
  pointer-events: none;
  transform: translateX(-50%) translateY(8px);
  transition: opacity 0.24s ease, transform 0.24s ease;
}

.tag-tooltip::before {
  content: '';
  position: absolute;
  left: 50%;
  top: -6px;
  width: 12px;
  height: 12px;
  background: rgba(9, 20, 37, 0.94);
  border-left: 1px solid rgba(100, 180, 255, 0.15);
  border-top: 1px solid rgba(100, 180, 255, 0.15);
  transform: translateX(-50%) rotate(45deg);
}

.tag-tooltip strong {
  display: block;
  margin-bottom: 6px;
  color: #f3f8ff;
  font-size: 15px;
  font-weight: 700;
}

.tag-tooltip p {
  margin: 0;
  color: rgba(194, 213, 244, 0.82);
  font-size: 13px;
  line-height: 1.65;
}

.tag-item:hover .tag-tooltip,
.tag-item:focus-within .tag-tooltip {
  opacity: 1;
  transform: translateX(-50%) translateY(0);
}

.tag:focus-visible {
  outline: 2px solid rgba(96, 165, 250, 0.9);
  outline-offset: 3px;
}

.login-launcher {
  position: relative;
  display: inline-flex;
  align-items: center;
  gap: 16px;
  padding: 14px 20px 14px 14px;
  border: 1px solid rgba(129, 184, 255, 0.26);
  border-radius: 999px;
  background: rgba(9, 20, 38, 0.54);
  box-shadow: 0 16px 40px rgba(0, 0, 0, 0.35);
  backdrop-filter: blur(18px);
  cursor: pointer;
  transition: transform 0.28s ease, box-shadow 0.28s ease, border-color 0.28s ease, background-color 0.28s ease;
  animation: fade-in-up 0.8s ease-out 0.15s both;
}

.login-launcher:hover {
  transform: translateY(-3px) scale(1.02);
  border-color: rgba(129, 184, 255, 0.44);
  background: rgba(12, 28, 52, 0.66);
  box-shadow: 0 18px 50px rgba(20, 74, 169, 0.28);
}

.login-launcher:focus-visible,
.dialog-close:focus-visible,
.toggle-icon:focus-visible {
  outline: 2px solid rgba(96, 165, 250, 0.9);
  outline-offset: 3px;
}

.launcher-aura {
  position: absolute;
  inset: -10px;
  border-radius: inherit;
  background: radial-gradient(circle, rgba(88, 158, 255, 0.24), transparent 72%);
  opacity: 0.7;
  filter: blur(12px);
}

.launcher-logo,
.launcher-copy {
  position: relative;
  z-index: 1;
}

.launcher-icon {
  position: relative;
  z-index: 1;
  width: 56px;
  height: 56px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border-radius: 50%;
  background: linear-gradient(135deg, rgba(37, 99, 235, 0.82), rgba(56, 189, 248, 0.82));
  box-shadow: 0 12px 28px rgba(37, 99, 235, 0.35);
}

.launcher-icon svg,
.launcher-fingerprint-img {
  width: 36px;
  height: 36px;
  display: block;
  object-fit: contain;
  color: #eaf3ff;
}

.launcher-copy {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: 2px;
  color: #e8f0ff;
  text-align: left;
}

.launcher-copy strong {
  font-size: 18px;
  font-weight: 700;
}

.launcher-copy span {
  color: rgba(180, 210, 255, 0.72);
  font-size: 13px;
}

.login-overlay {
  position: fixed;
  z-index: 3;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 24px;
  background: transparent;
  backdrop-filter: none;
}

.login-card {
  position: relative;
  width: min(100%, 420px);
  padding: 36px 32px 32px;
  border: 1px solid rgba(255, 255, 255, 0.18);
  border-radius: 24px;
  background: linear-gradient(180deg, rgba(8, 18, 34, 0.56), rgba(10, 22, 40, 0.62));
  box-shadow: 0 22px 60px rgba(0, 0, 0, 0.28);
  backdrop-filter: blur(28px);
  transform-origin: center;
}

.dialog-close {
  position: absolute;
  top: 16px;
  right: 16px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 36px;
  height: 36px;
  border: none;
  border-radius: 50%;
  background: rgba(255, 255, 255, 0.06);
  color: rgba(224, 236, 255, 0.88);
  cursor: pointer;
  transition: background-color 0.24s ease, transform 0.24s ease;
}

.dialog-close:hover {
  background: rgba(96, 165, 250, 0.16);
  transform: rotate(90deg);
}

.dialog-close svg,
.toggle-icon svg,
.error-icon,
.input-icon {
  width: 18px;
  height: 18px;
}

.card-header {
  margin-bottom: 28px;
  text-align: center;
}

.card-header h2 {
  margin: 0 0 6px;
  color: #fff;
  font-size: 24px;
  font-weight: 700;
}

.card-header p,
.remember-me,
.register-link {
  color: rgba(180, 210, 255, 0.62);
}

.card-header p {
  margin: 0;
  font-size: 14px;
}

.login-form {
  display: flex;
  flex-direction: column;
  gap: 18px;
}

.input-wrapper {
  position: relative;
  display: flex;
  align-items: center;
}

.input-icon {
  position: absolute;
  left: 14px;
  color: rgba(180, 210, 255, 0.4);
  pointer-events: none;
  transition: color 0.3s ease;
}

.form-input {
  box-sizing: border-box;
  width: 100%;
  padding: 12px 42px 12px 44px;
  border: 1px solid rgba(255, 255, 255, 0.12);
  border-radius: 12px;
  background: rgba(255, 255, 255, 0.06);
  color: #e8f0ff;
  font-size: 14px;
  outline: none;
  transition: all 0.3s ease;
}

.form-input::placeholder {
  color: rgba(180, 210, 255, 0.35);
}

.form-input:focus {
  border-color: rgba(100, 180, 255, 0.5);
  background: rgba(255, 255, 255, 0.08);
  box-shadow: 0 0 0 3px rgba(100, 180, 255, 0.1);
}

.input-wrapper:focus-within .input-icon {
  color: rgba(100, 180, 255, 0.8);
}

.form-input::-ms-clear,
.form-input::-ms-reveal {
  display: none;
}

.toggle-icon {
  position: absolute;
  right: 14px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  padding: 0;
  border: none;
  background: transparent;
  color: rgba(180, 210, 255, 0.4);
  cursor: pointer;
  transition: color 0.3s ease;
}

.toggle-icon:hover {
  color: rgba(100, 180, 255, 0.8);
}

.remember-me {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 13px;
  cursor: pointer;
  user-select: none;
}

.remember-me input {
  accent-color: #4a9eff;
}

.login-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  width: 100%;
  padding: 12px;
  border: none;
  border-radius: 12px;
  background: linear-gradient(135deg, #2563eb, #1d4ed8);
  box-shadow: 0 4px 16px rgba(37, 99, 235, 0.3);
  color: #fff;
  cursor: pointer;
  font-size: 15px;
  font-weight: 600;
  transition: transform 0.3s ease, box-shadow 0.3s ease, background 0.3s ease;
}

.login-btn:hover:not(:disabled) {
  transform: translateY(-1px);
  background: linear-gradient(135deg, #3b82f6, #2563eb);
  box-shadow: 0 6px 24px rgba(37, 99, 235, 0.4);
}

.login-btn:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.spinner {
  width: 18px;
  height: 18px;
  animation: spin 1s linear infinite;
}

.error-msg {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 10px 14px;
  border: 1px solid rgba(239, 68, 68, 0.25);
  border-radius: 10px;
  background: rgba(239, 68, 68, 0.12);
  color: #fca5a5;
  font-size: 13px;
}

.error-icon {
  flex-shrink: 0;
}

.register-link {
  margin: 4px 0 0;
  font-size: 13px;
  text-align: center;
}

.register-link a {
  color: #60a5fa;
  font-weight: 600;
  text-decoration: none;
  transition: color 0.2s ease;
}

.register-link a:hover {
  color: #93c5fd;
  text-decoration: underline;
}

.page-copyright {
  position: fixed;
  left: 50%;
  bottom: 22px;
  z-index: 2;
  display: flex;
  gap: 18px;
  align-items: center;
  justify-content: center;
  transform: translateX(-50%);
  padding: 10px 18px;
  border: 1px solid rgba(148, 163, 184, 0.16);
  border-radius: 999px;
  background: rgba(8, 18, 34, 0.4);
  backdrop-filter: blur(10px);
  color: rgba(180, 210, 255, 0.72);
  font-size: 12px;
  line-height: 1;
  white-space: nowrap;
}

.login-dialog-enter-active,
.login-dialog-leave-active {
  transition: opacity 0.24s ease;
}

.login-dialog-enter-active .login-card,
.login-dialog-leave-active .login-card {
  transition: transform 0.28s ease, opacity 0.28s ease;
}

.login-dialog-enter-from,
.login-dialog-leave-to {
  opacity: 0;
}

.login-dialog-enter-from .login-card,
.login-dialog-leave-to .login-card {
  opacity: 0;
  transform: scale(0.78) translateY(12px);
}

@keyframes spin {
  to {
    transform: rotate(360deg);
  }
}

@keyframes fade-in-down {
  from {
    opacity: 0;
    transform: translateY(-24px);
  }

  to {
    opacity: 1;
    transform: translateY(0);
  }
}

@keyframes fade-in-up {
  from {
    opacity: 0;
    transform: translateY(24px);
  }

  to {
    opacity: 1;
    transform: translateY(0);
  }
}

@media (max-width: 640px) {
  .content-layer {
    gap: 28px;
    padding: 12px 16px 88px;
  }

  .brand-title {
    font-size: 32px;
  }

  .login-launcher {
    width: min(100%, 320px);
    gap: 12px;
    padding-right: 18px;
  }

  .launcher-icon {
    width: 50px;
    height: 50px;
  }

  .login-overlay {
    padding: 16px;
  }

  .login-card {
    padding: 32px 24px 24px;
  }

  .brand-tags {
    gap: 8px;
  }

  .tag-item {
    width: auto;
  }

  .tag {
    padding: 5px 12px;
    font-size: 12px;
  }

  .tag-tooltip {
    width: min(240px, calc(100vw - 36px));
    padding: 12px 14px;
  }
}
</style>
