import type { VbenFormSchema } from '#/adapter/form';
import type { VxeTableGridColumns } from '#/adapter/vxe-table';
import type { LoginLogRecord } from '#/api';

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
          { label: $t('system.common.success'), value: 'success' },
          { label: $t('system.common.fail'), value: 'fail' },
        ],
      },
      fieldName: 'status',
      label: $t('logs.login.status'),
    },
  ];
}

export function useColumns(): VxeTableGridColumns<LoginLogRecord> {
  return [
    {
      field: 'email',
      minWidth: 180,
      title: $t('logs.login.user'),
    },
    {
      field: 'ip',
      title: $t('logs.login.ip'),
      width: 140,
    },
    {
      cellRender: {
        name: 'CellTag',
        options: [
          { color: 'success', label: $t('system.common.success'), value: 'success' },
          { color: 'error', label: $t('system.common.fail'), value: 'fail' },
        ],
      },
      field: 'status',
      title: $t('logs.login.status'),
      width: 90,
    },
    {
      field: 'failure_reason',
      minWidth: 160,
      showOverflow: true,
      title: $t('logs.login.failureReason'),
    },
    {
      field: 'user_agent',
      minWidth: 200,
      showOverflow: true,
      title: $t('logs.login.userAgent'),
    },
    {
      field: 'created_at',
      title: $t('logs.login.createdAt'),
      width: 180,
    },
  ];
}
