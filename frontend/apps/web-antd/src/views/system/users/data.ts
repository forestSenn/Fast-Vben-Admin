import type { VbenFormSchema } from '#/adapter/form';
import type { OnActionClickFn, VxeTableGridColumns } from '#/adapter/vxe-table';
import type { UserRecord } from '#/api';

import { z } from '#/adapter/form';
import { listDepartmentsApi, listPostsApi, listRolesApi } from '#/api';
import { $t } from '#/locales';

const PROTECTED_ADMIN_EMAIL = 'admin@example.com';

function isProtectedAdmin(row: UserRecord) {
  return row.email.toLowerCase() === PROTECTED_ADMIN_EMAIL;
}

export function useFormSchema(isEdit = false): VbenFormSchema[] {
  return [
    {
      component: 'Input',
      fieldName: 'email',
      label: $t('system.user.email'),
      rules: z.string().email($t('system.user.emailInvalid')),
    },
    {
      component: 'Input',
      fieldName: 'full_name',
      label: $t('system.user.fullName'),
    },
    {
      component: 'Input',
      componentProps: {
        maxlength: 11,
        placeholder: '13800138000',
      },
      fieldName: 'mobile',
      label: $t('system.user.mobile'),
      rules: z
        .string()
        .regex(/^1[3-9]\d{9}$/, $t('system.user.mobileInvalid'))
        .optional()
        .or(z.literal('')),
    },
    {
      component: 'ApiSelect',
      componentProps: {
        allowClear: true,
        api: async () => {
          const result = await listDepartmentsApi({ page: 1, page_size: 200 });
          return result.items;
        },
        class: 'w-full',
        labelField: 'name',
        valueField: 'id',
      },
      fieldName: 'department_id',
      label: $t('system.user.dept'),
    },
    {
      component: 'ApiSelect',
      componentProps: {
        api: async () => {
          const result = await listRolesApi({ page: 1, page_size: 200 });
          return result.items;
        },
        class: 'w-full',
        labelField: 'name',
        mode: 'multiple',
        valueField: 'id',
      },
      fieldName: 'role_ids',
      label: $t('system.user.roles'),
    },
    {
      component: 'ApiSelect',
      componentProps: {
        api: async () => {
          const result = await listPostsApi({
            is_active: true,
            page: 1,
            page_size: 200,
          });
          return result.items;
        },
        class: 'w-full',
        labelField: 'name',
        mode: 'multiple',
        valueField: 'id',
      },
      fieldName: 'post_ids',
      label: $t('system.user.posts'),
    },
    {
      component: 'InputPassword',
      fieldName: 'password',
      label: isEdit
        ? $t('system.user.newPassword')
        : $t('system.user.password'),
      rules: isEdit
        ? undefined
        : z
            .string()
            .min(1, $t('ui.formRules.required', [$t('system.user.password')])),
    },
    {
      component: 'Switch',
      defaultValue: true,
      fieldName: 'is_active',
      label: $t('common.enabled'),
    },
    {
      component: 'Switch',
      defaultValue: false,
      fieldName: 'is_superuser',
      label: $t('system.user.superuser'),
    },
  ];
}

export function useGridFormSchema(): VbenFormSchema[] {
  return [
    {
      component: 'Input',
      fieldName: 'keyword',
      label: $t('system.user.name'),
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
      label: $t('system.user.status'),
    },
    {
      component: 'RangePicker',
      fieldName: 'createTime',
      label: $t('system.user.createTime'),
    },
  ];
}

export function useColumns(
  onActionClick: OnActionClickFn<UserRecord>,
  onStatusChange?: (
    newStatus: boolean,
    row: UserRecord,
  ) => PromiseLike<boolean | undefined>,
): VxeTableGridColumns<UserRecord> {
  return [
    {
      field: 'email',
      minWidth: 200,
      title: $t('system.user.name'),
    },
    {
      field: 'id',
      minWidth: 200,
      title: $t('system.user.id'),
    },
    {
      cellRender: {
        attrs: { auth: 'system:user:update', beforeChange: onStatusChange },
        name: onStatusChange ? 'CellSwitch' : 'CellTag',
        props: {
          disabled: isProtectedAdmin,
        },
      },
      field: 'is_active',
      title: $t('system.user.status'),
      width: 100,
    },
    {
      field: 'full_name',
      minWidth: 120,
      title: $t('system.user.remark'),
    },
    {
      field: 'created_at',
      title: $t('system.user.createTime'),
      width: 180,
    },
    {
      align: 'center',
      cellRender: {
        attrs: {
          nameField: 'email',
          nameTitle: $t('system.user.name'),
          onClick: onActionClick,
        },
        name: 'CellOperation',
        options: [
          {
            auth: 'system:user:update',
            code: 'edit',
            disabled: isProtectedAdmin,
          },
          {
            auth: 'system:user:delete',
            code: 'delete',
            disabled: isProtectedAdmin,
          },
          {
            auth: 'system:user:update',
            code: 'reset-mfa',
            disabled: isProtectedAdmin,
            text: '重置 MFA',
          },
        ],
      },
      field: 'operation',
      fixed: 'right',
      title: $t('system.user.operation'),
      width: 180,
    },
  ];
}
