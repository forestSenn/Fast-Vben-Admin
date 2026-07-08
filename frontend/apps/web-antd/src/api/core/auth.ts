import type {
  Message,
  NewPassword,
  Token,
  UpdatePassword,
  UserPublic,
  UserUpdateMe,
} from '#/api/generated';

import { baseRequestClient, requestClient } from '#/api/request';

import { getMyPermissionsApi } from './rbac';

export namespace AuthApi {
  /** 登录接口参数 */
  export interface LoginParams {
    password?: string;
    username?: string;
  }

  /** 登录接口返回值 */
  export interface LoginResult {
    accessToken: string;
  }

  export type FastApiToken = Token;

  export type FastApiUser = UserPublic;

  export interface RefreshTokenResult {
    data: string;
    status: number;
  }

  export type MessageResult = Message;

  export type UpdateCurrentUserPayload = UserUpdateMe;

  export type UpdatePasswordPayload = UpdatePassword;

  export type ResetPasswordPayload = NewPassword;
}

/**
 * 登录
 */
export async function loginApi(data: AuthApi.LoginParams) {
  const formData = new URLSearchParams();
  formData.set('username', data.username ?? '');
  formData.set('password', data.password ?? '');

  const token = await requestClient.post<AuthApi.FastApiToken>(
    '/login/access-token',
    formData,
    {
      headers: {
        'Content-Type': 'application/x-www-form-urlencoded',
      },
    },
  );

  return {
    accessToken: token.access_token,
  };
}

/**
 * 刷新accessToken
 */
export async function refreshTokenApi() {
  return baseRequestClient.post<AuthApi.RefreshTokenResult>('/auth/refresh', {
    withCredentials: true,
  });
}

/**
 * 退出登录
 */
export async function logoutApi() {
  return Promise.resolve();
}

export function getCurrentUserApi() {
  return requestClient.get<AuthApi.FastApiUser>('/users/me');
}

export function updateCurrentUserApi(data: AuthApi.UpdateCurrentUserPayload) {
  return requestClient.request<AuthApi.FastApiUser>('/users/me', {
    data,
    method: 'PATCH',
  });
}

export function updateCurrentPasswordApi(data: AuthApi.UpdatePasswordPayload) {
  return requestClient.request<AuthApi.MessageResult>('/users/me/password', {
    data,
    method: 'PATCH',
  });
}

export function requestPasswordRecoveryApi(email: string) {
  return requestClient.post<AuthApi.MessageResult>(
    `/password-recovery/${encodeURIComponent(email)}`,
  );
}

export function resetPasswordApi(data: AuthApi.ResetPasswordPayload) {
  return requestClient.post<AuthApi.MessageResult>('/reset-password', data);
}

/**
 * 获取用户权限码
 */
export async function getAccessCodesApi() {
  return await getMyPermissionsApi();
}
