const AUTH_KEYS = {
  isAuthenticated: 'auth-isAuthenticated',
  user: 'auth-user',
  accessToken: 'auth-accessToken',
  refreshToken: 'auth-refreshToken',
  userPermissions: 'auth-userPermissions',
} as const

type AuthStorageKey = (typeof AUTH_KEYS)[keyof typeof AUTH_KEYS]

function getSessionStorage(): Storage | null {
  if (typeof window === 'undefined') {
    return null
  }
  return window.sessionStorage
}

function getLegacyStorage(): Storage | null {
  if (typeof window === 'undefined') {
    return null
  }
  return window.localStorage
}

function migrateLegacyValue(key: AuthStorageKey) {
  const sessionStorage = getSessionStorage()
  const legacyStorage = getLegacyStorage()
  if (!sessionStorage || !legacyStorage) {
    return
  }

  if (sessionStorage.getItem(key) !== null) {
    return
  }

  const legacyValue = legacyStorage.getItem(key)
  if (legacyValue === null) {
    return
  }

  sessionStorage.setItem(key, legacyValue)
  legacyStorage.removeItem(key)
}

export function migrateLegacyAuthStorage() {
  Object.values(AUTH_KEYS).forEach(migrateLegacyValue)
}

export function getAuthStorageItem(key: AuthStorageKey): string | null {
  migrateLegacyValue(key)
  return getSessionStorage()?.getItem(key) ?? null
}

export function setAuthStorageItem(key: AuthStorageKey, value: string) {
  getSessionStorage()?.setItem(key, value)
  getLegacyStorage()?.removeItem(key)
}

export function removeAuthStorageItem(key: AuthStorageKey) {
  getSessionStorage()?.removeItem(key)
  getLegacyStorage()?.removeItem(key)
}

export function clearAuthStorage() {
  Object.values(AUTH_KEYS).forEach(removeAuthStorageItem)
}

export function getStoredAccessToken(): string | null {
  return getAuthStorageItem(AUTH_KEYS.accessToken)
}

export function getStoredRefreshToken(): string | null {
  return getAuthStorageItem(AUTH_KEYS.refreshToken)
}

export function setStoredAccessToken(token: string) {
  setAuthStorageItem(AUTH_KEYS.accessToken, token)
}

export function setStoredRefreshToken(token: string) {
  setAuthStorageItem(AUTH_KEYS.refreshToken, token)
}

export { AUTH_KEYS }
