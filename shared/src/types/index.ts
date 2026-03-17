export type AppEnvironment = 'local' | 'testing' | 'production'

export interface PaginationMeta {
  currentPage: number
  from: number | null
  lastPage: number
  perPage: number
  to: number | null
  total: number
}
