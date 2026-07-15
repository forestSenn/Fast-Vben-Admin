<script lang="ts" setup>
import type { VbenFormSchema } from '@vben/common-ui';
import type { Recordable } from '@vben/types';

import { computed, ref } from 'vue';

import { AuthenticationCodeLogin, z } from '@vben/common-ui';
import { $t } from '@vben/locales';

import { message } from 'ant-design-vue';

import { sendLoginSmsCodeApi } from '#/api';
import { useAuthStore } from '#/store';

defineOptions({ name: 'CodeLogin' });

const authStore = useAuthStore();
const loginRef = ref<InstanceType<typeof AuthenticationCodeLogin>>();
const sending = ref(false);
const CODE_LENGTH = 6;
const defaultTenantCode =
  import.meta.env.VITE_APP_DEFAULT_TENANT_CODE || 'default';

async function handleSendCode() {
  const formApi = loginRef.value?.getFormApi();
  if (!formApi) {
    return;
  }
  await formApi.validateField('tenant_code');
  await formApi.validateField('mobile');
  if (
    !(await formApi.isFieldValid('tenant_code')) ||
    !(await formApi.isFieldValid('mobile'))
  ) {
    return;
  }

  const values = await formApi.getValues();
  sending.value = true;
  try {
    const result = await sendLoginSmsCodeApi({
      mobile: String(values.mobile),
      scene: 'login',
      tenant_code: String(values.tenant_code),
    });
    if (result.debug_code) {
      await formApi.setFieldValue('code', result.debug_code);
      message.success('调试验证码已自动填入');
    } else {
      message.success('验证码已发送');
    }
  } finally {
    sending.value = false;
  }
}

const formSchema = computed((): VbenFormSchema[] => [
  {
    component: 'VbenInput',
    componentProps: {
      autocomplete: 'organization',
      placeholder: '请输入租户编码',
    },
    fieldName: 'tenant_code',
    label: '租户',
    rules: z
      .string()
      .min(1, { message: '请输入租户编码' })
      .max(100, { message: '租户编码不能超过 100 个字符' })
      .default(defaultTenantCode),
  },
  {
    component: 'VbenInput',
    componentProps: {
      autocomplete: 'tel',
      inputmode: 'numeric',
      maxlength: 11,
      placeholder: $t('authentication.mobile'),
    },
    fieldName: 'mobile',
    label: $t('authentication.mobile'),
    rules: z
      .string()
      .min(1, { message: $t('authentication.mobileTip') })
      .refine((value) => /^1[3-9]\d{9}$/.test(value), {
        message: $t('authentication.mobileErrortip'),
      }),
  },
  {
    component: 'VbenPinInput',
    componentProps: {
      codeLength: CODE_LENGTH,
      createText: (countdown: number) =>
        countdown > 0
          ? $t('authentication.sendText', [countdown])
          : $t('authentication.sendCode'),
      handleSendCode,
      loading: sending.value,
      maxTime: 60,
      placeholder: $t('authentication.code'),
    },
    fieldName: 'code',
    label: $t('authentication.code'),
    rules: z.string().length(CODE_LENGTH, {
      message: $t('authentication.codeTip', [CODE_LENGTH]),
    }),
  },
]);

async function handleLogin(values: Recordable<any>) {
  await authStore.authSmsLogin({
    code: String(values.code),
    mobile: String(values.mobile),
    tenant_code: String(values.tenant_code),
  });
}
</script>

<template>
  <AuthenticationCodeLogin
    ref="loginRef"
    :form-schema="formSchema"
    :loading="authStore.loginLoading"
    @submit="handleLogin"
  />
</template>
