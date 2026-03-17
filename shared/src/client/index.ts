export interface ApiClientConfig {
  baseUrl: string
}

export function normalizeBaseUrl(baseUrl: string): string {
  return baseUrl.replace(/\/$/, '')
}

export function createApiClientConfig(baseUrl: string): ApiClientConfig {
  return {
    baseUrl: normalizeBaseUrl(baseUrl),
  }
}
