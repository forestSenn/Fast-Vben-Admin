<script lang="ts" setup>
import { ref } from 'vue';

import { IconifyIcon } from '@vben/icons';

import { Button } from 'ant-design-vue';

import DocumentAttachments from '#/modules/erp/components/document-attachments.vue';

defineProps<{ documentId: string; documentType: string }>();

const open = ref(false);
</script>

<template>
  <DocumentAttachments v-model:open="open" :document-id="documentId" :document-type="documentType" />
  <Button v-access:code="'erp:attachment:list'" class="gap-1" size="small" type="link" @click="open = true">
    <IconifyIcon class="size-4" icon="lucide:paperclip" />
    <span>附件</span>
  </Button>
</template>
