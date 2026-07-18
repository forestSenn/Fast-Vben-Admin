<script setup lang="ts">
import type { Recordable } from '@vben/types';
import type { VbenFormSchema } from '#/adapter/form';

import { ref } from 'vue';

import { message } from 'ant-design-vue';

import { useVbenForm, z } from '#/adapter/form';
import { updateCurrentPasswordApi } from '#/api';

const saving = ref(false);

const [Form] = useVbenForm({
  commonConfig: {
    labelWidth: 120,
  },
  schema: [
    {
      fieldName: 'oldPassword',
      label: '旧密码',
      component: 'InputPassword',
      componentProps: {
        placeholder: '请输入旧密码',
      },
      rules: z
        .string({ required_error: '请输入旧密码' })
        .min(8, { message: '密码至少需要 8 位' })
        .max(128, { message: '密码不能超过 128 位' }),
    },
    {
      fieldName: 'newPassword',
      label: '新密码',
      component: 'InputPassword',
      componentProps: {
        placeholder: '请输入新密码',
      },
      dependencies: {
        rules(values) {
          return z
            .string({ required_error: '请输入新密码' })
            .min(8, { message: '密码至少需要 8 位' })
            .max(128, { message: '密码不能超过 128 位' })
            .refine((value) => value !== values.oldPassword, {
              message: '新密码不能与旧密码相同',
            });
        },
        triggerFields: ['newPassword', 'oldPassword'],
      },
    },
    {
      fieldName: 'confirmPassword',
      label: '确认密码',
      component: 'InputPassword',
      componentProps: {
        placeholder: '请再次输入新密码',
      },
      dependencies: {
        rules(values) {
          const { newPassword } = values;
          return z
            .string({ required_error: '请再次输入新密码' })
            .min(8, { message: '密码至少需要 8 位' })
            .max(128, { message: '密码不能超过 128 位' })
            .refine((value) => value === newPassword, {
              message: '两次输入的密码不一致',
            });
        },
        triggerFields: ['newPassword'],
      },
    },
  ] satisfies VbenFormSchema[],
  resetButtonOptions: {
    show: false,
  },
  submitButtonOptions: {
    content: '更新密码',
  },
  handleSubmit,
});

async function handleSubmit(values: Recordable<any>) {
  saving.value = true;
  try {
    await updateCurrentPasswordApi({
      current_password: String(values.oldPassword || ''),
      new_password: String(values.newPassword || ''),
    });
    message.success('密码修改成功');
  } finally {
    saving.value = false;
  }
}
</script>
<template>
  <div
    class="mt-4 w-full lg:w-1/3 2xl:w-1/2"
    :class="{ 'pointer-events-none opacity-60': saving }"
  >
    <Form />
  </div>
</template>
