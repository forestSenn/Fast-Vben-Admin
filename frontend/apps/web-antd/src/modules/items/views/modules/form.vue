<script lang="ts" setup>
import type { ItemPayload, ItemRecord } from '#/modules/items/api/items';

import { computed, ref } from 'vue';

import { useVbenDrawer } from '@vben/common-ui';

import { createItemApi, updateItemApi } from '#/modules/items/api/items';

import { useVbenForm } from '#/adapter/form';
import { $t } from '#/locales';

import { useFormSchema } from '../data';

const emits = defineEmits<{ success: [] }>();

const itemId = ref<string>();

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
      if (itemId.value) {
        await updateItemApi(itemId.value, values as ItemPayload);
      } else {
        await createItemApi(values as ItemPayload);
      }
      emits('success');
      drawerApi.close();
    } catch {
      drawerApi.unlock();
    }
  },
  onOpenChange(isOpen) {
    if (!isOpen) return;

    const data = drawerApi.getData<ItemRecord>();
    formApi.resetForm();
    itemId.value = data?.id;

    if (data) {
      formApi.setValues(data);
    }
  },
});

const drawerTitle = computed(() =>
  itemId.value ? $t('business.edit') : $t('business.createModal'),
);
</script>

<template>
  <Drawer :title="drawerTitle" class="w-[560px]">
    <Form />
  </Drawer>
</template>
