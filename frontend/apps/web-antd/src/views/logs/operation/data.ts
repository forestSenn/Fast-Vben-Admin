import type { VbenFormSchema } from '#/adapter/form';
import type { VxeTableGridColumns } from '#/adapter/vxe-table';
import type { OperationLogRecord } from '#/api';

import { $t } from '#/locales';

export function useGridFormSchema(): VbenFormSchema[] {
  return [
    {
      component: 'Input',
      fieldName: 'keyword',
      label: $t('logs.common.keyword'),
    },
    {
      component: 'Select',
      componentProps: {
        allowClear: true,
        options: [
          { label: 'GET', value: 'GET' },
          { label: 'POST', value: 'POST' },
          { label: 'PUT', value: 'PUT' },
          { label: 'PATCH', value: 'PATCH' },
          { label: 'DELETE', value: 'DELETE' },
        ],
      },
      fieldName: 'method',
      label: $t('logs.operation.requestMethod'),
    },
    {
      component: 'InputNumber',
      componentProps: {
        class: 'w-full',
        min: 100,
      },
      fieldName: 'status_code',
      label: $t('logs.operation.statusCode'),
    },
  ];
}

export function useColumns(): VxeTableGridColumns<OperationLogRecord> {
  return [
    {
      field: 'email',
      minWidth: 160,
      title: $t('logs.operation.user'),
    },
    {
      field: 'module',
      title: $t('logs.operation.module'),
      width: 120,
    },
    {
      field: 'action',
      title: $t('logs.operation.action'),
      width: 100,
    },
    {
      cellRender: {
        name: 'CellTag',
        options: [
          { color: 'processing', label: 'GET', value: 'GET' },
          { color: 'success', label: 'POST', value: 'POST' },
          { color: 'warning', label: 'PUT', value: 'PUT' },
          { color: 'warning', label: 'PATCH', value: 'PATCH' },
          { color: 'error', label: 'DELETE', value: 'DELETE' },
        ],
      },
      field: 'method',
      title: $t('logs.operation.method'),
      width: 90,
    },
    {
      field: 'path',
      minWidth: 220,
      showOverflow: true,
      title: $t('logs.operation.path'),
    },
    {
      field: 'status_code',
      title: $t('logs.operation.statusCode'),
      width: 90,
    },
    {
      field: 'duration_ms',
      title: $t('logs.operation.durationMs'),
      width: 100,
    },
    {
      field: 'ip',
      title: $t('logs.operation.ip'),
      width: 140,
    },
    {
      field: 'created_at',
      title: $t('logs.operation.createdAt'),
      width: 180,
    },
  ];
}
