<script lang="ts" setup>
import type { VbenFormSchema } from '@vben/common-ui';
import type { Recordable } from '@vben/types';

import { computed, h, onMounted, ref } from 'vue';
import { useRouter } from 'vue-router';

import { AuthenticationRegister, z } from '@vben/common-ui';
import { LOGIN_PATH } from '@vben/constants';
import { $t } from '@vben/locales';

import { Button, Result, message } from 'ant-design-vue';

import {
  getRegistrationStatusApi,
  sendLoginSmsCodeApi,
} from '#/api';
import { useAuthStore } from '#/store';

defineOptions({ name: 'Register' });

const authStore = useAuthStore();
const router = useRouter();
const registerRef = ref<InstanceType<typeof AuthenticationRegister>>();
const registrationEnabled = ref<boolean>();
const sending = ref(false);
const CODE_LENGTH = 6;
const platformTenantCode =
  import.meta.env.VITE_APP_DEFAULT_TENANT_CODE || 'default';

async function handleSendCode() {
  const formApi = registerRef.value?.getFormApi();
  if (!formApi) {
    return;
  }
  await formApi.validateField('mobile');
  if (!(await formApi.isFieldValid('mobile'))) {
    return;
  }
  const values = await formApi.getValues();
  sending.value = true;
  try {
    const result = await sendLoginSmsCodeApi({
      mobile: String(values.mobile),
      scene: 'register',
      tenant_code: platformTenantCode,
    });
    if (result.debug_code) {
      await formApi.setFieldValue('sms_code', result.debug_code);
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
    componentProps: { placeholder: '租户名称' },
    fieldName: 'tenant_name',
    label: '租户名称',
    rules: z.string().min(2, { message: '租户名称至少 2 个字符' }),
  },
  {
    component: 'VbenInput',
    componentProps: { placeholder: '租户编码，例如 acme' },
    fieldName: 'tenant_code',
    label: '租户编码',
    rules: z
      .string()
      .regex(/^[a-z][a-z0-9-]{2,31}$/, '请使用 3-32 位小写字母、数字或连字符'),
  },
  {
    component: 'VbenInput',
    componentProps: { autocomplete: 'name', placeholder: '管理员姓名' },
    fieldName: 'full_name',
    label: '管理员姓名',
    rules: z.string().min(1, { message: '请输入管理员姓名' }),
  },
  {
    component: 'VbenInput',
    componentProps: {
      autocomplete: 'email',
      placeholder: 'example@example.com',
    },
    fieldName: 'email',
    label: $t('authentication.email'),
    rules: z
      .string()
      .min(1, { message: $t('authentication.emailTip') })
      .email($t('authentication.emailValidErrorTip')),
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
    rules: z.string().refine((value) => /^1[3-9]\d{9}$/.test(value), {
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
    },
    fieldName: 'sms_code',
    label: $t('authentication.code'),
    rules: z.string().length(CODE_LENGTH, {
      message: $t('authentication.codeTip', [CODE_LENGTH]),
    }),
  },
  {
    component: 'VbenInputPassword',
    componentProps: {
      autocomplete: 'new-password',
      passwordStrength: true,
      placeholder: $t('authentication.password'),
    },
    fieldName: 'password',
    label: $t('authentication.password'),
    rules: z.string().min(8, { message: '密码至少 8 位' }),
  },
  {
    component: 'VbenInputPassword',
    componentProps: {
      autocomplete: 'new-password',
      placeholder: $t('authentication.confirmPassword'),
    },
    dependencies: {
      rules(values) {
        return z
          .string()
          .min(8, { message: '密码至少 8 位' })
          .refine((value) => value === values.password, {
            message: $t('authentication.confirmPasswordTip'),
          });
      },
      triggerFields: ['password'],
    },
    fieldName: 'confirmPassword',
    label: $t('authentication.confirmPassword'),
  },
  {
    component: 'VbenCheckbox',
    fieldName: 'agreePolicy',
    renderComponentContent: () => ({
      default: () =>
        h('span', [
          $t('authentication.agree'),
          h(
            'span',
            { class: 'ml-1 text-muted-foreground' },
            `${$t('authentication.privacyPolicy')} & ${$t('authentication.terms')}`,
          ),
        ]),
    }),
    rules: z.boolean().refine(Boolean, {
      message: $t('authentication.agreeTip'),
    }),
  },
]);

async function handleSubmit(values: Recordable<any>) {
  await authStore.authTenantRegister({
    email: String(values.email),
    full_name: String(values.full_name),
    mobile: String(values.mobile),
    password: String(values.password),
    sms_code: String(values.sms_code),
    tenant_code: String(values.tenant_code),
    tenant_name: String(values.tenant_name),
  });
}

onMounted(async () => {
  try {
    registrationEnabled.value = (await getRegistrationStatusApi()).enabled;
  } catch {
    registrationEnabled.value = false;
  }
});
</script>

<template>
  <AuthenticationRegister
    v-if="registrationEnabled"
    ref="registerRef"
    :form-schema="formSchema"
    :loading="authStore.loginLoading"
    class="pb-16"
    sub-title="创建租户并初始化管理员账号"
    title="创建租户"
    @submit="handleSubmit"
  />
  <Result
    v-else-if="registrationEnabled === false"
    status="403"
    sub-title="请联系平台管理员开通公开注册"
    title="公开注册未开放"
  >
    <template #extra>
      <Button type="primary" @click="router.push(LOGIN_PATH)">返回登录</Button>
    </template>
  </Result>
</template>
