<script lang="ts" setup>
import type {
  TenantTemplateCreatePayload,
  TenantTemplateRecord,
  TenantTemplateUpdatePayload,
} from '#/api';

import { computed, ref } from 'vue';

import { useVbenDrawer } from '@vben/common-ui';

import { useVbenForm } from '#/adapter/form';
import { createTenantTemplateApi, updateTenantTemplateApi } from '#/api';
import { $t } from '#/locales';

import { useFormSchema } from '../data';

const emits = defineEmits<{ success: [] }>();
const templateId = ref<string>();

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
      name: values.name,
      root_department_code: values.root_department_code,
      root_department_name: values.root_department_name,
      seed_dictionaries: values.seed_dictionaries ?? true,
      seed_mail_accounts: values.seed_mail_accounts ?? true,
      seed_message_templates: values.seed_message_templates ?? true,
      seed_posts: values.seed_posts ?? true,
      seed_settings: values.seed_settings ?? true,
      seed_sms_channels: values.seed_sms_channels ?? true,
      seed_storage_channels: values.seed_storage_channels ?? true,
    };

    drawerApi.lock();
    try {
      await (templateId.value
        ? updateTenantTemplateApi(
            templateId.value,
            payload as TenantTemplateUpdatePayload,
          )
        : createTenantTemplateApi(payload as TenantTemplateCreatePayload));
      emits('success');
      drawerApi.close();
    } catch {
      drawerApi.unlock();
    }
  },
  onOpenChange(isOpen) {
    if (!isOpen) return;
    const data = drawerApi.getData<TenantTemplateRecord>();
    formApi.resetForm();
    templateId.value = data?.id;
    if (data) formApi.setValues(data);
  },
});

const drawerTitle = computed(() =>
  templateId.value
    ? $t('system.tenantTemplate.edit')
    : $t('system.tenantTemplate.create'),
);
</script>

<template>
  <Drawer :title="drawerTitle" class="w-[560px]">
    <Form />
  </Drawer>
</template>
