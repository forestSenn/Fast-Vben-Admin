import type { VbenFormSchema } from '#/adapter/form';
import type { OnActionClickFn, VxeTableGridColumns } from '#/adapter/vxe-table';
import type { TenantRecord } from '#/api';

import { formatDateTime } from '@vben/utils';

import { z } from '#/adapter/form';
import {
  DEFAULT_TENANT_ID,
  listSimpleTenantPlansApi,
  listSimpleTenantTemplatesApi,
} from '#/api';
import { $t } from '#/locales';

export const lifecycleOptions = [
  {
    color: 'processing',
    label: $t('system.tenant.statusTrial'),
    value: 'trial',
  },
  {
    color: 'success',
    label: $t('system.tenant.statusFormal'),
    value: 'formal',
  },
  {
    color: 'warning',
    label: $t('system.tenant.statusFrozen'),
    value: 'frozen',
  },
  {
    color: 'error',
    label: $t('system.tenant.statusExpired'),
    value: 'expired',
  },
  {
    color: 'default',
    label: $t('system.tenant.statusArchived'),
    value: 'archived',
  },
];

function datePickerProps() {
  return {
    class: 'w-full',
    showTime: true,
    valueFormat: 'YYYY-MM-DDTHH:mm:ssZ',
  };
}

function sectionSchema(fieldName: string, title: string): VbenFormSchema {
  return {
    component: 'Divider',
    componentProps: { orientation: 'left', plain: true },
    fieldName,
    formItemClass: 'col-span-2',
    hideLabel: true,
    renderComponentContent: () => ({ default: () => title }),
  };
}

export function useFormSchema(isEditing: () => boolean): VbenFormSchema[] {
  return [
    sectionSchema('section_basic', $t('system.tenant.sectionBasic')),
    {
      component: 'Input',
      fieldName: 'name',
      label: $t('system.tenant.tenantName'),
      rules: z.string().min(1).max(100),
    },
    {
      component: 'Input',
      fieldName: 'code',
      label: $t('system.tenant.tenantCode'),
      rules: z.string().min(1).max(100),
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
      rules: z.string().min(1),
    },
    sectionSchema('section_lifecycle', $t('system.tenant.sectionLifecycle')),
    {
      component: 'Select',
      componentProps: { options: lifecycleOptions.slice(0, 2) },
      defaultValue: 'formal',
      dependencies: {
        disabled: isEditing,
        triggerFields: ['code'],
      },
      fieldName: 'lifecycle_status',
      label: $t('system.tenant.lifecycleStatus'),
    },
    {
      component: 'DatePicker',
      componentProps: datePickerProps(),
      fieldName: 'effective_at',
      label: $t('system.tenant.effectiveAt'),
    },
    {
      component: 'DatePicker',
      componentProps: datePickerProps(),
      dependencies: {
        show: (values) => values.lifecycle_status === 'trial',
        triggerFields: ['lifecycle_status'],
      },
      fieldName: 'trial_ends_at',
      label: $t('system.tenant.trialEndsAt'),
    },
    {
      component: 'DatePicker',
      componentProps: datePickerProps(),
      fieldName: 'service_expires_at',
      label: $t('system.tenant.serviceExpiresAt'),
    },
    sectionSchema('section_contact', $t('system.tenant.sectionContact')),
    {
      component: 'Input',
      fieldName: 'contact_name',
      label: $t('system.tenant.contactName'),
    },
    {
      component: 'Input',
      componentProps: { maxlength: 32 },
      fieldName: 'contact_mobile',
      label: $t('system.tenant.contactMobile'),
    },
    {
      component: 'Input',
      fieldName: 'website',
      label: $t('system.tenant.website'),
    },
    {
      component: 'Input',
      fieldName: 'address_code',
      label: $t('system.tenant.addressCode'),
    },
    {
      component: 'Input',
      fieldName: 'address_detail',
      label: $t('system.tenant.addressDetail'),
    },
    sectionSchema('section_business', $t('system.tenant.sectionBusiness')),
    {
      component: 'InputNumber',
      componentProps: { class: 'w-full', min: 0, precision: 0 },
      fieldName: 'industry',
      label: $t('system.tenant.industry'),
    },
    {
      component: 'InputNumber',
      componentProps: { class: 'w-full', min: 0, precision: 0 },
      fieldName: 'type',
      label: $t('system.tenant.tenantType'),
    },
    {
      component: 'InputNumber',
      componentProps: { class: 'w-full', min: 0, precision: 0 },
      fieldName: 'account_count',
      label: $t('system.tenant.accountCount'),
    },
    {
      component: 'Input',
      fieldName: 'owner_name',
      label: $t('system.tenant.ownerName'),
    },
    {
      component: 'Input',
      fieldName: 'customer_source',
      label: $t('system.tenant.customerSource'),
    },
    {
      component: 'Textarea',
      componentProps: { maxLength: 500, rows: 2, showCount: true },
      fieldName: 'qualifications',
      formItemClass: 'col-span-2',
      label: $t('system.tenant.qualifications'),
    },
    {
      component: 'Textarea',
      componentProps: { maxLength: 1000, rows: 3, showCount: true },
      fieldName: 'follow_up_notes',
      formItemClass: 'col-span-2',
      label: $t('system.tenant.followUpNotes'),
    },
    {
      component: 'Textarea',
      componentProps: { maxLength: 500, rows: 3, showCount: true },
      fieldName: 'description',
      formItemClass: 'col-span-2',
      label: $t('system.tenant.description'),
    },
    sectionSchema(
      'section_provisioning',
      $t('system.tenant.sectionProvisioning'),
    ),
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
      rules: z.string().min(1),
    },
    {
      component: 'Input',
      dependencies: {
        show: () => !isEditing(),
        triggerFields: ['code'],
      },
      fieldName: 'username',
      label: $t('system.tenant.adminEmail'),
      rules: z.string().email().optional().or(z.literal('')),
    },
    {
      component: 'InputPassword',
      dependencies: {
        show: () => !isEditing(),
        triggerFields: ['code'],
      },
      fieldName: 'password',
      label: $t('system.tenant.adminPassword'),
    },
  ];
}

export function useLifecycleFormSchema(
  action: 'freeze' | 'renew',
): VbenFormSchema[] {
  if (action === 'renew') {
    return [
      {
        component: 'DatePicker',
        componentProps: datePickerProps(),
        fieldName: 'service_expires_at',
        label: $t('system.tenant.serviceExpiresAt'),
        rules: 'required',
      },
    ];
  }
  return [
    {
      component: 'Textarea',
      componentProps: { maxLength: 500, rows: 4, showCount: true },
      fieldName: 'frozen_reason',
      label: $t('system.tenant.freezeReason'),
      rules: 'required',
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
      componentProps: { allowClear: true, options: lifecycleOptions },
      fieldName: 'lifecycle_status',
      label: $t('system.tenant.lifecycleStatus'),
    },
    {
      component: 'ApiSelect',
      componentProps: {
        allowClear: true,
        api: listSimpleTenantPlansApi,
        class: 'w-full',
        labelField: 'name',
        valueField: 'id',
      },
      fieldName: 'plan_id',
      label: $t('system.tenant.plan'),
    },
    {
      component: 'Input',
      fieldName: 'owner_name',
      label: $t('system.tenant.ownerName'),
    },
    {
      component: 'Input',
      fieldName: 'customer_source',
      label: $t('system.tenant.customerSource'),
    },
    {
      component: 'InputNumber',
      componentProps: { class: 'w-full', min: 0, precision: 0 },
      fieldName: 'industry',
      label: $t('system.tenant.industry'),
    },
    {
      component: 'ApiSelect',
      componentProps: {
        allowClear: true,
        api: listSimpleTenantTemplatesApi,
        class: 'w-full',
        labelField: 'name',
        valueField: 'id',
      },
      fieldName: 'initialization_template_id',
      label: $t('system.tenant.template'),
    },
    {
      component: 'Select',
      componentProps: {
        allowClear: true,
        options: [
          { label: $t('system.tenant.expiring7Days'), value: 7 },
          { label: $t('system.tenant.expiring30Days'), value: 30 },
        ],
      },
      fieldName: 'expiring_in_days',
      label: $t('system.tenant.expiringSoon'),
    },
  ];
}

export function useColumns(
  onActionClick: OnActionClickFn<TenantRecord>,
): VxeTableGridColumns<TenantRecord> {
  return [
    {
      field: 'name',
      fixed: 'left',
      minWidth: 180,
      title: $t('system.tenant.tenantName'),
    },
    { field: 'code', minWidth: 150, title: $t('system.tenant.tenantCode') },
    {
      cellRender: { name: 'CellTag', options: lifecycleOptions },
      field: 'lifecycle_status',
      title: $t('system.tenant.lifecycleStatus'),
      width: 100,
    },
    { field: 'plan_name', minWidth: 130, title: $t('system.tenant.plan') },
    {
      field: 'owner_name',
      minWidth: 120,
      title: $t('system.tenant.ownerName'),
    },
    {
      field: 'contact_name',
      minWidth: 120,
      title: $t('system.tenant.contactName'),
    },
    {
      field: 'contact_mobile',
      minWidth: 130,
      title: $t('system.tenant.contactMobile'),
    },
    {
      field: 'current_account_count',
      title: $t('system.tenant.currentAccountCount'),
      width: 110,
    },
    {
      field: 'service_expires_at',
      formatter: ({ cellValue }) =>
        cellValue ? formatDateTime(cellValue) : '-',
      title: $t('system.tenant.serviceExpiresAt'),
      width: 180,
    },
    {
      field: 'created_at',
      formatter: ({ cellValue }) =>
        cellValue ? formatDateTime(cellValue) : '-',
      title: $t('system.tenant.createTime'),
      width: 180,
    },
    {
      align: 'center',
      cellRender: {
        attrs: {
          maxVisible: 2,
          moreText: $t('system.common.more'),
          nameField: 'name',
          nameTitle: $t('system.tenant.name'),
          onClick: onActionClick,
        },
        name: 'CellOperation',
        options: [
          {
            auth: 'platform:tenant:list',
            code: 'overview',
            text: $t('system.tenant.overview'),
          },
          {
            auth: 'platform:tenant:update',
            code: 'edit',
            disabled: (row: TenantRecord) => row.id === DEFAULT_TENANT_ID,
          },
          {
            auth: 'platform:tenant:lifecycle',
            code: 'convert',
            disabled: (row: TenantRecord) =>
              row.id === DEFAULT_TENANT_ID || row.lifecycle_status !== 'trial',
            text: $t('system.tenant.convertFormal'),
          },
          {
            auth: 'platform:tenant:lifecycle',
            code: 'renew',
            disabled: (row: TenantRecord) =>
              row.id === DEFAULT_TENANT_ID ||
              row.lifecycle_status === 'archived',
            text: $t('system.tenant.renew'),
          },
          {
            auth: 'platform:tenant:lifecycle',
            code: 'freeze',
            disabled: (row: TenantRecord) =>
              row.id === DEFAULT_TENANT_ID ||
              ['archived', 'frozen'].includes(row.lifecycle_status ?? 'formal'),
            text: $t('system.tenant.freeze'),
          },
          {
            auth: 'platform:tenant:lifecycle',
            code: 'unfreeze',
            disabled: (row: TenantRecord) =>
              row.id === DEFAULT_TENANT_ID || row.lifecycle_status !== 'frozen',
            text: $t('system.tenant.unfreeze'),
          },
          {
            auth: 'platform:tenant:sync-menu',
            code: 'sync-menu',
            disabled: (row: TenantRecord) => row.id === DEFAULT_TENANT_ID,
            text: $t('system.tenant.syncMenu'),
          },
          {
            auth: 'platform:tenant:delete',
            code: 'archive',
            disabled: (row: TenantRecord) =>
              row.id === DEFAULT_TENANT_ID ||
              row.lifecycle_status === 'archived',
            text: $t('system.tenant.archive'),
          },
        ],
      },
      field: 'operation',
      fixed: 'right',
      title: $t('system.tenant.operation'),
      width: 250,
    },
  ];
}
