import type { VbenFormSchema } from '#/adapter/form';
import type { OnActionClickFn, VxeTableGridColumns } from '#/adapter/vxe-table';
import type { TenantRecord } from '#/api';

import { z } from '#/adapter/form';
import {
  DEFAULT_TENANT_ID,
  listSimpleTenantPlansApi,
  listSimpleTenantTemplatesApi,
} from '#/api';
import { $t } from '#/locales';

export function useFormSchema(isEditing: () => boolean): VbenFormSchema[] {
  return [
    {
      component: 'Input',
      fieldName: 'name',
      label: $t('system.tenant.tenantName'),
      rules: z
        .string()
        .min(1, $t('ui.formRules.required', [$t('system.tenant.tenantName')]))
        .max(100),
    },
    {
      component: 'Input',
      fieldName: 'code',
      label: $t('system.tenant.tenantCode'),
      rules: z
        .string()
        .min(1, $t('ui.formRules.required', [$t('system.tenant.tenantCode')]))
        .max(100),
    },
    {
      component: 'ApiSelect',
      componentProps: {
        api: listSimpleTenantPlansApi,
        class: 'w-full',
        labelField: 'name',
        valueField: 'id',
      },
      fieldName: 'plan_id',
      label: $t('system.tenant.plan'),
      rules: z
        .string()
        .min(1, $t('ui.formRules.required', [$t('system.tenant.plan')])),
    },
    {
      component: 'Textarea',
      componentProps: {
        maxLength: 500,
        rows: 4,
        showCount: true,
      },
      fieldName: 'description',
      label: $t('system.tenant.description'),
    },
    {
      component: 'ApiSelect',
      componentProps: () => ({
        api: listSimpleTenantTemplatesApi,
        class: 'w-full',
        disabled: isEditing(),
        labelField: 'name',
        valueField: 'id',
      }),
      fieldName: 'initialization_template_id',
      label: $t('system.tenant.template'),
      rules: z
        .string()
        .min(1, $t('ui.formRules.required', [$t('system.tenant.template')])),
    },
    {
      component: 'Switch',
      defaultValue: true,
      fieldName: 'is_active',
      label: $t('system.tenant.status'),
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
      label: $t('system.tenant.status'),
    },
  ];
}

export function useColumns(
  onActionClick: OnActionClickFn<TenantRecord>,
  onStatusChange?: (
    newStatus: boolean,
    row: TenantRecord,
  ) => PromiseLike<boolean | undefined>,
): VxeTableGridColumns<TenantRecord> {
  return [
    {
      field: 'name',
      minWidth: 180,
      title: $t('system.tenant.tenantName'),
    },
    {
      field: 'code',
      minWidth: 160,
      title: $t('system.tenant.tenantCode'),
    },
    {
      field: 'plan_name',
      minWidth: 140,
      title: $t('system.tenant.plan'),
    },
    {
      field: 'initialization_template_name',
      minWidth: 150,
      title: $t('system.tenant.template'),
    },
    {
      cellRender: {
        attrs: {
          auth: 'platform:tenant:update',
          beforeChange: onStatusChange,
        },
        name: onStatusChange ? 'CellSwitch' : 'CellTag',
      },
      field: 'is_active',
      title: $t('system.tenant.status'),
      width: 100,
    },
    {
      field: 'description',
      minWidth: 220,
      showOverflow: true,
      title: $t('system.tenant.description'),
    },
    {
      field: 'created_at',
      title: $t('system.tenant.createTime'),
      width: 180,
    },
    {
      align: 'center',
      cellRender: {
        attrs: {
          nameField: 'name',
          nameTitle: $t('system.tenant.name'),
          onClick: onActionClick,
        },
        name: 'CellOperation',
        options: [
          {
            auth: 'platform:tenant:update',
            code: 'edit',
          },
          {
            auth: 'platform:tenant:delete',
            code: 'archive',
            disabled: (row: TenantRecord) =>
              row.id === DEFAULT_TENANT_ID || !row.is_active,
            text: $t('system.tenant.archive'),
          },
        ],
      },
      field: 'operation',
      fixed: 'right',
      title: $t('system.tenant.operation'),
      width: 150,
    },
  ];
}
