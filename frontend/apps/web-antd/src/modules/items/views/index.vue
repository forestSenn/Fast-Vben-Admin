<script lang="ts" setup>
import type {
  OnActionClickParams,
  VxeTableGridOptions,
} from '#/adapter/vxe-table';
import type { ItemRecord } from '#/modules/items/api/items';

import { Page, useVbenDrawer, useVbenModal } from '@vben/common-ui';
import { Plus } from '@vben/icons';

import { Button, message } from 'ant-design-vue';

import { useVbenVxeGrid } from '#/adapter/vxe-table';
import { downloadApi } from '#/api';
import {
  deleteItemApi,
  itemsExportPath,
  itemsImportTemplatePath,
  listItemsApi,
} from '#/modules/items/api/items';
import { $t } from '#/locales';

import { buildKeyword } from '#/views/system/shared/utils';
import { useColumns, useGridFormSchema } from './data';
import Form from './modules/form.vue';
import Import from './modules/import.vue';

const [FormDrawer, formDrawerApi] = useVbenDrawer({
  connectedComponent: Form,
  destroyOnClose: true,
});

const [ImportModal, importModalApi] = useVbenModal({
  connectedComponent: Import,
  destroyOnClose: true,
});

function onActionClick({ code, row }: OnActionClickParams<ItemRecord>) {
  switch (code) {
    case 'delete': {
      void onDelete(row);
      break;
    }
    case 'edit': {
      formDrawerApi.setData(row).open();
      break;
    }
  }
}

async function onDelete(row: ItemRecord) {
  const hideLoading = message.loading({
    content: $t('business.deleting', [row.title]),
    duration: 0,
    key: 'item_delete',
  });
  try {
    await deleteItemApi(row.id);
    message.success({
      content: $t('business.deleteSuccess', [row.title]),
      key: 'item_delete',
    });
    onRefresh();
  } catch {
    hideLoading();
  }
}

const [Grid, gridApi] = useVbenVxeGrid({
  formOptions: {
    schema: useGridFormSchema(),
    submitOnChange: true,
  },
  gridOptions: {
    columns: useColumns(onActionClick),
    height: 'auto',
    keepSource: true,
    proxyConfig: {
      ajax: {
        query: async ({ page }, formValues) => {
          return await listItemsApi({
            keyword: buildKeyword(formValues.keyword) || undefined,
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
  } as VxeTableGridOptions<ItemRecord>,
});

function onRefresh() {
  gridApi.query();
}

function onCreate() {
  formDrawerApi.setData(undefined).open();
}

async function exportItems() {
  await downloadApi(itemsExportPath, 'items.csv');
}

async function downloadTemplate() {
  await downloadApi(itemsImportTemplatePath, 'items-import-template.csv');
}

function openImport() {
  importModalApi.open();
}
</script>

<template>
  <Page auto-content-height>
    <FormDrawer @success="onRefresh" />
    <ImportModal @success="onRefresh" />
    <Grid :table-title="$t('business.list')">
      <template #toolbar-tools>
        <Button v-access:code="'business:item:create'" type="primary" @click="onCreate">
          <Plus class="size-5" />
          {{ $t('business.create') }}
        </Button>
        <Button v-access:code="'business:item:list'" class="ml-2" @click="exportItems">
          {{ $t('business.export') }}
        </Button>
        <Button
          v-access:code="'business:item:create'"
          class="ml-2"
          @click="downloadTemplate"
        >
          {{ $t('business.template') }}
        </Button>
        <Button v-access:code="'business:item:create'" class="ml-2" @click="openImport">
          {{ $t('business.import') }}
        </Button>
      </template>
    </Grid>
  </Page>
</template>
