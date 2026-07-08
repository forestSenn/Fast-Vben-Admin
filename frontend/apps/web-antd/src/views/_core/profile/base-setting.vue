<script setup lang="ts">
import type { Recordable } from '@vben/types';

import type { VbenFormSchema } from '#/adapter/form';

import { computed, onMounted, ref } from 'vue';

import { ProfileBaseSetting } from '@vben/common-ui';
import { useUserStore } from '@vben/stores';

import { message } from 'ant-design-vue';

import {
  getCurrentUserApi,
  getUserInfoApi,
  updateCurrentUserApi,
} from '#/api';

const userStore = useUserStore();
const profileBaseSettingRef = ref();
const saving = ref(false);

const formSchema = computed((): VbenFormSchema[] => {
  return [
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
  ];
});

async function loadProfile() {
  const data = await getCurrentUserApi();
  profileBaseSettingRef.value.getFormApi().setValues({
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
  } finally {
    saving.value = false;
  }
}

onMounted(async () => {
  await loadProfile();
});
</script>
<template>
  <ProfileBaseSetting
    ref="profileBaseSettingRef"
    :class="{ 'pointer-events-none opacity-60': saving }"
    :form-schema="formSchema"
    @submit="handleSubmit"
  />
</template>
