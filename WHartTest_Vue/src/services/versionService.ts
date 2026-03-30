import packageJson from '../../package.json'

export interface VersionInfo {
  current: string
  latest?: string
  hasUpdate: boolean
  releaseUrl?: string
  releaseNotes?: string
  checkTime?: Date
}

interface GitHubContentsResponse {
  version?: string
}

interface PackageJsonVersionPayload {
  version?: string
}

const GITHUB_REPO = 'weixiaoluan/flytest'
const GITHUB_REPO_URL = `https://github.com/${GITHUB_REPO}`
const GITHUB_UPDATES_URL = `${GITHUB_REPO_URL}/commits/main`
const GITHUB_PACKAGE_JSON_URL = `https://raw.githubusercontent.com/${GITHUB_REPO}/main/WHartTest_Vue/package.json`

let cachedVersionInfo: VersionInfo | null = null
let lastCheckTime = 0
const CHECK_INTERVAL = 1000 * 60 * 60

export function getCurrentVersion(): string {
  return packageJson.version || '0.0.0'
}

export function getVersionUpdatesUrl(): string {
  return GITHUB_UPDATES_URL
}

function normalizeVersion(version?: string): string {
  return version?.replace(/^v/, '').trim() || ''
}

async function fetchRepoPackageVersion(): Promise<string | undefined> {
  const response = await fetch(GITHUB_PACKAGE_JSON_URL)

  if (!response.ok) {
    return undefined
  }

  try {
    const remotePackageJson = await response.json() as PackageJsonVersionPayload
    return normalizeVersion(remotePackageJson.version)
  } catch (error) {
    console.warn('Failed to parse remote package.json version', error)
    return undefined
  }
}

export function compareVersions(v1: string, v2: string): number {
  const parts1 = normalizeVersion(v1).split('.').map(Number)
  const parts2 = normalizeVersion(v2).split('.').map(Number)

  for (let i = 0; i < Math.max(parts1.length, parts2.length); i++) {
    const p1 = parts1[i] || 0
    const p2 = parts2[i] || 0
    if (p1 > p2) return 1
    if (p1 < p2) return -1
  }

  return 0
}

export async function checkLatestVersion(): Promise<VersionInfo> {
  const now = Date.now()

  if (cachedVersionInfo && now - lastCheckTime < CHECK_INTERVAL) {
    return cachedVersionInfo
  }

  const current = getCurrentVersion()
  const versionInfo: VersionInfo = {
    current,
    hasUpdate: false,
    releaseUrl: getVersionUpdatesUrl(),
    releaseNotes: 'Version source: weixiaoluan/flytest/WHartTest_Vue/package.json'
  }

  try {
    const repoVersion = await fetchRepoPackageVersion()
    if (repoVersion) {
      versionInfo.latest = repoVersion
      versionInfo.hasUpdate = compareVersions(repoVersion, current) > 0
    }

    versionInfo.checkTime = new Date()
  } catch (error) {
    console.warn('Failed to check latest version', error)
  }

  cachedVersionInfo = versionInfo
  lastCheckTime = now
  return versionInfo
}

export function formatVersion(version: string): string {
  if (!version || version === '0.0.0') {
    return 'dev'
  }

  return `v${normalizeVersion(version)}`
}
