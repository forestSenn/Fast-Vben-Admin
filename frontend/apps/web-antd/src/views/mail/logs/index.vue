<script lang="ts" setup>
import type { VxeTableGridOptions } from '#/adapter/vxe-table';
import type { MailLogRecord } from '#/api';

import { Page } from '@vben/common-ui';

import { useVbenVxeGrid } from '#/adapter/vxe-table';
import { listMailLogsApi } from '#/api';

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
          return await listMailLogsApi({
            keyword: formValues.keyword || undefined,
            page: page.currentPage,
            page_size: page.pageSize,
            send_status: formValues.send_status || undefined,
            to_email: formValues.to_email || undefined,
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
  } as VxeTableGridOptions<MailLogRecord>,
});
</script>

<template>
  <Page auto-content-height>
    <Grid table-title="邮件日志" />
  </Page>
</template>
