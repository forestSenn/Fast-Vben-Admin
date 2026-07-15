<script lang="ts" setup>
import type {
  OnActionClickParams,
  VxeTableGridOptions,
} from '#/adapter/vxe-table';
import type { TenantTemplateRecord } from '#/api';

import { Page, useVbenDrawer } from '@vben/common-ui';
import { Plus } from '@vben/icons';

import { Button, message } from 'ant-design-vue';

import { useVbenVxeGrid } from '#/adapter/vxe-table';
import { deleteTenantTemplateApi, listTenantTemplatesApi } from '#/api';
import { $t } from '#/locales';

import { buildKeyword, confirmAction } from '../shared/utils';
import { useColumns, useGridFormSchema } from './data';
import Form from './modules/form.vue';

const [FormDrawer, formDrawerApi] = useVbenDrawer({
  connectedComponent: Form,
  destroyOnClose: true,
});

function onActionClick({
  code,
  row,
}: OnActionClickParams<TenantTemplateRecord>) {
  if (code === 'edit') formDrawerApi.setData(row).open();
  if (code === 'delete') void onDelete(row);
}

async function onDelete(row: TenantTemplateRecord) {
  try {
    await confirmAction(
      $t('system.tenantTemplate.deleteConfirm', [row.name]),
      $t('system.tenantTemplate.delete'),
    );
    await deleteTenantTemplateApi(row.id);
    message.success($t('system.common.success'));
    gridApi.query();
  } catch {
    // Cancellation and request errors are handled by the shared UI layer.
  }
}

const [Grid, gridApi] = useVbenVxeGrid({
  formOptions: { schema: useGridFormSchema(), submitOnChange: true },
  gridOptions: {
    columns: useColumns(onActionClick),
    height: 'auto',
    keepSource: true,
    proxyConfig: {
      ajax: {
        query: async ({ page }, formValues) =>
          await listTenantTemplatesApi({
            is_active: formValues.is_active,
            keyword: buildKeyword(formValues.keyword),
            page: page.currentPage,
            page_size: page.pageSize,
          }),
      },
    },
    rowConfig: { keyField: 'id' },
    toolbarConfig: {
      custom: true,
      export: false,
      refresh: true,
      search: true,
      zoom: true,
    },
  } as VxeTableGridOptions<TenantTemplateRecord>,
});
</script>

<template>
  <Page auto-content-height>
    <FormDrawer @success="gridApi.query()" />
    <Grid :table-title="$t('system.tenantTemplate.list')">
      <template #toolbar-tools>
        <Button
          v-access:code="'platform:template:create'"
          type="primary"
          @click="formDrawerApi.setData(undefined).open()"
        >
          <Plus class="size-5" />
          {{ $t('system.tenantTemplate.create') }}
        </Button>
      </template>
    </Grid>
  </Page>
</template>
