<script lang="ts" setup>
import type {
  OnActionClickParams,
  VxeTableGridOptions,
} from '#/adapter/vxe-table';
import type { TenantRecord } from '#/api';

import { Page, useVbenDrawer } from '@vben/common-ui';
import { Plus } from '@vben/icons';

import { Button, message } from 'ant-design-vue';

import { useVbenVxeGrid } from '#/adapter/vxe-table';
import {
  archiveTenantApi,
  DEFAULT_TENANT_ID,
  listTenantsApi,
  notifyTenantMembershipsChanged,
  updateTenantApi,
} from '#/api';
import { $t } from '#/locales';

import { buildKeyword, confirmAction } from '../shared/utils';
import { useColumns, useGridFormSchema } from './data';
import Form from './modules/form.vue';

const [FormDrawer, formDrawerApi] = useVbenDrawer({
  connectedComponent: Form,
  destroyOnClose: true,
});

async function onStatusChange(newStatus: boolean, row: TenantRecord) {
  if (row.id === DEFAULT_TENANT_ID) {
    message.warning('默认租户不能停用');
    return false;
  }
  try {
    await confirmAction(
      `确认将租户 ${row.name} 的状态切换为【${newStatus ? '启用' : '禁用'}】吗？`,
      '切换状态',
    );
    await updateTenantApi(row.id, { is_active: newStatus });
    notifyTenantMembershipsChanged();
    return true;
  } catch {
    return false;
  }
}

function onActionClick({ code, row }: OnActionClickParams<TenantRecord>) {
  switch (code) {
    case 'archive': {
      void onArchive(row);
      break;
    }
    case 'edit': {
      formDrawerApi.setData(row).open();
      break;
    }
  }
}

async function onArchive(row: TenantRecord) {
  try {
    await confirmAction(
      `停用后该租户的现有会话将立即失效，确认停用 ${row.name} 吗？`,
      '确认停用租户',
    );
    await archiveTenantApi(row.id);
    notifyTenantMembershipsChanged();
    message.success(`${row.name} 已停用`);
    onRefresh();
  } catch {
    // Cancellation and request errors are handled by the shared UI layer.
  }
}

const [Grid, gridApi] = useVbenVxeGrid({
  formOptions: {
    schema: useGridFormSchema(),
    submitOnChange: true,
  },
  gridOptions: {
    columns: useColumns(onActionClick, onStatusChange),
    height: 'auto',
    keepSource: true,
    proxyConfig: {
      ajax: {
        query: async ({ page }, formValues) => {
          return await listTenantsApi({
            is_active: formValues.is_active,
            keyword: buildKeyword(formValues.keyword),
            page: page.currentPage,
            page_size: page.pageSize,
          });
        },
      },
    },
    rowConfig: {
      keyField: 'id',
    },
    toolbarConfig: {
      custom: true,
      export: false,
      refresh: true,
      search: true,
      zoom: true,
    },
  } as VxeTableGridOptions<TenantRecord>,
});

function onRefresh() {
  notifyTenantMembershipsChanged();
  gridApi.query();
}

function onCreate() {
  formDrawerApi.setData(undefined).open();
}
</script>

<template>
  <Page auto-content-height>
    <FormDrawer @success="onRefresh" />
    <Grid :table-title="$t('system.tenant.list')">
      <template #toolbar-tools>
        <Button
          v-access:code="'platform:tenant:create'"
          type="primary"
          @click="onCreate"
        >
          <Plus class="size-5" />
          {{ $t('system.tenant.create') }}
        </Button>
      </template>
    </Grid>
  </Page>
</template>
