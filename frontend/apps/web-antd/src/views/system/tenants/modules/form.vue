<script lang="ts" setup>
import type {
  TenantCreatePayload,
  TenantRecord,
  TenantUpdatePayload,
} from '#/api';

import { computed, ref } from 'vue';

import { useVbenDrawer } from '@vben/common-ui';

import { createTenantApi, updateTenantApi } from '#/api';
import { useVbenForm } from '#/adapter/form';
import { $t } from '#/locales';

import { useFormSchema } from '../data';

const emits = defineEmits<{ success: [] }>();

const tenantId = ref<string>();

const [Form, formApi] = useVbenForm({
  schema: useFormSchema(() => !!tenantId.value),
  showDefaultActions: false,
});

const [Drawer, drawerApi] = useVbenDrawer({
  async onConfirm() {
    const { valid } = await formApi.validate();
    if (!valid) return;

    const values = await formApi.getValues();
    const payload = {
      code: values.code,
      description: values.description || undefined,
      is_active: values.is_active ?? true,
      name: values.name,
      plan_id: values.plan_id,
      ...(!tenantId.value && {
        initialization_template_id: values.initialization_template_id,
      }),
    };

    drawerApi.lock();
    try {
      await (tenantId.value
        ? updateTenantApi(tenantId.value, payload as TenantUpdatePayload)
        : createTenantApi(payload as TenantCreatePayload));
      emits('success');
      drawerApi.close();
    } catch {
      drawerApi.unlock();
    }
  },
  onOpenChange(isOpen) {
    if (!isOpen) return;

    const data = drawerApi.getData<TenantRecord>();
    formApi.resetForm();
    tenantId.value = data?.id;
    if (data) {
      formApi.setValues({
        ...data,
        description: data.description || undefined,
      });
    }
  },
});

const drawerTitle = computed(() =>
  tenantId.value ? $t('system.tenant.edit') : $t('system.tenant.create'),
);
</script>

<template>
  <Drawer :title="drawerTitle" class="w-[560px]">
    <Form />
  </Drawer>
</template>
