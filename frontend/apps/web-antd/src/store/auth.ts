import type { Recordable, UserInfo } from '@vben/types';

import { ref } from 'vue';
import { useRouter } from 'vue-router';

import { LOGIN_PATH } from '@vben/constants';
import { preferences } from '@vben/preferences';
import { resetAllStores, useAccessStore, useUserStore } from '@vben/stores';

import { notification } from 'ant-design-vue';
import { defineStore } from 'pinia';

import {
  exchangeEnterpriseOidcTicketApi,
  getAccessCodesApi,
  getUserInfoApi,
  loginApi,
  logoutApi,
  registerTenantApi,
  smsLoginApi,
  switchTenantApi,
} from '#/api';
import { $t } from '#/locales';

export const useAuthStore = defineStore('auth', () => {
  const accessStore = useAccessStore();
  const userStore = useUserStore();
  const router = useRouter();

  const loginLoading = ref(false);

  /**
   * 异步处理登录操作
   * Asynchronously handle the login process
   * @param params 登录表单数据
   */
  async function completeLogin(
    accessToken: string,
    onSuccess?: () => Promise<void> | void,
  ) {
    let userInfo: null | UserInfo = null;
    accessStore.setAccessToken(accessToken);

    const [fetchUserInfoResult, accessCodes] = await Promise.all([
      fetchUserInfo(),
      getAccessCodesApi(),
    ]);
    userInfo = fetchUserInfoResult;
    userStore.setUserInfo(userInfo);
    accessStore.setAccessCodes(accessCodes);

    if (accessStore.loginExpired) {
      accessStore.setLoginExpired(false);
    } else {
      onSuccess
        ? await onSuccess?.()
        : await router.push(
            userInfo.homePath || preferences.app.defaultHomePath,
          );
    }

    if (userInfo?.realName) {
      notification.success({
        description: `${$t('authentication.loginSuccessDesc')}:${userInfo?.realName}`,
        duration: 3,
        message: $t('authentication.loginSuccess'),
      });
    }

    return { userInfo };
  }

  async function authLogin(
    params: Recordable<any>,
    onSuccess?: () => Promise<void> | void,
  ) {
    try {
      loginLoading.value = true;
      const { accessToken } = await loginApi(params);
      return await completeLogin(accessToken, onSuccess);
    } finally {
      loginLoading.value = false;
    }
  }

  async function authEnterpriseOidcLogin(
    ticket: string,
    onSuccess?: () => Promise<void> | void,
  ) {
    try {
      loginLoading.value = true;
      const { accessToken } = await exchangeEnterpriseOidcTicketApi(ticket);
      return await completeLogin(accessToken, onSuccess);
    } finally {
      loginLoading.value = false;
    }
  }

  async function authSmsLogin(
    params: Parameters<typeof smsLoginApi>[0],
    onSuccess?: () => Promise<void> | void,
  ) {
    try {
      loginLoading.value = true;
      const { accessToken } = await smsLoginApi(params);
      return await completeLogin(accessToken, onSuccess);
    } finally {
      loginLoading.value = false;
    }
  }

  async function authTenantRegister(
    params: Parameters<typeof registerTenantApi>[0],
    onSuccess?: () => Promise<void> | void,
  ) {
    try {
      loginLoading.value = true;
      const { accessToken } = await registerTenantApi(params);
      return await completeLogin(accessToken, onSuccess);
    } finally {
      loginLoading.value = false;
    }
  }

  async function logout(redirect: boolean = true) {
    try {
      await logoutApi();
    } catch {
      // 不做任何处理
    }
    resetAllStores();
    accessStore.setLoginExpired(false);

    // 回登录页带上当前路由地址
    await router.replace({
      path: LOGIN_PATH,
      query: redirect
        ? {
            redirect: encodeURIComponent(router.currentRoute.value.fullPath),
          }
        : {},
    });
  }

  async function fetchUserInfo() {
    const userInfo = await getUserInfoApi();
    userStore.setUserInfo(userInfo);
    return userInfo;
  }

  async function switchTenant(tenantId: string) {
    const { accessToken } = await switchTenantApi({ tenant_id: tenantId });
    accessStore.setAccessToken(accessToken);
    const homePath =
      userStore.userInfo?.homePath || preferences.app.defaultHomePath;
    window.location.assign(router.resolve(homePath).href);
  }

  function $reset() {
    loginLoading.value = false;
  }

  return {
    $reset,
    authEnterpriseOidcLogin,
    authLogin,
    authSmsLogin,
    authTenantRegister,
    fetchUserInfo,
    loginLoading,
    logout,
    switchTenant,
  };
});
