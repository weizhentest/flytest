import { request } from '@/utils/request'

export interface ProfileData {
  id: number
  username: string
  username_changed_at?: string | null
  username_next_editable_at?: string | null
  can_change_username?: boolean
  email: string
  first_name: string
  last_name: string
  real_name?: string
  phone_number?: string
  is_staff: boolean
  is_active: boolean
  groups: string[]
}

export interface UpdateProfilePayload {
  username?: string
  email: string
  real_name?: string
  phone_number?: string
}

export interface ChangePasswordPayload {
  current_password: string
  new_password: string
  confirm_password: string
}

export const getCurrentProfile = () =>
  request<ProfileData>({
    url: '/accounts/profile/',
    method: 'GET',
  })

export const updateCurrentProfile = (payload: UpdateProfilePayload) =>
  request<ProfileData>({
    url: '/accounts/profile/',
    method: 'PUT',
    data: payload,
  })

export const changeCurrentPassword = (payload: ChangePasswordPayload) =>
  request<null>({
    url: '/accounts/change-password/',
    method: 'POST',
    data: payload,
  })
