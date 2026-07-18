import type { VbenFormSchema } from '#/adapter/form';
import type { VxeTableGridColumns } from '#/adapter/vxe-table';
import type { SmsLogRecord } from '#/api';

export function useGridFormSchema(): VbenFormSchema[] {
  return [
    {
      component: 'Input',
      componentProps: {
        placeholder: '手机号',
      },
      fieldName: 'mobile',
      label: '手机号',
    },
    {
      component: 'Input',
      componentProps: {
        placeholder: '模板编码 / 内容',
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
    {
      component: 'Input',
      componentProps: {
        placeholder: '回执状态',
      },
      fieldName: 'receive_status',
      label: '回执状态',
    },
  ];
}

export function useColumns(): VxeTableGridColumns<SmsLogRecord> {
  return [
    {
      field: 'mobile',
      minWidth: 130,
      title: '手机号',
    },
    {
      field: 'template_name',
      minWidth: 150,
      title: '模板名称',
    },
    {
      field: 'template_code',
      minWidth: 140,
      title: '模板编码',
    },
    {
      field: 'send_status',
      title: '发送状态',
      width: 110,
    },
    {
      field: 'receive_status',
      title: '回执状态',
      width: 110,
    },
    {
      field: 'api_send_message',
      minWidth: 200,
      title: '发送结果',
    },
    {
      field: 'sent_at',
      title: '发送时间',
      width: 180,
    },
    {
      field: 'received_at',
      title: '回执时间',
      width: 180,
    },
  ];
}
