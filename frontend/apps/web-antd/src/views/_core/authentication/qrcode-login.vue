<script lang="ts" setup>
import { computed, onBeforeUnmount, onMounted, ref } from 'vue';

import { AuthenticationQrCodeLogin } from '@vben/common-ui';

import {
  createQrCodeLoginApi,
  getQrCodeLoginStatusApi,
  type AuthApi,
} from '#/api';
import { useAuthStore } from '#/store';

defineOptions({ name: 'QrCodeLogin' });

const POLL_INTERVAL_MS = 1500;
const authStore = useAuthStore();
const tenantCode =
  import.meta.env.VITE_APP_DEFAULT_TENANT_CODE || 'default';
const challenge = ref<AuthApi.QrLoginChallenge>();
const remainingSeconds = ref(0);
const loading = ref(false);
const expired = ref(false);
const status = ref<'confirmed' | 'pending'>('pending');
const errorMessage = ref('');
let countdownTimer: ReturnType<typeof setInterval> | undefined;
let pollTimer: ReturnType<typeof setTimeout> | undefined;
let requestVersion = 0;

const qrPayload = computed(() => {
  if (!challenge.value) return '';
  const url = new URL('/auth/qrcode-confirm', window.location.origin);
  url.searchParams.set('challenge_id', challenge.value.challenge_id);
  url.searchParams.set('scan_token', challenge.value.scan_token);
  return url.toString();
});

const description = computed(() => {
  if (expired.value) return '二维码已过期，请重新获取';
  if (status.value === 'confirmed') return '已确认，正在登录';
  if (errorMessage.value) return errorMessage.value;
  return "扫码后点击 '确认'，即可完成登录";
});

function clearTimers() {
  if (pollTimer) clearTimeout(pollTimer);
  if (countdownTimer) clearInterval(countdownTimer);
  pollTimer = undefined;
  countdownTimer = undefined;
}

function markExpired() {
  expired.value = true;
  clearTimers();
}

async function pollStatus(version: number) {
  if (
    version !== requestVersion ||
    !challenge.value ||
    expired.value ||
    status.value === 'confirmed'
  ) {
    return;
  }
  try {
    const result = await getQrCodeLoginStatusApi({
      challenge_id: challenge.value.challenge_id,
      poll_token: challenge.value.poll_token,
    });
    if (version !== requestVersion) return;
    status.value = result.status;
    if (result.status === 'confirmed') {
      clearTimers();
      await authStore.authQrCodeLogin({
        challenge_id: challenge.value.challenge_id,
        poll_token: challenge.value.poll_token,
      });
      return;
    }
  } catch (error: any) {
    if (version !== requestVersion) return;
    const code = error?.response?.data?.code;
    if (code === 'AUTH_QR_EXPIRED') {
      markExpired();
      return;
    }
    errorMessage.value = '暂时无法查询扫码状态，正在重试';
  }
  pollTimer = setTimeout(() => void pollStatus(version), POLL_INTERVAL_MS);
}

async function createChallenge() {
  const version = ++requestVersion;
  clearTimers();
  loading.value = true;
  expired.value = false;
  errorMessage.value = '';
  status.value = 'pending';
  challenge.value = undefined;
  try {
    const result = await createQrCodeLoginApi({
      tenant_code: tenantCode,
    });
    if (version !== requestVersion) return;
    challenge.value = result;
    remainingSeconds.value = result.expires_in;
    countdownTimer = setInterval(() => {
      remainingSeconds.value = Math.max(0, remainingSeconds.value - 1);
      if (remainingSeconds.value === 0) markExpired();
    }, 1000);
    pollTimer = setTimeout(() => void pollStatus(version), POLL_INTERVAL_MS);
  } catch (error: any) {
    if (version !== requestVersion) return;
    errorMessage.value =
      error?.response?.data?.message || '二维码创建失败，请稍后重试';
  } finally {
    if (version === requestVersion) loading.value = false;
  }
}

onMounted(() => void createChallenge());
onBeforeUnmount(() => {
  requestVersion += 1;
  clearTimers();
});
</script>

<template>
  <AuthenticationQrCodeLogin
    :description="description"
    :expired="expired"
    :loading="loading || authStore.loginLoading"
    :qr-code-value="qrPayload"
    @refresh="createChallenge"
  />
</template>
