import axios from 'axios'
import { defineStore } from 'pinia'
import {
  login as loginService,
  register as registerService,
  type AuthServiceLoginResponse,
  type AuthServiceRegisterResponse,
} from '@/services/authService'
import { getUserPermissions } from '@/services/permissionService'
import { API_BASE_URL } from '@/config/api'
import { useProjectStore } from '@/store/projectStore'
import {
  AUTH_KEYS,
  clearAuthStorage,
  getAuthStorageItem,
  migrateLegacyAuthStorage,
  removeAuthStorageItem,
  setAuthStorageItem,
} from '@/utils/authStorage'

interface User {
  id: number
  username: string
  email: string
  first_name: string
  last_name: string
  phone_number?: string
  real_name?: string
  is_staff: boolean
  is_active: boolean
  groups: any[]
  approval_status?: 'pending' | 'approved' | 'rejected'
  approval_status_display?: string
  approval_review_note?: string
  approval_reviewed_at?: string | null
  approval_reviewed_by?: string | null
}

interface Permission {
  id: number
  name: string
  name_cn: string
  codename: string
  content_type: {
    id: number
    app_label: string
    app_label_cn: string
    app_label_sort: number
    app_label_subcategory: string | null
    app_label_subcategory_sort: number
    model: string
    model_cn: string
    model_verbose: string
  }
}

interface AuthState {
  isAuthenticated: boolean
  isInitialized: boolean
  user: User | null
  accessToken: string | null
  refreshToken: string | null
  loginError: string | null
  registerError: string | null
  isLoading: boolean
  userPermissions: Permission[] | string[] | []
}

let bootstrapPromise: Promise<boolean> | null = null

function readStoredJson<T>(key: (typeof AUTH_KEYS)[keyof typeof AUTH_KEYS]): T | null {
  const raw = getAuthStorageItem(key)
  if (!raw) {
    return null
  }

  try {
    return JSON.parse(raw) as T
  } catch (error) {
    console.error(`Failed to parse auth storage key ${key}:`, error)
    removeAuthStorageItem(key)
    return null
  }
}

function extractPayload<T>(responseData: any): T {
  if (responseData && typeof responseData === 'object' && 'data' in responseData) {
    return responseData.data as T
  }
  return responseData as T
}

export const useAuthStore = defineStore('auth', {
  state: (): AuthState => {
    migrateLegacyAuthStorage()
    return {
      isAuthenticated: getAuthStorageItem(AUTH_KEYS.isAuthenticated) === 'true',
      isInitialized: false,
      user: readStoredJson<User>(AUTH_KEYS.user),
      accessToken: null,
      refreshToken: null,
      loginError: null,
      registerError: null,
      isLoading: false,
      userPermissions: readStoredJson<Permission[] | string[]>(AUTH_KEYS.userPermissions) ?? [],
    }
  },

  actions: {
    persistUserState() {
      setAuthStorageItem(AUTH_KEYS.isAuthenticated, this.isAuthenticated ? 'true' : 'false')
      if (this.user) {
        setAuthStorageItem(AUTH_KEYS.user, JSON.stringify(this.user))
      } else {
        removeAuthStorageItem(AUTH_KEYS.user)
      }
    },

    hydrateFromStorage() {
      migrateLegacyAuthStorage()
      removeAuthStorageItem(AUTH_KEYS.accessToken)
      removeAuthStorageItem(AUTH_KEYS.refreshToken)
      this.isAuthenticated = getAuthStorageItem(AUTH_KEYS.isAuthenticated) === 'true'
      this.user = readStoredJson<User>(AUTH_KEYS.user)
      this.userPermissions = readStoredJson<Permission[] | string[]>(AUTH_KEYS.userPermissions) ?? []
    },

    resetAuthState() {
      this.isAuthenticated = false
      this.user = null
      this.accessToken = null
      this.refreshToken = null
      this.loginError = null
      this.registerError = null
      this.userPermissions = []
      clearAuthStorage()
    },

    updateAccessToken(token: string | null) {
      this.accessToken = token
    },

    updateRefreshToken(token: string | null) {
      this.refreshToken = token
    },

    setCurrentUser(user: User | null) {
      this.user = user
      this.persistUserState()
    },

    async bootstrapSession(force = false): Promise<boolean> {
      if (bootstrapPromise && !force) {
        return bootstrapPromise
      }

      bootstrapPromise = (async () => {
        this.hydrateFromStorage()

        if (this.accessToken && this.user && this.isAuthenticated && !force) {
          this.isInitialized = true
          return true
        }

        try {
          const refreshResponse = await axios.post(
            `${API_BASE_URL}/token/refresh/`,
            {},
            {
              withCredentials: true,
              headers: { Accept: 'application/json' },
            },
          )
          const refreshPayload = extractPayload<{ access?: string; refresh?: string }>(refreshResponse.data)
          if (!refreshPayload?.access) {
            throw new Error('No access token returned from refresh endpoint.')
          }

          this.accessToken = refreshPayload.access
          this.refreshToken = refreshPayload.refresh || null

          const userResponse = await axios.get(`${API_BASE_URL}/accounts/me/`, {
            withCredentials: true,
            headers: {
              Accept: 'application/json',
              Authorization: `Bearer ${refreshPayload.access}`,
            },
          })
          const userPayload = extractPayload<User>(userResponse.data)

          this.isAuthenticated = true
          this.user = userPayload
          this.persistUserState()
          await this.loadUserPermissions()
          this.isInitialized = true
          return true
        } catch {
          this.resetAuthState()
          this.isInitialized = true
          return false
        } finally {
          bootstrapPromise = null
        }
      })()

      return bootstrapPromise
    },

    async login(username: string, password: string, rememberMe = false): Promise<boolean> {
      this.isLoading = true
      this.loginError = null

      try {
        const response: AuthServiceLoginResponse = await loginService(username, password, rememberMe)
        if (!response.success || !response.data) {
          this.resetAuthState()
          this.loginError = response.error || '登录失败，请检查您的凭据。'
          return false
        }

        this.isAuthenticated = true
        this.user = response.data.user
        this.accessToken = response.data.access
        this.refreshToken = response.data.refresh
        this.persistUserState()
        await this.loadUserPermissions()
        this.isInitialized = true
        return true
      } catch (error: any) {
        this.resetAuthState()
        this.loginError = error.message || '发生未知错误，请稍后再试。'
        return false
      } finally {
        this.isLoading = false
      }
    },

    logout() {
      const authHeader = this.accessToken ? { Authorization: `Bearer ${this.accessToken}` } : {}
      void axios.post(
        `${API_BASE_URL}/accounts/logout/`,
        {},
        {
          withCredentials: true,
          headers: authHeader,
        },
      ).catch(() => undefined)

      this.resetAuthState()
      this.isInitialized = true

      const projectStore = useProjectStore()
      projectStore.reset()
    },

    checkAuthStatus() {
      this.hydrateFromStorage()
    },

    async register(realName: string, phoneNumber: string, password: string): Promise<AuthServiceRegisterResponse> {
      this.isLoading = true
      this.registerError = null

      try {
        const response: AuthServiceRegisterResponse = await registerService(realName, phoneNumber, password)
        if (response.success && response.data) {
          this.logout()
          return response
        }

        this.registerError = response.error || '注册失败，请检查您输入的信息。'
        return response
      } catch (error: any) {
        this.registerError = error.message || '发生未知错误，请稍后再试。'
        return {
          success: false,
          error: this.registerError,
        }
      } finally {
        this.isLoading = false
      }
    },

    hasPermission(permission: string): boolean {
      if (!this.isAuthenticated || !this.user) {
        return false
      }

      if (this.user.is_staff) {
        return true
      }

      if (this.user.approval_status !== 'approved') {
        return false
      }

      if (!this.userPermissions || this.userPermissions.length === 0) {
        return false
      }

      if (typeof this.userPermissions[0] === 'string') {
        return (this.userPermissions as string[]).includes(permission)
      }

      return (this.userPermissions as Permission[]).some(item => {
        const standardFormat = `${item.content_type.app_label}.${item.codename}`
        return item.codename === permission || item.name === permission || standardFormat === permission
      })
    },

    setUserPermissions(permissions: Permission[] | string[]) {
      this.userPermissions = permissions
      setAuthStorageItem(AUTH_KEYS.userPermissions, JSON.stringify(permissions))
    },

    async loadUserPermissions() {
      if (!this.user?.id) {
        this.setUserPermissions([])
        return
      }

      try {
        const response = await getUserPermissions(this.user.id)
        if (response.success && response.data) {
          this.setUserPermissions(response.data)
          return
        }

        this.setUserPermissions([])
        console.warn('获取用户权限失败或无权限数据:', response.error || '无数据')
      } catch (error) {
        this.setUserPermissions([])
        console.error('获取用户权限失败:', error)
      }
    },
  },

  getters: {
    isLoggedIn: (state: AuthState) => state.isAuthenticated,
    currentUser: (state: AuthState) => state.user,
    isApproved: (state: AuthState) =>
      Boolean(state.user && (state.user.is_staff || state.user.approval_status === 'approved')),
    approvalStatus: (state: AuthState) => state.user?.approval_status || 'pending',
    getAccessToken: (state: AuthState) => state.accessToken,
    getRefreshToken: (state: AuthState) => state.refreshToken,
    getLoginError: (state: AuthState) => state.loginError,
    getRegisterError: (state: AuthState) => state.registerError,
    getIsLoading: (state: AuthState) => state.isLoading,
    isPermissionsLoaded: (state: AuthState) => Array.isArray(state.userPermissions),
  },
})
