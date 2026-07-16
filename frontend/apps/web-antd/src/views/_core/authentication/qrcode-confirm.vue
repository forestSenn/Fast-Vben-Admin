<script lang="ts" setup>
import { computed, onMounted, ref } from 'vue';
import { useRoute, useRouter } from 'vue-router';

import { LOGIN_PATH } from '@vben/constants';
import { useAccessStore, useUserStore } from '@vben/stores';

import { Button, Result } from 'ant-design-vue';

import { confirmQrCodeLoginApi } from '#/api';
import { useAuthStore } from '#/store';

defineOptions({ name: 'QrCodeLoginConfirm' });

const route = useRoute();
const router = useRouter();
const authStore = useAuthStore();
const accessStore = useAccessStore();
const userStore = useUserStore();
const submitting = ref(false);
const confirmed = ref(false);
const errorMessage = ref('');

const challengeId = computed(() => String(route.query.challenge_id || ''));
const scanToken = computed(() => String(route.query.scan_token || ''));
const hasValidParameters = computed(
  () => challengeId.value.length > 0 && scanToken.value.length >= 32,
);
const isLoggedIn = computed(() => Boolean(accessStore.accessToken));
const accountName = computed(
  () => userStore.userInfo?.realName || userStore.userInfo?.username || '当前账号',
);

function goToLogin() {
  router.push({
    path: LOGIN_PATH,
    query: { redirect: encodeURIComponent(route.fullPath) },
  });
}

async function confirmLogin() {
  if (!hasValidParameters.value || !isLoggedIn.value) return;
  submitting.value = true;
  errorMessage.value = '';
  try {
    await confirmQrCodeLoginApi({
      challenge_id: challengeId.value,
      scan_token: scanToken.value,
    });
    confirmed.value = true;
  } catch (error: any) {
    errorMessage.value =
      error?.response?.data?.message || '确认失败，请重新扫描二维码';
  } finally {
    submitting.value = false;
  }
}

onMounted(async () => {
  if (isLoggedIn.value && !userStore.userInfo) {
    try {
      await authStore.fetchUserInfo();
    } catch {
      // The request interceptor handles an expired login session.
    }
  }
});
</script>

<template>
  <Result
    v-if="!hasValidParameters"
    status="error"
    sub-title="二维码内容不完整，请返回电脑端重新获取"
    title="无效的二维码"
  >
    <template #extra>
      <Button type="primary" @click="router.push(LOGIN_PATH)">返回登录</Button>
    </template>
  </Result>

  <Result
    v-else-if="!isLoggedIn"
    status="info"
    sub-title="登录后将自动返回当前确认页面"
    title="请先登录账号"
  >
    <template #extra>
      <Button type="primary" @click="goToLogin">前往登录</Button>
    </template>
  </Result>

  <Result
    v-else-if="confirmed"
    status="success"
    sub-title="电脑端正在完成登录，本页面可以关闭"
    title="登录已确认"
  >
    <template #extra>
      <Button type="primary" @click="router.push('/dashboard')">进入系统</Button>
    </template>
  </Result>

  <Result
    v-else
    status="info"
    :sub-title="`将允许电脑端以 ${accountName} 登录`"
    title="确认扫码登录"
  >
    <template #extra>
      <div class="flex flex-col gap-2 sm:flex-row sm:justify-center">
        <Button :loading="submitting" type="primary" @click="confirmLogin">
          确认登录
        </Button>
        <Button @click="router.push('/dashboard')">取消</Button>
      </div>
      <p v-if="errorMessage" class="mt-4 text-sm text-destructive">
        {{ errorMessage }}
      </p>
    </template>
  </Result>
</template>
