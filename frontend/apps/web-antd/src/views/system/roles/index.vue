<script lang="ts" setup>
import type {
  OnActionClickParams,
  VxeTableGridOptions,
} from '#/adapter/vxe-table';
import type { RoleRecord } from '#/api';

import { Page, useVbenDrawer } from '@vben/common-ui';
import { Plus } from '@vben/icons';

import { Button, message } from 'ant-design-vue';

import { useVbenVxeGrid } from '#/adapter/vxe-table';
import { deleteRoleApi, listRolesApi, updateRoleApi } from '#/api';

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

async function onStatusChange(newStatus: boolean, row: RoleRecord) {
  try {
    await confirmAction(
      `确认将角色 ${row.name} 的状态切换为【${newStatus ? '启用' : '禁用'}】吗？`,
      '切换状态',
    );
    await updateRoleApi(row.id, { is_active: newStatus });
    return true;
  } catch {
    return false;
  }
}

function onActionClick({ code, row }: OnActionClickParams<RoleRecord>) {
  switch (code) {
    case 'delete': {
      void onDelete(row);
      break;
    }
    case 'edit': {
      formDrawerApi.setData(row).open();
      break;
    }
    case 'permission': {
      permissionDrawerApi.setData(row).open();
      break;
    }
  }
}

async function onDelete(row: RoleRecord) {
  const hideLoading = message.loading({
    content: `正在删除 ${row.name}`,
    duration: 0,
    key: 'role_delete',
  });
  try {
    await deleteRoleApi(row.id);
    message.success({
      content: `${row.name} 已删除`,
      key: 'role_delete',
    });
    onRefresh();
  } catch {
    hideLoading();
  }
}

const [Grid, gridApi] = useVbenVxeGrid({
  formOptions: {
    fieldMappingTime: [['createTime', ['startTime', 'endTime']]],
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
          return await listRolesApi({
            keyword: buildKeyword(
              formValues.name,
              formValues.code,
              formValues.description,
            ),
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
  } as VxeTableGridOptions<RoleRecord>,
});

function onRefresh() {
  gridApi.query();
}

function onCreate() {
  formDrawerApi.setData(undefined).open();
}
</script>

<template>
  <Page auto-content-height>
    <FormDrawer @success="onRefresh" />
    <PermissionDrawer @success="onRefresh" />
    <Grid table-title="角色列表">
      <template #toolbar-tools>
        <Button
          v-access:code="'system:role:create'"
          type="primary"
          @click="onCreate"
        >
          <Plus class="size-5" />
          新增角色
        </Button>
      </template>
    </Grid>
  </Page>
</template>
