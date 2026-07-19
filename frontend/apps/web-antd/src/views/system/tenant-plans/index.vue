<script lang="ts" setup>
import type {
  OnActionClickParams,
  VxeTableGridOptions,
} from '#/adapter/vxe-table';
import type { TenantPlanRecord } from '#/api';

import { Page, useVbenDrawer } from '@vben/common-ui';
import { Plus } from '@vben/icons';

import { Button, message } from 'ant-design-vue';

import { useVbenVxeGrid } from '#/adapter/vxe-table';
import {
  deleteTenantPlanApi,
  listTenantPlansApi,
  syncTenantPlanMenusApi,
} from '#/api';
import { $t } from '#/locales';

import { buildKeyword, confirmAction } from '../shared/utils';
import { useColumns, useGridFormSchema } from './data';
import Form from './modules/form.vue';
import Permission from './modules/permission.vue';

const [FormDrawer, formDrawerApi] = useVbenDrawer({
  connectedComponent: Form,
  destroyOnClose: true,
});

const [PermissionDrawer, permissionDrawerApi] = useVbenDrawer({
  connectedComponent: Permission,
  destroyOnClose: true,
});

function onActionClick({ code, row }: OnActionClickParams<TenantPlanRecord>) {
  if (code === 'edit') formDrawerApi.setData(row).open();
  if (code === 'delete') void onDelete(row);
  if (code === 'grant-menu') permissionDrawerApi.setData(row).open();
  if (code === 'sync-menu') void onSyncMenus(row);
}

function showSyncResult(successCount = 0, failedCount = 0, skippedCount = 0) {
  message.success(
    $t('system.tenantPlan.syncResult', [
      successCount,
      failedCount,
      skippedCount,
    ]),
  );
}

async function onSyncMenus(row: TenantPlanRecord) {
  try {
    await confirmAction(
      $t('system.tenantPlan.syncConfirm', [row.name]),
      $t('system.tenantPlan.syncMenu'),
    );
    const result = await syncTenantPlanMenusApi(row.id);
    showSyncResult(
      result.success_count,
      result.failed_count,
      result.skipped_count,
    );
  } catch {
    // Cancellation and request errors are handled by the shared UI layer.
  }
}

async function onDelete(row: TenantPlanRecord) {
  try {
    await confirmAction(
      $t('system.tenantPlan.deleteConfirm', [row.name]),
      $t('system.tenantPlan.delete'),
    );
    await deleteTenantPlanApi(row.id);
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
          await listTenantPlansApi({
            is_active: formValues.is_active,
            keyword: buildKeyword(formValues.keyword),
            page: page.currentPage,
            page_size: page.pageSize,
            published: formValues.published,
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
  } as VxeTableGridOptions<TenantPlanRecord>,
});
</script>

<template>
  <Page auto-content-height>
    <FormDrawer @success="gridApi.query()" />
    <PermissionDrawer @success="gridApi.query()" />
    <Grid :table-title="$t('system.tenantPlan.list')">
      <template #toolbar-tools>
        <Button
          v-access:code="'platform:plan:create'"
          type="primary"
          @click="formDrawerApi.setData(undefined).open()"
        >
          <Plus class="size-5" />
          {{ $t('system.tenantPlan.create') }}
        </Button>
      </template>
    </Grid>
  </Page>
</template>
