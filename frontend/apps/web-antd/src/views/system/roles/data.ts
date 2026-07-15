import type { VbenFormSchema } from '#/adapter/form';
import type { OnActionClickFn, VxeTableGridColumns } from '#/adapter/vxe-table';
import type { RoleRecord } from '#/api';

import { z } from '#/adapter/form';
import { listDepartmentsApi } from '#/api';
import { $t } from '#/locales';

import { buildDepartmentTree } from '../shared/utils';

const dataScopeOptions = () => [
  { label: $t('system.role.dataScopeAll'), value: 'all' },
  { label: $t('system.role.dataScopeDepartment'), value: 'department' },
  {
    label: $t('system.role.dataScopeDepartmentChildren'),
    value: 'department_and_children',
  },
  { label: $t('system.role.dataScopeSelf'), value: 'self' },
  { label: $t('system.role.dataScopeCustom'), value: 'custom' },
];

function formatDataScope(value?: null | string) {
  return (
    dataScopeOptions().find((option) => option.value === value)?.label ?? '-'
  );
}

export function useFormSchema(): VbenFormSchema[] {
  return [
    {
      component: 'Input',
      fieldName: 'name',
      label: $t('system.role.roleName'),
      rules: z
        .string()
        .min(1, $t('ui.formRules.required', [$t('system.role.roleName')])),
    },
    {
      component: 'Input',
      componentProps: (values) => ({
        disabled: !!values.is_system,
      }),
      fieldName: 'code',
      label: $t('system.role.roleCode'),
      rules: z
        .string()
        .min(1, $t('ui.formRules.required', [$t('system.role.roleCode')])),
    },
    {
      component: 'Textarea',
      componentProps: {
        rows: 3,
      },
      fieldName: 'description',
      label: $t('system.role.remark'),
    },
    {
      component: 'Select',
      componentProps: {
        options: dataScopeOptions(),
      },
      defaultValue: 'self',
      fieldName: 'data_scope',
      label: $t('system.role.dataScope'),
    },
    {
      component: 'ApiTreeSelect',
      componentProps: {
        allowClear: true,
        api: async () => {
          const result = await listDepartmentsApi({ page: 1, page_size: 500 });
          return buildDepartmentTree(result.items);
        },
        childrenField: 'children',
        class: 'w-full',
        labelField: 'name',
        multiple: true,
        treeCheckable: true,
        valueField: 'id',
      },
      dependencies: {
        show: (values) => values.data_scope === 'custom',
        triggerFields: ['data_scope'],
      },
      fieldName: 'custom_department_ids',
      label: $t('system.role.customDepartments'),
    },
    {
      component: 'InputNumber',
      componentProps: {
        class: 'w-full',
      },
      defaultValue: 0,
      fieldName: 'sort',
      label: $t('system.common.sort'),
    },
    {
      component: 'Switch',
      defaultValue: true,
      fieldName: 'is_active',
      label: $t('common.enabled'),
    },
    {
      component: 'Switch',
      componentProps: (values) => ({
        disabled: !!values.is_system,
      }),
      defaultValue: false,
      fieldName: 'is_system',
      label: $t('system.role.systemRole'),
    },
  ];
}

export function useGridFormSchema(): VbenFormSchema[] {
  return [
    {
      component: 'Input',
      fieldName: 'name',
      label: $t('system.role.roleName'),
    },
    {
      component: 'Input',
      fieldName: 'code',
      label: $t('system.role.roleCode'),
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
      label: $t('system.role.status'),
    },
    {
      component: 'Input',
      fieldName: 'description',
      label: $t('system.role.remark'),
    },
    {
      component: 'RangePicker',
      fieldName: 'createTime',
      label: $t('system.role.createTime'),
    },
  ];
}

export function useColumns(
  onActionClick: OnActionClickFn<RoleRecord>,
  onStatusChange?: (
    newStatus: boolean,
    row: RoleRecord,
  ) => PromiseLike<boolean | undefined>,
): VxeTableGridColumns<RoleRecord> {
  return [
    {
      field: 'name',
      minWidth: 160,
      title: $t('system.role.roleName'),
    },
    {
      field: 'code',
      minWidth: 160,
      title: $t('system.role.roleCode'),
    },
    {
      field: 'data_scope',
      formatter: ({ cellValue }) => formatDataScope(cellValue),
      minWidth: 150,
      title: $t('system.role.dataScope'),
    },
    {
      cellRender: {
        attrs: { auth: 'system:role:update', beforeChange: onStatusChange },
        name: onStatusChange ? 'CellSwitch' : 'CellTag',
      },
      field: 'is_active',
      title: $t('system.role.status'),
      width: 100,
    },
    {
      field: 'description',
      minWidth: 180,
      showOverflow: true,
      title: $t('system.role.remark'),
    },
    {
      field: 'created_at',
      title: $t('system.role.createTime'),
      width: 180,
    },
    {
      align: 'center',
      cellRender: {
        attrs: {
          nameField: 'name',
          nameTitle: $t('system.role.name'),
          onClick: onActionClick,
        },
        name: 'CellOperation',
        options: [
          {
            auth: 'system:role:update',
            code: 'permission',
            text: $t('system.role.permissions'),
          },
          {
            auth: 'system:role:update',
            code: 'edit',
          },
          {
            auth: 'system:role:delete',
            code: 'delete',
            disabled: (row: RoleRecord) => !!row.is_system,
          },
        ],
      },
      field: 'operation',
      fixed: 'right',
      title: $t('system.role.operation'),
      width: 180,
    },
  ];
}
