<script lang="ts" setup>
import type { VxeTableGridOptions } from '#/adapter/vxe-table';
import type { LoginLogRecord } from '#/api';

import { Page } from '@vben/common-ui';

import { useVbenVxeGrid } from '#/adapter/vxe-table';
import { listLoginLogsApi } from '#/api';

import { buildKeyword } from '../../system/shared/utils';
import { useColumns, useGridFormSchema } from './data';

const [Grid] = useVbenVxeGrid({
  formOptions: {
    schema: useGridFormSchema(),
    submitOnChange: true,
  },
  gridOptions: {
    columns: useColumns(),
    height: 'auto',
    keepSource: true,
    proxyConfig: {
      ajax: {
        query: async ({ page }, formValues) => {
          return await listLoginLogsApi({
            keyword: buildKeyword(formValues.keyword) || undefined,
            page: page.currentPage,
            page_size: page.pageSize,
            status: formValues.status || undefined,
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
  } as VxeTableGridOptions<LoginLogRecord>,
});
</script>

<template>
  <Page auto-content-height>
    <Grid table-title="登录日志" />
  </Page>
</template>
