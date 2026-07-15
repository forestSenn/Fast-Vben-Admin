<script lang="ts" setup>
import type {
  TenantPlanCreatePayload,
  TenantPlanRecord,
  TenantPlanUpdatePayload,
} from '#/api';

import { computed, ref } from 'vue';

import { useVbenDrawer } from '@vben/common-ui';

import { useVbenForm } from '#/adapter/form';
import { createTenantPlanApi, updateTenantPlanApi } from '#/api';
import { $t } from '#/locales';

import { useFormSchema } from '../data';

const emits = defineEmits<{ success: [] }>();
const planId = ref<string>();

const [Form, formApi] = useVbenForm({
  schema: useFormSchema(),
  showDefaultActions: false,
});

const [Drawer, drawerApi] = useVbenDrawer({
  async onConfirm() {
    const { valid } = await formApi.validate();
    if (!valid) return;
    const values = await formApi.getValues();
    const payload = {
      code: values.code,
      description: values.description || null,
      is_active: values.is_active ?? true,
      is_default: values.is_default ?? false,
      max_file_assets: values.max_file_assets ?? null,
      max_members: values.max_members ?? null,
      max_storage_bytes: values.max_storage_bytes ?? null,
      name: values.name,
    };

    drawerApi.lock();
    try {
      await (planId.value
        ? updateTenantPlanApi(planId.value, payload as TenantPlanUpdatePayload)
        : createTenantPlanApi(payload as TenantPlanCreatePayload));
      emits('success');
      drawerApi.close();
    } catch {
      drawerApi.unlock();
    }
  },
  onOpenChange(isOpen) {
    if (!isOpen) return;
    const data = drawerApi.getData<TenantPlanRecord>();
    formApi.resetForm();
    planId.value = data?.id;
    if (data) formApi.setValues(data);
  },
});

const drawerTitle = computed(() =>
  planId.value ? $t('system.tenantPlan.edit') : $t('system.tenantPlan.create'),
);
</script>

<template>
  <Drawer :title="drawerTitle" class="w-[560px]">
    <Form />
  </Drawer>
</template>
