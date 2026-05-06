<template>
  <div class="register-container">
    <div class="background-decoration">
      <div class="decoration-circle circle-1"></div>
      <div class="decoration-circle circle-2"></div>
      <div class="decoration-circle circle-3"></div>
    </div>

    <div class="register-card">
      <div class="brand-section">
        <div class="brand-logo">
          <img :src="brandFullLogoUrl" alt="FlyTest Logo" class="register-full-logo" />
        </div>
        <h1 class="brand-title">注册新账号</h1>
        <p class="brand-subtitle">欢迎加入 FlyTest</p>
      </div>

      <form class="register-form" @submit.prevent="handleSubmit">
        <div class="input-group">
          <div class="input-wrapper">
            <div class="input-icon">
              <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="1.5" stroke="currentColor">
                <path stroke-linecap="round" stroke-linejoin="round" d="M15.75 6a3.75 3.75 0 11-7.5 0 3.75 3.75 0 017.5 0zM4.501 20.118a7.5 7.5 0 0114.998 0A17.933 17.933 0 0112 21.75c-2.676 0-5.216-.584-7.499-1.632z" />
              </svg>
            </div>
            <input
              id="realName"
              v-model.trim="formState.realName"
              type="text"
              required
              class="form-input"
              maxlength="20"
              placeholder="请输入姓名（仅支持中文）"
            />
          </div>
          <div class="input-tip">姓名仅支持 2 到 20 位中文，且不能与其他用户重复。</div>
        </div>

        <div class="input-group">
          <div class="input-wrapper">
            <div class="input-icon">
              <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="1.5" stroke="currentColor">
                <path stroke-linecap="round" stroke-linejoin="round" d="M2.25 6.75c0-1.243 1.007-2.25 2.25-2.25h15a2.25 2.25 0 012.25 2.25v10.5A2.25 2.25 0 0119.5 19.5h-15a2.25 2.25 0 01-2.25-2.25V6.75z" />
                <path stroke-linecap="round" stroke-linejoin="round" d="M8.25 6.75h7.5M8.25 12h7.5m-7.5 5.25h4.5" />
              </svg>
            </div>
            <input
              id="phoneNumber"
              v-model.trim="formState.phoneNumber"
              type="tel"
              required
              class="form-input"
              inputmode="numeric"
              maxlength="11"
              placeholder="请输入手机号"
            />
          </div>
        </div>

        <div class="input-group">
          <div class="input-wrapper">
            <div class="input-icon">
              <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="1.5" stroke="currentColor">
                <path stroke-linecap="round" stroke-linejoin="round" d="M16.5 10.5V6.75a4.5 4.5 0 10-9 0v3.75m-.75 11.25h10.5a2.25 2.25 0 002.25-2.25v-6.75a2.25 2.25 0 00-2.25-2.25H6.75a2.25 2.25 0 00-2.25 2.25v6.75a2.25 2.25 0 002.25 2.25z" />
              </svg>
            </div>
            <input
              :type="showPassword ? 'text' : 'password'"
              id="password"
              v-model="formState.password"
              required
              class="form-input"
              placeholder="请输入密码"
            />
            <div class="password-toggle" @click="togglePasswordVisibility">
              <svg v-if="!showPassword" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="1.5" stroke="currentColor">
                <path stroke-linecap="round" stroke-linejoin="round" d="M2.036 12.322a1.012 1.012 0 010-.639C3.423 7.51 7.36 4.5 12 4.5c4.638 0 8.573 3.007 9.963 7.178.07.207.07.431 0 .639C20.577 16.49 16.64 19.5 12 19.5c-4.638 0-8.573-3.007-9.963-7.178z" />
                <path stroke-linecap="round" stroke-linejoin="round" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
              </svg>
              <svg v-else xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="1.5" stroke="currentColor">
                <path stroke-linecap="round" stroke-linejoin="round" d="M3.98 8.223A10.477 10.477 0 001.934 12C3.226 16.338 7.244 19.5 12 19.5c.993 0 1.953-.138 2.863-.395M6.228 6.228A10.45 10.45 0 0112 4.5c4.756 0 8.773 3.162 10.065 7.498a10.523 10.523 0 01-4.293 5.774M6.228 6.228L3 3m3.228 3.228l3.65 3.65m7.894 7.894L21 21m-3.228-3.228l-3.65-3.65m0 0a3 3 0 10-4.243-4.243m4.242 4.242L9.88 9.88" />
              </svg>
            </div>
          </div>
        </div>

        <div class="input-group">
          <div class="input-wrapper">
            <div class="input-icon">
              <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="1.5" stroke="currentColor">
                <path stroke-linecap="round" stroke-linejoin="round" d="M9 12.75L11.25 15 15 9.75m-3-7.036A11.959 11.959 0 013.598 6 11.99 11.99 0 003 9.749c0 5.592 3.824 10.29 9 11.623 5.176-1.332 9-6.03 9-11.622 0-1.31-.21-2.571-.598-3.751h-.152c-3.196 0-6.1-1.248-8.25-3.285z" />
              </svg>
            </div>
            <input
              :type="showConfirmPassword ? 'text' : 'password'"
              id="confirmPassword"
              v-model="formState.confirmPassword"
              required
              class="form-input"
              placeholder="请再次输入密码"
            />
            <div class="password-toggle" @click="toggleConfirmPasswordVisibility">
              <svg v-if="!showConfirmPassword" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="1.5" stroke="currentColor">
                <path stroke-linecap="round" stroke-linejoin="round" d="M2.036 12.322a1.012 1.012 0 010-.639C3.423 7.51 7.36 4.5 12 4.5c4.638 0 8.573 3.007 9.963 7.178.07.207.07.431 0 .639C20.577 16.49 16.64 19.5 12 19.5c-4.638 0-8.573-3.007-9.963-7.178z" />
                <path stroke-linecap="round" stroke-linejoin="round" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
              </svg>
              <svg v-else xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="1.5" stroke="currentColor">
                <path stroke-linecap="round" stroke-linejoin="round" d="M3.98 8.223A10.477 10.477 0 001.934 12C3.226 16.338 7.244 19.5 12 19.5c.993 0 1.953-.138 2.863-.395M6.228 6.228A10.45 10.45 0 0112 4.5c4.756 0 8.773 3.162 10.065 7.498a10.523 10.523 0 01-4.293 5.774M6.228 6.228L3 3m3.228 3.228l3.65 3.65m7.894 7.894L21 21m-3.228-3.228l-3.65-3.65m0 0a3 3 0 10-4.243-4.243m4.242 4.242L9.88 9.88" />
              </svg>
            </div>
          </div>
        </div>

        <button type="submit" class="register-button" :class="{ loading: isLoading }" :disabled="isLoading">
          <span v-if="!isLoading">注册</span>
          <span v-else class="loading-content">
            <svg class="loading-spinner" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
              <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
              <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
            </svg>
            注册中...
          </span>
        </button>

        <div v-if="registerError" class="error-message">
          <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="1.5" stroke="currentColor" class="error-icon">
            <path stroke-linecap="round" stroke-linejoin="round" d="M12 9v3.75m9-.75a9 9 0 11-18 0 9 9 0 0118 0zm-9 3.75h.008v.008H12v-.008z" />
          </svg>
          {{ registerError }}
        </div>

        <div v-if="registerSuccess.username" class="register-tip">
          <div class="success-title">注册成功</div>
          <div class="success-row">
            <span class="success-label">系统用户名</span>
            <code class="success-username">{{ registerSuccess.username }}</code>
          </div>
          <div class="success-row">
            <span class="success-label">登录方式</span>
            <span>系统用户名 + 密码，或手机号 + 密码</span>
          </div>
          <div class="success-row">
            <span class="success-label">审核状态</span>
            <span>请等待管理员审核后再登录</span>
          </div>
        </div>

        <div class="login-link">
          <p>
            已有账号？
            <router-link to="/login" class="link">点击登录</router-link>
          </p>
        </div>
      </form>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, reactive, ref } from 'vue';
import { Message } from '@arco-design/web-vue';
import { useAuthStore } from '@/store/authStore';
import { brandFullLogoUrl } from '@/utils/assetUrl';

const CHINA_MOBILE_REGEX = /^1[3-9]\d{9}$/;
const CHINESE_REAL_NAME_REGEX = /^[\u4e00-\u9fff·]{2,20}$/;

const authStore = useAuthStore();

const formState = reactive({
  realName: '',
  phoneNumber: '',
  password: '',
  confirmPassword: '',
});

const showPassword = ref(false);
const showConfirmPassword = ref(false);
const registerSuccess = reactive({
  username: '',
});

const isLoading = computed(() => authStore.getIsLoading);
const registerError = computed(() => authStore.getRegisterError);

const togglePasswordVisibility = () => {
  showPassword.value = !showPassword.value;
};

const toggleConfirmPasswordVisibility = () => {
  showConfirmPassword.value = !showConfirmPassword.value;
};

const validateForm = () => {
  if (!formState.realName || !formState.phoneNumber || !formState.password || !formState.confirmPassword) {
    Message.warning('请填写所有必填项');
    return false;
  }

  if (!CHINESE_REAL_NAME_REGEX.test(formState.realName)) {
    Message.warning('姓名仅支持2到20位中文');
    return false;
  }

  if (!CHINA_MOBILE_REGEX.test(formState.phoneNumber)) {
    Message.warning('请填写真实的手机号');
    return false;
  }

  if (formState.password !== formState.confirmPassword) {
    Message.warning('两次输入的密码不一致');
    return false;
  }

  return true;
};

const handleSubmit = async () => {
  if (!validateForm()) {
    return;
  }

  try {
    registerSuccess.username = '';
    const result = await authStore.register(formState.realName, formState.phoneNumber, formState.password);
    if (result.success && result.data) {
      registerSuccess.username = result.data.username || '';
      Message.success(`注册成功，系统用户名：${registerSuccess.username}`);
      formState.realName = '';
      formState.phoneNumber = '';
      formState.password = '';
      formState.confirmPassword = '';
    }
  } catch (error) {
    console.error('Exception during authStore.register call:', error);
    Message.error('注册过程中发生意外错误');
  }
};
</script>

<style scoped>
.register-container {
  height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 20px;
  background: linear-gradient(135deg, #f8f9fc 0%, #e9ecf3 100%);
  position: relative;
  overflow: hidden;
  box-sizing: border-box;
}

.background-decoration {
  position: absolute;
  inset: 0;
  pointer-events: none;
  z-index: 1;
}

.decoration-circle {
  position: absolute;
  border-radius: 50%;
  background: linear-gradient(135deg, rgba(var(--theme-accent-rgb), 0.1) 0%, rgba(var(--theme-accent-rgb), 0.05) 100%);
  animation: float 6s ease-in-out infinite;
}

.circle-1 {
  width: 200px;
  height: 200px;
  top: 10%;
  left: 10%;
}

.circle-2 {
  width: 150px;
  height: 150px;
  top: 70%;
  right: 15%;
  animation-delay: 2s;
}

.circle-3 {
  width: 100px;
  height: 100px;
  top: 50%;
  left: 80%;
  animation-delay: 4s;
}

@keyframes float {
  0%, 100% {
    transform: translateY(0) scale(1);
    opacity: 0.7;
  }
  50% {
    transform: translateY(-20px) scale(1.05);
    opacity: 1;
  }
}

.register-card {
  background: #ffffff;
  border-radius: 20px;
  box-shadow: 0 25px 50px rgba(0, 0, 0, 0.08), 0 15px 25px rgba(0, 0, 0, 0.04);
  padding: 40px 45px;
  width: 100%;
  max-width: 480px;
  position: relative;
  z-index: 2;
  border: 1px solid rgba(255, 255, 255, 0.2);
  animation: slideUp 0.8s cubic-bezier(0.4, 0, 0.2, 1);
}

.brand-section {
  text-align: center;
  margin-bottom: 32px;
}

.brand-logo {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: min(240px, 100%);
  max-width: 100%;
  height: auto;
  margin-bottom: 20px;
}

.register-full-logo {
  width: 100%;
  max-width: 240px;
  height: auto;
  object-fit: contain;
}

.brand-title {
  font-size: 28px;
  font-weight: 700;
  color: #333333;
  margin: 0 0 6px 0;
}

.brand-subtitle {
  font-size: 15px;
  color: #6b7280;
  margin: 0;
  font-weight: 500;
}

.register-form {
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.input-wrapper {
  position: relative;
  display: flex;
  align-items: center;
}

.input-icon {
  position: absolute;
  left: 18px;
  z-index: 1;
  color: #9ca3af;
}

.input-icon svg {
  width: 20px;
  height: 20px;
}

.form-input {
  width: 100%;
  padding: 16px 20px 16px 54px;
  border: 1.5px solid #e5e7eb;
  border-radius: 14px;
  font-size: 16px;
  color: #374151;
  background: #fafafa;
  transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
  box-sizing: border-box;
  min-height: 52px;
}

.form-input:focus {
  outline: none;
  border-color: var(--theme-accent);
  background: #ffffff;
  box-shadow: 0 0 0 4px rgba(var(--theme-accent-rgb), 0.08);
}

.input-tip {
  margin-top: 6px;
  padding-left: 4px;
  font-size: 12px;
  line-height: 1.5;
  color: #6b7280;
}

.password-toggle {
  position: absolute;
  right: 18px;
  cursor: pointer;
  color: #9ca3af;
  z-index: 1;
}

.password-toggle svg {
  width: 20px;
  height: 20px;
}

.register-button {
  width: 100%;
  padding: 12px 24px;
  background: var(--theme-accent);
  border: none;
  border-radius: 14px;
  color: #ffffff;
  font-size: 16px;
  font-weight: 600;
  cursor: pointer;
  min-height: 48px;
}

.register-button:disabled {
  opacity: 0.7;
  cursor: not-allowed;
}

.loading-content {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
}

.loading-spinner {
  width: 20px;
  height: 20px;
  animation: spin 1s linear infinite;
}

.error-message {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 16px 20px;
  background: #fef2f2;
  border: 1px solid #fecaca;
  border-radius: 8px;
  color: #dc2626;
  font-size: 15px;
}

.error-icon {
  width: 22px;
  height: 22px;
  flex-shrink: 0;
}

.register-tip {
  padding: 12px 14px;
  border-radius: 10px;
  background: rgba(var(--theme-accent-rgb), 0.08);
  color: #4b5563;
  font-size: 14px;
  line-height: 1.6;
}

.success-title {
  margin-bottom: 8px;
  color: #1f2937;
  font-size: 15px;
  font-weight: 600;
}

.success-row {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-top: 4px;
}

.success-label {
  min-width: 72px;
  color: #6b7280;
}

.success-username {
  padding: 2px 8px;
  border-radius: 8px;
  background: rgba(var(--theme-accent-rgb), 0.14);
  color: var(--theme-accent);
  font-size: 13px;
}

.login-link {
  text-align: center;
}

.login-link p {
  font-size: 15px;
  color: #6b7280;
  margin: 0;
}

.login-link .link {
  color: var(--theme-accent);
  text-decoration: none;
  font-weight: 500;
}

@keyframes spin {
  from {
    transform: rotate(0deg);
  }
  to {
    transform: rotate(360deg);
  }
}

@keyframes slideUp {
  from {
    opacity: 0;
    transform: translateY(40px) scale(0.95);
  }
  to {
    opacity: 1;
    transform: translateY(0) scale(1);
  }
}

@media (max-width: 768px) {
  .register-container {
    padding: 16px;
    overflow-y: auto;
  }

  .register-card {
    padding: 24px 20px;
    max-width: none;
  }

  .form-input {
    padding: 12px 14px 12px 42px;
    min-height: 44px;
  }

  .input-icon {
    left: 14px;
  }

  .password-toggle {
    right: 14px;
  }
}
</style>
