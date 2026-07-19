import type { VbenFormSchema } from '#/adapter/form';
import type { OnActionClickFn, VxeTableGridColumns } from '#/adapter/vxe-table';
import type { ItemRecord } from '#/modules/items/api/items';

import { z } from '#/adapter/form';
import { $t } from '#/locales';

export function useFormSchema(): VbenFormSchema[] {
  return [
    {
      component: 'Input',
      fieldName: 'title',
      label: $t('business.title'),
      rules: z
        .string()
        .min(1, $t('ui.formRules.required', [$t('business.title')])),
    },
    {
      component: 'Textarea',
      componentProps: {
        rows: 4,
      },
      fieldName: 'description',
      label: $t('business.description'),
    },
  ];
}

export function useGridFormSchema(): VbenFormSchema[] {
  return [
    {
      component: 'Input',
      componentProps: {
        placeholder: $t('business.searchPlaceholder'),
      },
      fieldName: 'keyword',
      label: $t('business.keyword'),
    },
  ];
}

export function useColumns(
  onActionClick: OnActionClickFn<ItemRecord>,
): VxeTableGridColumns<ItemRecord> {
  return [
    {
      field: 'title',
      minWidth: 180,
      showOverflow: true,
      title: $t('business.title'),
    },
    {
      field: 'description',
      formatter: ({ cellValue }) => cellValue || '-',
      minWidth: 220,
      showOverflow: true,
      title: $t('business.description'),
    },
    {
      field: 'created_at',
      title: $t('business.createdAt'),
      width: 180,
    },
    {
      field: 'updated_at',
      formatter: ({ cellValue }) => cellValue || '-',
      title: $t('business.updatedAt'),
      width: 180,
    },
    {
      align: 'center',
      cellRender: {
        attrs: {
          nameField: 'title',
          nameTitle: $t('business.name'),
          onClick: onActionClick,
        },
        name: 'CellOperation',
        options: [
          {
            auth: 'business:item:update',
            code: 'edit',
          },
          {
            auth: 'business:item:delete',
            code: 'delete',
          },
        ],
      },
      field: 'operation',
      fixed: 'right',
      title: $t('business.operation'),
      width: 140,
    },
  ];
}
