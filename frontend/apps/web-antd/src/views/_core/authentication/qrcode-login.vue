<script lang="ts" setup>
import { useRouter } from 'vue-router';

import { LOGIN_PATH } from '@vben/constants';

import { Button, Result } from 'ant-design-vue';

defineOptions({ name: 'QrCodeLogin' });

const router = useRouter();
</script>

<template>
  <Result
    status="info"
    sub-title="扫码确认服务完成配置后即可使用"
    title="扫码登录尚未开放"
  >
    <template #extra>
      <Button type="primary" @click="router.push(LOGIN_PATH)">返回登录</Button>
    </template>
  </Result>
</template>
