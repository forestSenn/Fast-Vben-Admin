<script lang="ts" setup>
import { reactive, ref } from 'vue';
import { useRoute, useRouter } from 'vue-router';

import { resetPasswordApi } from '#/api';

import {
  Button as AButton,
  Form as AForm,
  FormItem as AFormItem,
  InputPassword as AInputPassword,
  message,
} from 'ant-design-vue';

defineOptions({ name: 'ResetPassword' });

const route = useRoute();
const router = useRouter();
const loading = ref(false);

const formState = reactive({
  confirmPassword: '',
  newPassword: '',
});

async function handleSubmit() {
  const token = String(route.query.token || '');
  if (!token) {
    message.error('重置链接无效或已过期');
    return;
  }
  if (!formState.newPassword || formState.newPassword.length < 8) {
    message.warning('新密码至少 8 位');
    return;
  }
  if (formState.newPassword !== formState.confirmPassword) {
    message.warning('两次输入的密码不一致');
    return;
  }

  loading.value = true;
  try {
    await resetPasswordApi({
      new_password: formState.newPassword,
      token,
    });
    message.success('密码已重置，请重新登录');
    await router.push('/auth/login');
  } finally {
    loading.value = false;
  }
}
</script>

<template>
  <div @keydown.enter.prevent="handleSubmit">
    <div class="mb-8 text-center">
      <h2 class="text-2xl font-semibold">重置密码</h2>
      <p class="text-muted-foreground mt-2 text-sm">为你的账号设置新密码</p>
    </div>

    <a-form :model="formState" layout="vertical">
      <a-form-item label="新密码" required>
        <a-input-password
          v-model:value="formState.newPassword"
          autocomplete="new-password"
          placeholder="至少 8 位"
        />
      </a-form-item>
      <a-form-item label="确认密码" required>
        <a-input-password
          v-model:value="formState.confirmPassword"
          autocomplete="new-password"
          placeholder="再次输入新密码"
        />
      </a-form-item>
      <a-button
        block
        :loading="loading"
        type="primary"
        @click="handleSubmit"
      >
        重置密码
      </a-button>
    </a-form>
  </div>
</template>
