import type { VbenFormSchema } from '#/adapter/form';
import type { OnActionClickFn, VxeTableGridColumns } from '#/adapter/vxe-table';
import type { TenantPlanRecord } from '#/api';

import { z } from '#/adapter/form';
import { $t } from '#/locales';

function formatLimit(value: null | number | undefined) {
  return value === null || value === undefined
    ? $t('system.tenantPlan.unlimited')
    : value;
}

export function useFormSchema(): VbenFormSchema[] {
  return [
    {
      component: 'Input',
      fieldName: 'name',
      label: $t('system.tenantPlan.planName'),
      rules: z.string().min(1).max(100),
    },
    {
      component: 'Input',
      fieldName: 'code',
      label: $t('system.tenantPlan.planCode'),
      rules: z.string().min(1).max(100),
    },
    {
      component: 'InputNumber',
      componentProps: { class: 'w-full', min: 1, precision: 0 },
      fieldName: 'max_members',
      label: $t('system.tenantPlan.maxMembers'),
    },
    {
      component: 'InputNumber',
      componentProps: { class: 'w-full', min: 1, precision: 0 },
      fieldName: 'max_file_assets',
      label: $t('system.tenantPlan.maxFiles'),
    },
    {
      component: 'InputNumber',
      componentProps: { class: 'w-full', min: 1, precision: 0 },
      fieldName: 'max_storage_bytes',
      label: $t('system.tenantPlan.maxStorage'),
    },
    {
      component: 'Textarea',
      componentProps: { maxLength: 500, rows: 3, showCount: true },
      fieldName: 'description',
      label: $t('system.common.description'),
    },
    {
      component: 'Switch',
      defaultValue: false,
      fieldName: 'is_default',
      label: $t('system.tenantPlan.defaultPlan'),
    },
    {
      component: 'Switch',
      defaultValue: true,
      fieldName: 'is_active',
      label: $t('system.tenantPlan.status'),
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
      label: $t('system.tenantPlan.status'),
    },
  ];
}

export function useColumns(
  onActionClick: OnActionClickFn<TenantPlanRecord>,
): VxeTableGridColumns<TenantPlanRecord> {
  return [
    { field: 'name', minWidth: 160, title: $t('system.tenantPlan.planName') },
    { field: 'code', minWidth: 140, title: $t('system.tenantPlan.planCode') },
    {
      field: 'max_members',
      formatter: ({ cellValue }) => formatLimit(cellValue),
      title: $t('system.tenantPlan.maxMembers'),
      width: 110,
    },
    {
      field: 'max_file_assets',
      formatter: ({ cellValue }) => formatLimit(cellValue),
      title: $t('system.tenantPlan.maxFiles'),
      width: 110,
    },
    {
      field: 'max_storage_bytes',
      formatter: ({ cellValue }) => formatLimit(cellValue),
      title: $t('system.tenantPlan.maxStorage'),
      width: 150,
    },
    {
      field: 'is_default',
      formatter: ({ cellValue }) =>
        cellValue ? $t('system.tenantPlan.defaultPlan') : '-',
      title: $t('system.tenantPlan.defaultPlan'),
      width: 100,
    },
    {
      cellRender: { name: 'CellTag' },
      field: 'is_active',
      title: $t('system.tenantPlan.status'),
      width: 90,
    },
    {
      align: 'center',
      cellRender: {
        attrs: {
          nameField: 'name',
          onClick: onActionClick,
        },
        name: 'CellOperation',
        options: [
          { auth: 'platform:plan:update', code: 'edit' },
          {
            auth: 'platform:plan:delete',
            code: 'delete',
            disabled: (row: TenantPlanRecord) => row.is_default,
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
