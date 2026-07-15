import type { VbenFormSchema } from '#/adapter/form';
import type { OnActionClickFn, VxeTableGridColumns } from '#/adapter/vxe-table';
import type { TenantTemplateRecord } from '#/api';

import { z } from '#/adapter/form';
import { $t } from '#/locales';

const seedFields = [
  'seed_posts',
  'seed_dictionaries',
  'seed_settings',
  'seed_storage_channels',
  'seed_message_templates',
  'seed_sms_channels',
  'seed_mail_accounts',
] as const;

export function useFormSchema(): VbenFormSchema[] {
  return [
    {
      component: 'Input',
      fieldName: 'name',
      label: $t('system.tenantTemplate.templateName'),
      rules: z.string().min(1).max(100),
    },
    {
      component: 'Input',
      fieldName: 'code',
      label: $t('system.tenantTemplate.templateCode'),
      rules: z.string().min(1).max(100),
    },
    {
      component: 'Input',
      defaultValue: 'root',
      fieldName: 'root_department_code',
      label: $t('system.tenantTemplate.rootDepartmentCode'),
      rules: z.string().min(1).max(100),
    },
    {
      component: 'Input',
      defaultValue: '总部',
      fieldName: 'root_department_name',
      label: $t('system.tenantTemplate.rootDepartmentName'),
      rules: z.string().min(1).max(100),
    },
    {
      component: 'Textarea',
      componentProps: { maxLength: 500, rows: 3, showCount: true },
      fieldName: 'description',
      label: $t('system.common.description'),
    },
    ...seedFields.map(
      (fieldName): VbenFormSchema => ({
        component: 'Switch',
        defaultValue: true,
        fieldName,
        label: $t(`system.tenantTemplate.${fieldName}`),
      }),
    ),
    {
      component: 'Switch',
      defaultValue: false,
      fieldName: 'is_default',
      label: $t('system.tenantTemplate.defaultTemplate'),
    },
    {
      component: 'Switch',
      defaultValue: true,
      fieldName: 'is_active',
      label: $t('system.tenantTemplate.status'),
    },
  ];
}

export function useGridFormSchema(): VbenFormSchema[] {
  return [
    {
      component: 'Input',
      fieldName: 'keyword',
      label: $t('system.common.keyword'),
    },
    {
      component: 'Select',
      componentProps: {
        allowClear: true,
        options: [
          { label: $t('common.enabled'), value: true },
          { label: $t('common.disabled'), value: false },
        ],
      },
      fieldName: 'is_active',
      label: $t('system.tenantTemplate.status'),
    },
  ];
}

export function useColumns(
  onActionClick: OnActionClickFn<TenantTemplateRecord>,
): VxeTableGridColumns<TenantTemplateRecord> {
  return [
    {
      field: 'name',
      minWidth: 180,
      title: $t('system.tenantTemplate.templateName'),
    },
    {
      field: 'code',
      minWidth: 150,
      title: $t('system.tenantTemplate.templateCode'),
    },
    {
      field: 'root_department_name',
      minWidth: 160,
      title: $t('system.tenantTemplate.rootDepartmentName'),
    },
    {
      field: 'is_default',
      formatter: ({ cellValue }) =>
        cellValue ? $t('system.tenantTemplate.defaultTemplate') : '-',
      title: $t('system.tenantTemplate.defaultTemplate'),
      width: 110,
    },
    {
      cellRender: { name: 'CellTag' },
      field: 'is_active',
      title: $t('system.tenantTemplate.status'),
      width: 90,
    },
    {
      align: 'center',
      cellRender: {
        attrs: { nameField: 'name', onClick: onActionClick },
        name: 'CellOperation',
        options: [
          { auth: 'platform:template:update', code: 'edit' },
          {
            auth: 'platform:template:delete',
            code: 'delete',
            disabled: (row: TenantTemplateRecord) => row.is_default,
          },
        ],
      },
      field: 'operation',
      fixed: 'right',
      title: $t('system.common.operation'),
      width: 140,
    },
  ];
}
