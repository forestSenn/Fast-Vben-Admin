import type { VbenFormSchema } from '#/adapter/form';
import type { VxeTableGridColumns } from '#/adapter/vxe-table';
import type { MailLogRecord } from '#/api';

export function useGridFormSchema(): VbenFormSchema[] {
  return [
    {
      component: 'Input',
      componentProps: {
        placeholder: '收件人邮箱',
      },
      fieldName: 'to_email',
      label: '收件人',
    },
    {
      component: 'Input',
      componentProps: {
        placeholder: '主题 / 模板编码',
      },
      fieldName: 'keyword',
      label: '关键词',
    },
    {
      component: 'Input',
      componentProps: {
        placeholder: '发送状态',
      },
      fieldName: 'send_status',
      label: '发送状态',
    },
  ];
}

export function useColumns(): VxeTableGridColumns<MailLogRecord> {
  return [
    {
      field: 'to_email',
      minWidth: 180,
      title: '收件人',
    },
    {
      field: 'title',
      minWidth: 200,
      title: '主题',
    },
    {
      field: 'template_name',
      minWidth: 150,
      title: '模板名称',
    },
    {
      field: 'send_status',
      title: '发送状态',
      width: 110,
    },
    {
      field: 'send_message',
      minWidth: 220,
      title: '发送结果',
    },
    {
      field: 'sent_at',
      title: '发送时间',
      width: 180,
    },
    {
      field: 'created_at',
      title: '创建时间',
      width: 180,
    },
  ];
}
