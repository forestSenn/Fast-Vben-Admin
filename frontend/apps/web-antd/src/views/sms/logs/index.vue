<script lang="ts" setup>
import type { VxeTableGridOptions } from '#/adapter/vxe-table';
import type { SmsLogRecord } from '#/api';

import { Page } from '@vben/common-ui';

import { useVbenVxeGrid } from '#/adapter/vxe-table';
import { listSmsLogsApi } from '#/api';

import { useColumns, useGridFormSchema } from './data';

const [Grid] = useVbenVxeGrid({
  formOptions: {
    schema: useGridFormSchema(),
    submitOnChange: true,
  },
  gridOptions: {
    columns: useColumns(),
    height: 'auto',
    proxyConfig: {
      ajax: {
        query: async ({ page }, formValues) => {
          return await listSmsLogsApi({
            keyword: formValues.keyword || undefined,
            mobile: formValues.mobile || undefined,
            page: page.currentPage,
            page_size: page.pageSize,
            receive_status: formValues.receive_status || undefined,
            send_status: formValues.send_status || undefined,
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
  } as VxeTableGridOptions<SmsLogRecord>,
});
</script>

<template>
  <Page auto-content-height>
    <Grid table-title="短信日志" />
  </Page>
</template>
