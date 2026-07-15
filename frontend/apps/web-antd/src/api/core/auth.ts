import type {
  LoginCaptchaChallenge as FastApiLoginCaptchaChallenge,
  Message,
  NewPassword,
  RegistrationStatus,
  SmsCodeRequest,
  SmsCodeSent,
  SmsLoginRequest,
  TenantRegistrationRequest,
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
    captcha_code?: string;
    captcha_id?: string;
    mfa_code?: string;
    password?: string;
    tenant_code?: string;
    username?: string;
  }

  /** 登录接口返回值 */
  export interface LoginResult {
    accessToken: string;
  }

  export type FastApiToken = Token;
  export type LoginCaptchaChallenge = FastApiLoginCaptchaChallenge;

  export type FastApiUser = UserPublic;

  export interface RefreshTokenResult {
    data: string;
    status: number;
  }

  export type MessageResult = Message;

  export type UpdateCurrentUserPayload = UserUpdateMe;

  export type UpdatePasswordPayload = UpdatePassword;

  export type ResetPasswordPayload = NewPassword;

  export type SendSmsCodePayload = SmsCodeRequest;

  export type SendSmsCodeResult = SmsCodeSent;

  export type SmsLoginPayload = SmsLoginRequest;

  export type TenantRegistrationPayload = TenantRegistrationRequest;

  export type RegistrationStatusResult = RegistrationStatus;

  export interface MfaStatus {
    confirmed_at?: null | string;
    enabled: boolean;
    method?: null | string;
    pending_setup: boolean;
    recovery_codes_remaining: number;
  }

  export interface MfaSetup {
    account_name: string;
    issuer: string;
    otpauth_uri: string;
    secret: string;
  }

  export interface EnableMfaPayload {
    code: string;
  }

  export interface EnableMfaResult extends MessageResult {
    recovery_codes: string[];
  }

  export interface DisableMfaPayload extends EnableMfaPayload {
    current_password: string;
  }

  export interface EnterpriseOidcStatus {
    enabled: boolean;
    login_url?: null | string;
  }
}

/**
 * 登录
 */
export async function loginApi(data: AuthApi.LoginParams) {
  const formData = new URLSearchParams();
  formData.set('username', data.username ?? '');
  formData.set('password', data.password ?? '');
  if (data.tenant_code) {
    formData.set('tenant_code', data.tenant_code);
  }
  if (data.captcha_id) {
    formData.set('captcha_id', data.captcha_id);
  }
  if (data.captcha_code) {
    formData.set('captcha_code', data.captcha_code);
  }
  if (data.mfa_code) {
    formData.set('mfa_code', data.mfa_code);
  }

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

export function getCurrentUserMfaStatusApi() {
  return requestClient.get<AuthApi.MfaStatus>('/users/me/mfa');
}

export function setupCurrentUserMfaApi() {
  return requestClient.post<AuthApi.MfaSetup>('/users/me/mfa/setup');
}

export function enableCurrentUserMfaApi(data: AuthApi.EnableMfaPayload) {
  return requestClient.post<AuthApi.EnableMfaResult>('/users/me/mfa/enable', data);
}

export function disableCurrentUserMfaApi(data: AuthApi.DisableMfaPayload) {
  return requestClient.post<AuthApi.MessageResult>('/users/me/mfa/disable', data);
}

export function requestPasswordRecoveryApi(email: string) {
  return requestClient.post<AuthApi.MessageResult>(
    `/password-recovery/${encodeURIComponent(email)}`,
  );
}

export function getLoginCaptchaApi(username: string) {
  return requestClient.get<AuthApi.LoginCaptchaChallenge>('/login/captcha', {
    params: {
      username,
    },
  });
}

export function sendLoginSmsCodeApi(data: AuthApi.SendSmsCodePayload) {
  return requestClient.post<AuthApi.SendSmsCodeResult>('/login/sms-code', data);
}

export async function smsLoginApi(data: AuthApi.SmsLoginPayload) {
  const token = await requestClient.post<AuthApi.FastApiToken>(
    '/login/sms',
    data,
  );
  return {
    accessToken: token.access_token,
  };
}

export function getRegistrationStatusApi() {
  return requestClient.get<AuthApi.RegistrationStatusResult>(
    '/login/registration/status',
    { skipErrorMessage: true },
  );
}

export async function registerTenantApi(
  data: AuthApi.TenantRegistrationPayload,
) {
  const token = await requestClient.post<AuthApi.FastApiToken>(
    '/login/register-tenant',
    data,
  );
  return {
    accessToken: token.access_token,
  };
}

export function getEnterpriseOidcStatusApi() {
  return requestClient.get<AuthApi.EnterpriseOidcStatus>(
    '/login/enterprise-oidc/status',
    { skipErrorMessage: true },
  );
}

export async function exchangeEnterpriseOidcTicketApi(ticket: string) {
  const token = await requestClient.post<AuthApi.FastApiToken>(
    '/login/enterprise-oidc/exchange',
    { ticket },
  );
  return { accessToken: token.access_token };
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
