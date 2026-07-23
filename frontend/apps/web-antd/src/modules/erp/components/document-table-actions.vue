<script lang="ts" setup>
import { VbenTableAction } from '#/adapter/vxe-table';

import DocumentAttachmentButton from './document-attachment-button.vue';

const props = withDefaults(
  defineProps<{
    approveImpact?: string;
    approvePermission: string;
    deletePermission: string;
    documentId: string;
    documentNo?: string;
    documentType: string;
    reversePermission: string;
    status: string;
    updatePermission: string;
  }>(),
  {
    approveImpact: '审批后将立即记账，确认继续吗？',
    documentNo: '',
  },
);

const emit = defineEmits<{
  approve: [];
  delete: [];
  edit: [];
  reverse: [];
}>();
</script>

<template>
  <div class="flex items-center justify-center gap-1">
    <DocumentAttachmentButton
      :document-id="documentId"
      :document-type="documentType"
    />
    <VbenTableAction
      :actions="[
        {
          auth: [props.updatePermission],
          icon: 'lucide:square-pen',
          ifShow: () => props.status === 'draft',
          onClick: () => emit('edit'),
          text: '编辑',
          variant: 'link',
        },
        {
          auth:
            props.status === 'draft'
              ? [props.approvePermission]
              : [props.reversePermission],
          icon: 'lucide:clipboard-check',
          onClick:
            props.status === 'draft' ? undefined : () => emit('reverse'),
          popConfirm:
            props.status === 'draft'
              ? {
                  cancelText: '取消',
                  confirm: () => emit('approve'),
                  okText: '确认',
                  title: props.approveImpact,
                }
              : undefined,
          text: props.status === 'draft' ? '审批' : '反审批',
          variant: 'link',
        },
        {
          auth: [props.deletePermission],
          danger: true,
          icon: 'lucide:trash-2',
          ifShow: () => props.status === 'draft',
          popConfirm: {
            cancelText: '取消',
            confirm: () => emit('delete'),
            okText: '确认',
            title: `确认删除草稿单据${props.documentNo ? ` ${props.documentNo}` : ''}吗？`,
          },
          text: '删除',
          variant: 'link',
        },
      ]"
    />
  </div>
</template>
