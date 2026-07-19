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

function formatPrice(value: null | number | undefined) {
  return new Intl.NumberFormat(undefined, {
    currency: 'CNY',
    style: 'currency',
  }).format(value ?? 0);
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
      componentProps: { class: 'w-full', min: 0, precision: 0 },
      defaultValue: 0,
      fieldName: 'type',
      label: $t('system.tenantPlan.type'),
    },
    {
      component: 'InputNumber',
      componentProps: { class: 'w-full', min: 0, precision: 2 },
      defaultValue: 0,
      fieldName: 'price',
      label: $t('system.tenantPlan.price'),
    },
    {
      component: 'Input',
      fieldName: 'logo',
      label: $t('system.tenantPlan.logo'),
    },
    {
      component: 'InputNumber',
      componentProps: { class: 'w-full', min: 0, precision: 0 },
      defaultValue: 1,
      fieldName: 'order_num',
      label: $t('system.tenantPlan.orderNum'),
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
      component: 'RadioGroup',
      componentProps: {
        buttonStyle: 'solid',
        options: [
          { label: $t('system.tenantPlan.unpublished'), value: 0 },
          { label: $t('system.tenantPlan.published'), value: 1 },
        ],
        optionType: 'button',
      },
      defaultValue: 0,
      fieldName: 'published',
      label: $t('system.tenantPlan.publishStatus'),
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
    {
      component: 'Textarea',
      componentProps: { maxLength: 500, rows: 3, showCount: true },
      fieldName: 'description',
      formItemClass: 'col-span-2',
      label: $t('system.common.description'),
    },
    {
      component: 'Textarea',
      componentProps: { maxLength: 500, rows: 3, showCount: true },
      fieldName: 'remark',
      formItemClass: 'col-span-2',
      label: $t('system.tenantPlan.remark'),
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
    {
      component: 'Select',
      componentProps: {
        allowClear: true,
        options: [
          { label: $t('system.tenantPlan.unpublished'), value: 0 },
          { label: $t('system.tenantPlan.published'), value: 1 },
        ],
      },
      fieldName: 'published',
      label: $t('system.tenantPlan.publishStatus'),
    },
  ];
}

export function useColumns(
  onActionClick: OnActionClickFn<TenantPlanRecord>,
): VxeTableGridColumns<TenantPlanRecord> {
  return [
    {
      field: 'name',
      fixed: 'left',
      minWidth: 160,
      title: $t('system.tenantPlan.planName'),
    },
    { field: 'code', minWidth: 140, title: $t('system.tenantPlan.planCode') },
    {
      field: 'price',
      formatter: ({ cellValue }) => formatPrice(cellValue),
      title: $t('system.tenantPlan.price'),
      width: 110,
    },
    {
      cellRender: {
        name: 'CellTag',
        options: [
          {
            color: 'default',
            label: $t('system.tenantPlan.unpublished'),
            value: 0,
          },
          {
            color: 'success',
            label: $t('system.tenantPlan.published'),
            value: 1,
          },
        ],
      },
      field: 'published',
      title: $t('system.tenantPlan.publishStatus'),
      width: 100,
    },
    {
      field: 'max_members',
      formatter: ({ cellValue }) => formatLimit(cellValue),
      title: $t('system.tenantPlan.maxMembers'),
      width: 110,
    },
    {
      field: 'menu_count',
      title: $t('system.tenantPlan.menuCount'),
      width: 100,
    },
    {
      field: 'subscription_num',
      title: $t('system.tenantPlan.subscriptionNum'),
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
          maxVisible: 2,
          moreText: $t('system.common.more'),
          nameField: 'name',
          onClick: onActionClick,
        },
        name: 'CellOperation',
        options: [
          {
            auth: 'platform:plan:grant-menu',
            code: 'grant-menu',
            disabled: (row: TenantPlanRecord) => row.is_default,
            text: $t('system.tenantPlan.grantMenu'),
          },
          {
            auth: 'platform:plan:sync-menu',
            code: 'sync-menu',
            text: $t('system.tenantPlan.syncMenu'),
          },
          {
            auth: 'platform:plan:update',
            code: 'edit',
            disabled: (row: TenantPlanRecord) => row.is_default,
          },
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
      width: 210,
    },
  ];
}
