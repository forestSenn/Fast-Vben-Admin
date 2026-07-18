<script setup lang="ts">
import type { Recordable } from '@vben/types';

import type { AuthApi } from '#/api';
import type { VbenFormSchema } from '#/adapter/form';

import { onMounted, ref, watch } from 'vue';

import { useUserStore } from '@vben/stores';

import { message } from 'ant-design-vue';

import { useVbenForm } from '#/adapter/form';
import { getUserInfoApi, updateCurrentUserApi } from '#/api';

const props = defineProps<{
  profile?: AuthApi.FastApiUser;
}>();

const emit = defineEmits<{
  (e: 'success'): void;
}>();

const userStore = useUserStore();
const saving = ref(false);

const [Form, formApi] = useVbenForm({
  commonConfig: {
    labelWidth: 70,
  },
  schema: [
    {
      fieldName: 'full_name',
      component: 'Input',
      label: '姓名',
    },
    {
      fieldName: 'email',
      component: 'Input',
      label: '邮箱',
    },
  ] satisfies VbenFormSchema[],
  resetButtonOptions: {
    show: false,
  },
  submitButtonOptions: {
    content: '更新基本信息',
  },
  handleSubmit,
});

function applyProfile(data?: AuthApi.FastApiUser) {
  if (!data) {
    return;
  }
  formApi.setValues({
    email: data.email,
    full_name: data.full_name || '',
  });
}

async function handleSubmit(values: Recordable<any>) {
  saving.value = true;
  try {
    await updateCurrentUserApi({
      email: String(values.email || ''),
      full_name: String(values.full_name || ''),
    });
    userStore.setUserInfo(await getUserInfoApi());
    message.success('个人资料已更新');
    emit('success');
  } finally {
    saving.value = false;
  }
}

onMounted(async () => {
  applyProfile(props.profile);
});

watch(
  () => props.profile,
  (profile) => {
    applyProfile(profile);
  },
  { deep: true },
);
</script>
<template>
  <div
    class="mt-4 w-full lg:w-1/2 2xl:w-2/5"
    :class="{ 'pointer-events-none opacity-60': saving }"
  >
    <Form />
  </div>
</template>
