import type { TableActionProps } from '@vben/common-ui';
import type { VxeTableGridOptions } from '@vben/plugins/vxe-table';
import type { Recordable } from '@vben/types';

import type { ComponentPropsMap, ComponentType } from './component';

import { defineComponent, h } from 'vue';

import { useAccess } from '@vben/access';
import { VbenTableAction as VbenTableActionCore } from '@vben/common-ui';
import { IconifyIcon } from '@vben/icons';
import { $te } from '@vben/locales';
import {
  setupVbenVxeTable,
  useVbenVxeGrid as useGrid,
} from '@vben/plugins/vxe-table';
import { formatDateTime, get, isFunction, isString } from '@vben/utils';

import { objectOmit } from '@vueuse/core';
import {
  Button,
  Dropdown,
  Image,
  Menu,
  Popconfirm,
  Switch,
  Tag,
} from 'ant-design-vue';

import { $t } from '#/locales';

import { useVbenForm } from './form';

setupVbenVxeTable({
  configVxeTable: (vxeUI) => {
    vxeUI.setConfig({
      grid: {
        align: 'center',
        border: false,
        columnConfig: {
          resizable: true,
        },
        formConfig: {
          enabled: false,
        },
        minHeight: 180,
        proxyConfig: {
          autoLoad: true,
          response: {
            result: 'items',
            total: 'total',
            list: 'items',
          },
          showActiveMsg: true,
          showResponseMsg: false,
        },
        round: true,
        showOverflow: true,
        size: 'small',
      } as VxeTableGridOptions,
    });

    vxeUI.renderer.forEach((_item, key) => {
      if (key.startsWith('Cell')) {
        vxeUI.renderer.delete(key);
      }
    });

    vxeUI.renderer.add('CellImage', {
      renderTableDefault(renderOpts, params) {
        const { props } = renderOpts;
        const { column, row } = params;
        return h(Image, { src: row[column.field], ...props });
      },
    });

    vxeUI.renderer.add('CellLink', {
      renderTableDefault(renderOpts) {
        const { props } = renderOpts;
        return h(
          Button,
          { size: 'small', type: 'link' },
          { default: () => props?.text },
        );
      },
    });

    vxeUI.renderer.add('CellTag', {
      renderTableDefault({ options, props }, { column, row }) {
        const value = get(row, column.field);
        const tagOptions = options ?? [
          { color: 'success', label: '启用', value: true },
          { color: 'error', label: '禁用', value: false },
        ];
        const tagItem = tagOptions.find((item) => item.value === value);
        return h(
          Tag,
          {
            ...props,
            ...objectOmit(tagItem ?? {}, ['label']),
          },
          { default: () => tagItem?.label ?? value },
        );
      },
    });

    vxeUI.renderer.add('CellSwitch', {
      renderTableDefault({ attrs, props }, { column, row }) {
        const { hasAccessByCodes } = useAccess();
        const loadingKey = `__loading_${column.field}`;
        const auth = attrs?.auth;
        const disabled =
          typeof props?.disabled === 'function'
            ? props.disabled(row)
            : props?.disabled;
        const hasPermission = auth
          ? hasAccessByCodes(Array.isArray(auth) ? auth : [auth])
          : true;
        const finallyProps = {
          checkedChildren: '启用',
          checkedValue: true,
          unCheckedChildren: '禁用',
          unCheckedValue: false,
          ...props,
          checked: row[column.field],
          disabled: disabled || !hasPermission,
          loading: row[loadingKey] ?? false,
          'onUpdate:checked': onChange,
        };
        async function onChange(newVal: boolean) {
          if (!hasPermission) return;
          row[loadingKey] = true;
          try {
            const result = await attrs?.beforeChange?.(newVal, row);
            if (result !== false) {
              row[column.field] = newVal;
            }
          } finally {
            row[loadingKey] = false;
          }
        }
        return h(Switch, finallyProps as any);
      },
    });

    vxeUI.renderer.add('CellOperation', {
      renderTableDefault({ attrs, options, props }, { column, row }) {
        const { hasAccessByCodes } = useAccess();
        const defaultProps = { size: 'small', type: 'link', ...props };
        let align: string;
        switch (column.align) {
          case 'center': {
            align = 'center';
            break;
          }
          case 'left': {
            align = 'start';
            break;
          }
          default: {
            align = 'end';
            break;
          }
        }
        const presets: Recordable<Recordable<any>> = {
          delete: {
            danger: true,
            text: '删除',
          },
          detail: {
            text: '详情',
          },
          edit: {
            text: '修改',
          },
        };
        const operations: Array<Recordable<any>> = (
          options || ['edit', 'delete']
        )
          .map((opt) => {
            if (isString(opt)) {
              return presets[opt]
                ? { code: opt, ...presets[opt], ...defaultProps }
                : {
                    code: opt,
                    text: $te(`common.${opt}`) ? $t(`common.${opt}`) : opt,
                    ...defaultProps,
                  };
            }
            return { ...defaultProps, ...presets[opt.code], ...opt };
          })
          .map((opt) => {
            const optBtn: Recordable<any> = {};
            Object.keys(opt).forEach((key) => {
              optBtn[key] = isFunction(opt[key]) ? opt[key](row) : opt[key];
            });
            return optBtn;
          })
          .filter((opt) => {
            if (opt.show === false) return false;
            if (!opt.auth) return true;
            const authCodes = Array.isArray(opt.auth) ? opt.auth : [opt.auth];
            return hasAccessByCodes(authCodes);
          });

        function renderBtn(opt: Recordable<any>, listen = true) {
          return h(
            Button,
            {
              ...props,
              ...opt,
              icon: undefined,
              onClick: listen
                ? () =>
                    attrs?.onClick?.({
                      code: opt.code,
                      row,
                    })
                : undefined,
            },
            {
              default: () => {
                const content = [];
                if (opt.icon) {
                  content.push(
                    h(IconifyIcon, { class: 'size-5', icon: opt.icon }),
                  );
                }
                content.push(opt.text);
                return content;
              },
            },
          );
        }

        function renderConfirm(opt: Recordable<any>) {
          let viewportWrapper: HTMLElement | null = null;
          return h(
            Popconfirm,
            {
              getPopupContainer(el) {
                viewportWrapper = el.closest('.vxe-table--viewport-wrapper');
                return document.body;
              },
              placement: 'topLeft',
              title: `确认删除${attrs?.nameTitle || ''}`,
              ...props,
              ...opt,
              icon: undefined,
              onOpenChange: (open: boolean) => {
                if (open) {
                  viewportWrapper?.style.setProperty('pointer-events', 'none');
                } else {
                  viewportWrapper?.style.removeProperty('pointer-events');
                }
              },
              onConfirm: () => {
                attrs?.onClick?.({
                  code: opt.code,
                  row,
                });
              },
            },
            {
              default: () => renderBtn({ ...opt }, false),
              description: () =>
                h(
                  'div',
                  { class: 'truncate' },
                  `确认删除 ${row[attrs?.nameField || 'name']} 吗？`,
                ),
            },
          );
        }

        const maxVisible = attrs?.maxVisible ?? operations.length;
        const visibleOperations = operations.slice(0, maxVisible);
        const dropdownOperations = operations.slice(maxVisible);
        const btns = visibleOperations.map((opt) =>
          opt.code === 'delete' ? renderConfirm(opt) : renderBtn(opt),
        );
        if (dropdownOperations.length > 0) {
          btns.push(
            h(
              Dropdown,
              {
                trigger: ['click'],
              },
              {
                default: () =>
                  h(
                    Button,
                    {
                      'aria-label': attrs?.moreText || '更多操作',
                      size: 'small',
                      title: attrs?.moreText || '更多操作',
                      type: 'text',
                    },
                    {
                      default: () =>
                        h(IconifyIcon, {
                          class: 'size-5',
                          icon: 'lucide:ellipsis',
                        }),
                    },
                  ),
                overlay: () =>
                  h(Menu, {
                    items: dropdownOperations.map((opt) => ({
                      danger: opt.danger,
                      disabled: opt.disabled,
                      key: opt.code,
                      label: opt.text,
                    })),
                    onClick: ({ key }: { key: number | string }) => {
                      attrs?.onClick?.({ code: String(key), row });
                    },
                  }),
              },
            ),
          );
        }
        return h(
          'div',
          {
            class: 'flex table-operations',
            style: { justifyContent: align },
          },
          btns,
        );
      },
    });
  },
  useVbenForm,
});

const DATE_TIME_FIELD_RE = /(_at|_time)$/;

function shouldApplyDateTimeFormatter(column: Recordable<any>) {
  return (
    isString(column.field) &&
    DATE_TIME_FIELD_RE.test(column.field) &&
    !column.formatter &&
    !column.cellRender
  );
}

function applyDefaultColumnFormatters(
  columns: Recordable<any>[] = [],
): Recordable<any>[] {
  return columns.map((column) => {
    const nextColumn = { ...column };
    if (Array.isArray(column.children)) {
      nextColumn.children = applyDefaultColumnFormatters(column.children);
    }
    if (shouldApplyDateTimeFormatter(nextColumn)) {
      nextColumn.formatter = ({ cellValue }: { cellValue: unknown }) =>
        cellValue ? formatDateTime(String(cellValue)) : '-';
    }
    return nextColumn;
  });
}

export const useVbenVxeGrid = <T extends Record<string, any>>(
  ...rest: Parameters<typeof useGrid<T, ComponentType, ComponentPropsMap>>
) => {
  const [options, ...others] = rest;
  const nextOptions =
    options?.gridOptions?.columns && Array.isArray(options.gridOptions.columns)
      ? {
          ...options,
          gridOptions: {
            ...options.gridOptions,
            columns: applyDefaultColumnFormatters(
              options.gridOptions.columns as Recordable<any>[],
            ),
          },
        }
      : options;

  return useGrid<T, ComponentType, ComponentPropsMap>(
    ...( [nextOptions, ...others] as Parameters<
      typeof useGrid<T, ComponentType, ComponentPropsMap>
    >),
  );
};

export const VbenTableAction = defineComponent(
  (props: TableActionProps, { attrs, slots }) => {
    const { hasAccessByCodes } = useAccess();
    function hasPermission(auth?: string | string[]) {
      if (!auth) return true;
      return hasAccessByCodes(Array.isArray(auth) ? auth : [auth]);
    }
    return () =>
      h(VbenTableActionCore, { hasPermission, ...props, ...attrs }, slots);
  },
  {
    name: 'VbenTableAction',
    inheritAttrs: false,
  },
);

export type OnActionClickParams<T = Recordable<any>> = {
  code: string;
  row: T;
};
export type OnActionClickFn<T = Recordable<any>> = (
  params: OnActionClickParams<T>,
) => void;
export type * from '@vben/plugins/vxe-table';
