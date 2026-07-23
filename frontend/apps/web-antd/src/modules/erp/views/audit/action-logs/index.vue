<script lang="ts" setup>
import type { VxeTableGridOptions } from '#/adapter/vxe-table';
import type { ActionLogQuery, DocumentActionLogRecord } from '#/modules/erp/api/erp';

import { reactive } from 'vue';

import { Page } from '@vben/common-ui';
import { RotateCw, Search } from '@vben/icons';
import { Button, Input, Select, Tag } from 'ant-design-vue';

import { useVbenVxeGrid } from '#/adapter/vxe-table';
import { listDocumentActionLogsApi } from '#/modules/erp/api/erp';

const filters = reactive<ActionLogQuery>({
  action: undefined,
  resource_id: undefined,
  resource_type: undefined,
});

const actionOptions = [
  { label: '创建', value: 'created' },
  { label: '更新', value: 'updated' },
  { label: '删除', value: 'deleted' },
  { label: '审核', value: 'approved' },
  { label: '反审核', value: 'reversed' },
  { label: '导出', value: 'exported' },
  { label: '敏感信息查看', value: 'sensitive_viewed' },
];

const actionLabels: Record<string, string> = Object.fromEntries(
  actionOptions.map((option) => [option.value, option.label]),
);

const [Grid, gridApi] = useVbenVxeGrid({
  gridOptions: {
    columns: [
      { field: 'occurred_at', formatter: 'formatDateTime', minWidth: 170, title: '操作时间' },
      { field: 'action', slots: { default: 'action' }, title: '动作', width: 130 },
      { field: 'resource_type', minWidth: 140, title: '资源类型' },
      { field: 'resource_no', minWidth: 150, title: '单据号' },
      { field: 'resource_id', minWidth: 220, showOverflow: 'tooltip', title: '资源 ID' },
      { field: 'old_status', minWidth: 100, title: '原状态' },
      { field: 'new_status', minWidth: 100, title: '新状态' },
      { field: 'old_version', title: '原版本', width: 90 },
      { field: 'new_version', title: '新版本', width: 90 },
      { field: 'reason', minWidth: 180, showOverflow: 'tooltip', title: '原因' },
    ],
    height: 'auto',
    proxyConfig: {
      ajax: {
        query: async ({ page }) =>
          await listDocumentActionLogsApi({
            ...filters,
            page: page.currentPage,
            page_size: page.pageSize,
          }),
      },
    },
    rowConfig: { keyField: 'id' },
    toolbarConfig: { custom: true, refresh: true, zoom: true },
  } as VxeTableGridOptions<DocumentActionLogRecord>,
});

function search() {
  gridApi.query();
}

function reset() {
  Object.assign(filters, { action: undefined, resource_id: undefined, resource_type: undefined });
  search();
}
</script>

<template>
  <Page auto-content-height>
    <Grid table-title="操作日志">
      <template #toolbar-tools>
        <div class="flex flex-wrap items-center gap-1">
          <Input v-model:value="filters.resource_type" allow-clear class="w-36" placeholder="资源类型" @press-enter="search" />
          <Input v-model:value="filters.resource_id" allow-clear class="w-48" placeholder="资源 ID" @press-enter="search" />
          <Select v-model:value="filters.action" allow-clear class="w-36" :options="actionOptions" placeholder="操作动作" />
          <Button class="gap-1" type="primary" @click="search"><Search class="size-4" /><span>查询</span></Button>
          <Button class="gap-1" @click="reset"><RotateCw class="size-4" /><span>重置</span></Button>
        </div>
      </template>
      <template #action="{ row }"><Tag color="blue">{{ actionLabels[row.action] ?? row.action }}</Tag></template>
    </Grid>
  </Page>
</template>
