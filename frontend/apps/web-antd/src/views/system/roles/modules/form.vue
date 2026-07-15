<script lang="ts" setup>
import type { RoleCreatePayload, RoleRecord, RoleUpdatePayload } from '#/api';

import { computed, ref } from 'vue';

import { useVbenDrawer } from '@vben/common-ui';

import { createRoleApi, updateRoleApi } from '#/api';

import { useVbenForm } from '#/adapter/form';

import { useFormSchema } from '../data';

const emits = defineEmits<{ success: [] }>();

const formData = ref<RoleRecord>();
const roleId = ref<string>();

const [Form, formApi] = useVbenForm({
  schema: useFormSchema(),
  showDefaultActions: false,
});

const [Drawer, drawerApi] = useVbenDrawer({
  async onConfirm() {
    const { valid } = await formApi.validate();
    if (!valid) return;

    const values = await formApi.getValues();
    drawerApi.lock();
    try {
      await (roleId.value
        ? updateRoleApi(roleId.value, values as RoleUpdatePayload)
        : createRoleApi(values as RoleCreatePayload));
      emits('success');
      drawerApi.close();
    } catch {
      drawerApi.unlock();
    }
  },
  onOpenChange(isOpen) {
    if (!isOpen) return;

    const data = drawerApi.getData<RoleRecord>();
    formApi.resetForm();
    formData.value = data;
    roleId.value = data?.id;

    if (data) {
      formApi.setValues(data);
    }
  },
});

const drawerTitle = computed(() => (roleId.value ? '编辑角色' : '新增角色'));
</script>

<template>
  <Drawer :title="drawerTitle">
    <Form />
  </Drawer>
</template>
