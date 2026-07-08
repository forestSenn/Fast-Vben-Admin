import type {
  UserCreate,
  UserPublic,
  UsersPublic,
  UserUpdate,
} from '#/api/generated';

import { requestClient } from '#/api/request';

export type UserRecord = UserPublic;

export type UserListResult = UsersPublic;

export interface UserListParams {
  keyword?: string;
  page?: number;
  page_size?: number;
}

export type UserCreatePayload = UserCreate;

export type UserUpdatePayload = UserUpdate;

export function listUsersApi(params: UserListParams) {
  return requestClient.get<UserListResult>('/users', { params });
}

export function createUserApi(data: UserCreatePayload) {
  return requestClient.post<UserRecord>('/users', data);
}

export function updateUserApi(userId: string, data: UserUpdatePayload) {
  return requestClient.request<UserRecord>(`/users/${userId}`, {
    data,
    method: 'PATCH',
  });
}

export function deleteUserApi(userId: string) {
  return requestClient.delete<void>(`/users/${userId}`);
}

export const usersExportPath = '/users/export';
