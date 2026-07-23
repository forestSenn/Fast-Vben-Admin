<script lang="ts" setup>
import type { VxeTableGridOptions } from '#/adapter/vxe-table';
import type {
  ProductCategoryRecord,
  ProductRecord,
  StockBalanceRecord,
  StockLedgerRecord,
  StockQuery,
  WarehouseRecord,
} from '#/modules/erp/api/erp';

import { computed, reactive, ref, watch } from 'vue';
import { useRoute } from 'vue-router';

import { Page } from '@vben/common-ui';
import { Download, RotateCw, Search } from '@vben/icons';

import { Button, Input, Select, Segmented } from 'ant-design-vue';

import { useVbenVxeGrid, VbenTableAction } from '#/adapter/vxe-table';
import { downloadApi } from '#/api';
import ErpRemoteSelect from '#/modules/erp/components/erp-remote-select.vue';
import LedgerSourceDocument from '#/modules/erp/components/ledger-source-document.vue';
import {
  listProductCategoriesApi,
  listProductsApi,
  listStockBalancesApi,
  listStockRecordsApi,
  listWarehousesApi,
  stockBalancesExportPath,
  stockRecordsExportPath,
} from '#/modules/erp/api/erp';

const route = useRoute();

function viewForPath(path: string): 'balance' | 'ledger' {
  return path === '/erp/stock/ledger' ? 'ledger' : 'balance';
}

const view = ref<'balance' | 'ledger'>(viewForPath(route.path));
const isDedicatedPage = computed(
  () => route.path === '/erp/stock/balances' || route.path === '/erp/stock/ledger',
);
const products = ref<ProductRecord[]>([]);
const categories = ref<ProductCategoryRecord[]>([]);
const warehouses = ref<WarehouseRecord[]>([]);

const balanceFilters = reactive({
  category_id: undefined as string | undefined,
  product_id: undefined as string | undefined,
  warehouse_id: undefined as string | undefined,
});
const ledgerFilters = reactive({
  category_id: undefined as string | undefined,
  ledger_type: undefined as string | undefined,
  occurred_from: undefined as string | undefined,
  occurred_to: undefined as string | undefined,
  product_id: undefined as string | undefined,
  source_document_no: undefined as string | undefined,
  warehouse_id: undefined as string | undefined,
});

const ledgerTypeOptions = [
  { label: '采购入库', value: 'purchase_in' },
  { label: '采购入库冲销', value: 'purchase_in_reversal' },
  { label: '采购退货', value: 'purchase_return' },
  { label: '采购退货冲销', value: 'purchase_return_reversal' },
  { label: '销售出库', value: 'sale_out' },
  { label: '销售出库冲销', value: 'sale_out_reversal' },
  { label: '销售退货', value: 'sale_return' },
  { label: '销售退货冲销', value: 'sale_return_reversal' },
  { label: '其他入库', value: 'other_in' },
  { label: '其他入库冲销', value: 'other_in_reversal' },
  { label: '其他出库', value: 'other_out' },
  { label: '其他出库冲销', value: 'other_out_reversal' },
  { label: '调拨入库', value: 'move_in' },
  { label: '调拨入库冲销', value: 'move_in_reversal' },
  { label: '调拨出库', value: 'move_out' },
  { label: '调拨出库冲销', value: 'move_out_reversal' },
  { label: '库存盘点', value: 'check_gain' },
  { label: '盘盈冲销', value: 'check_gain_reversal' },
  { label: '盘亏', value: 'check_loss' },
  { label: '盘亏冲销', value: 'check_loss_reversal' },
];

function toUtc(value: string | undefined) {
  return value ? new Date(value).toISOString() : undefined;
}

function balanceQuery(): StockQuery {
  return { ...balanceFilters };
}

function ledgerQuery(): StockQuery {
  return {
    ...ledgerFilters,
    occurred_from: toUtc(ledgerFilters.occurred_from),
    occurred_to: toUtc(ledgerFilters.occurred_to),
  };
}

async function exportCurrentView() {
  const params = view.value === 'balance' ? balanceQuery() : ledgerQuery();
  const query = new URLSearchParams(
    Object.entries(params)
      .filter(
        ([, value]) => value !== undefined && value !== null && value !== '',
      )
      .map(([key, value]) => [key, String(value)]),
  ).toString();
  const path =
    view.value === 'balance' ? stockBalancesExportPath : stockRecordsExportPath;
  await downloadApi(
    `${path}${query ? `?${query}` : ''}`,
    view.value === 'balance' ? 'stock-balances.csv' : 'stock-records.csv',
  );
}

const [BalanceGrid, balanceGridApi] = useVbenVxeGrid({
  gridOptions: {
    columns: [
      { field: 'product_code', minWidth: 140, title: '商品编码' },
      { field: 'product_name', minWidth: 190, title: '商品名称' },
      { field: 'unit_name', title: '单位', width: 100 },
      { field: 'warehouse_name', minWidth: 160, title: '仓库' },
      { field: 'quantity', title: '可用数量', width: 130 },
      { field: 'updated_at', title: '最近记账', width: 180 },
      { align: 'center', field: 'operation', fixed: 'right', slots: { default: 'operation' }, title: '操作', width: 100 },
    ],
    height: 'auto',
    proxyConfig: {
      ajax: {
        query: async ({ page }) =>
          await listStockBalancesApi({
            ...balanceQuery(),
            page: page.currentPage,
            page_size: page.pageSize,
          }),
      },
    },
    rowConfig: { keyField: 'id' },
    toolbarConfig: { custom: true, refresh: true, zoom: true },
  } as VxeTableGridOptions<StockBalanceRecord>,
});

const [LedgerGrid, ledgerGridApi] = useVbenVxeGrid({
  gridOptions: {
    columns: [
      { field: 'occurred_at', title: '发生时间', width: 180 },
      { field: 'ledger_type', title: '业务类型', width: 150 },
      { field: 'product_code', minWidth: 140, title: '商品编码' },
      { field: 'product_name', minWidth: 190, title: '商品名称' },
      { field: 'warehouse_name', minWidth: 160, title: '仓库' },
      { field: 'delta_quantity', title: '变动数量', width: 120 },
      { field: 'balance_after', title: '结存数量', width: 120 },
      { field: 'source_document_no', minWidth: 170, slots: { default: 'sourceDocument' }, title: '来源单号' },
      { field: 'operator_name', minWidth: 130, title: '操作人' },
    ],
    height: 'auto',
    proxyConfig: {
      ajax: {
        query: async ({ page }) =>
          await listStockRecordsApi({
            ...ledgerQuery(),
            page: page.currentPage,
            page_size: page.pageSize,
          }),
      },
    },
    rowConfig: { keyField: 'id' },
    toolbarConfig: { custom: true, refresh: true, zoom: true },
  } as VxeTableGridOptions<StockLedgerRecord>,
});

function queryCurrentView() {
  (view.value === 'balance' ? balanceGridApi : ledgerGridApi).query();
}

watch(
  () => route.path,
  (path) => {
    if (!isDedicatedPage.value) return;
    view.value = viewForPath(path);
    queryCurrentView();
  },
);

function openLedger(balance: StockBalanceRecord) {
  Object.assign(ledgerFilters, {
    category_id: undefined,
    ledger_type: undefined,
    occurred_from: undefined,
    occurred_to: undefined,
    product_id: balance.product_id,
    source_document_no: undefined,
    warehouse_id: balance.warehouse_id,
  });
  view.value = 'ledger';
  ledgerGridApi.query();
}

function resetFilters() {
  if (view.value === 'balance') {
    Object.assign(balanceFilters, {
      category_id: undefined,
      product_id: undefined,
      warehouse_id: undefined,
    });
  } else {
    Object.assign(ledgerFilters, {
      category_id: undefined,
      ledger_type: undefined,
      occurred_from: undefined,
      occurred_to: undefined,
      product_id: undefined,
      source_document_no: undefined,
      warehouse_id: undefined,
    });
  }
  queryCurrentView();
}

function formatProduct(product: ProductRecord) { return { label: `${product.code} - ${product.name}`, value: product.id }; }
function formatCategory(category: ProductCategoryRecord) { return { label: category.name, value: category.id }; }
function formatWarehouse(warehouse: WarehouseRecord) { return { label: warehouse.name, value: warehouse.id }; }
async function loadProducts(keyword: string) {
  const result = await listProductsApi({ keyword, page: 1, page_size: 50 });
  products.value = result.items;
  return products.value;
}
async function loadCategories(keyword: string) {
  const result = await listProductCategoriesApi({ keyword, page: 1, page_size: 50 });
  categories.value = result.items;
  return categories.value;
}
async function loadWarehouses(keyword: string) {
  const result = await listWarehousesApi({ keyword, page: 1, page_size: 50 });
  warehouses.value = result.items;
  return warehouses.value;
}
</script>

<template>
  <Page auto-content-height>
    <div
      class="mb-3 flex flex-wrap items-center justify-between gap-3 border-b border-[var(--vben-border-color)] pb-3"
    >
      <div>
        <div class="text-base font-semibold">{{ view === 'balance' ? '产品库存' : '出入库明细' }}</div>
        <div class="mt-1 text-sm text-[var(--vben-text-color-2)]">
          余额与不可变流水
        </div>
      </div>
      <div class="flex items-center gap-2">
        <Button
          v-access:code="
            view === 'balance' ? 'erp:stock:export' : 'erp:stock-record:export'
          "
          class="gap-1"
          title="导出当前筛选"
          @click="exportCurrentView"
        >
          <Download class="size-4" />
          <span>导出</span>
        </Button>
        <Segmented
          v-if="!isDedicatedPage"
          v-model:value="view"
          :options="[
            { label: '库存余额', value: 'balance' },
            { label: '库存流水', value: 'ledger' },
          ]"
          @change="queryCurrentView"
        />
      </div>
    </div>

    <div class="mb-3 flex flex-wrap items-center gap-2">
      <ErpRemoteSelect
        v-if="view === 'balance'"
        v-model:value="balanceFilters.product_id"
        allow-clear
        class="w-52"
        :format-option="formatProduct"
        :load="loadProducts"
        placeholder="商品"
        @change="queryCurrentView"
      />
      <ErpRemoteSelect
        v-else
        v-model:value="ledgerFilters.product_id"
        allow-clear
        class="w-52"
        :format-option="formatProduct"
        :load="loadProducts"
        placeholder="商品"
        @change="queryCurrentView"
      />
      <ErpRemoteSelect
        v-if="view === 'balance'"
        v-model:value="balanceFilters.category_id"
        allow-clear
        class="w-48"
        :format-option="formatCategory"
        :load="loadCategories"
        placeholder="商品分类"
        @change="queryCurrentView"
      />
      <ErpRemoteSelect
        v-else
        v-model:value="ledgerFilters.category_id"
        allow-clear
        class="w-48"
        :format-option="formatCategory"
        :load="loadCategories"
        placeholder="商品分类"
        @change="queryCurrentView"
      />
      <ErpRemoteSelect
        v-if="view === 'balance'"
        v-model:value="balanceFilters.warehouse_id"
        allow-clear
        class="w-48"
        :format-option="formatWarehouse"
        :load="loadWarehouses"
        placeholder="仓库"
        @change="queryCurrentView"
      />
      <ErpRemoteSelect
        v-else
        v-model:value="ledgerFilters.warehouse_id"
        allow-clear
        class="w-48"
        :format-option="formatWarehouse"
        :load="loadWarehouses"
        placeholder="仓库"
        @change="queryCurrentView"
      />
      <template v-if="view === 'ledger'">
        <Select
          v-model:value="ledgerFilters.ledger_type"
          allow-clear
          class="w-40"
          :options="ledgerTypeOptions"
          placeholder="业务类型"
          @change="queryCurrentView"
        />
        <Input
          v-model:value="ledgerFilters.source_document_no"
          allow-clear
          class="w-44"
          placeholder="来源单号"
          @press-enter="queryCurrentView"
        />
        <Input
          v-model:value="ledgerFilters.occurred_from"
          class="w-52"
          type="datetime-local"
          @change="queryCurrentView"
        />
        <Input
          v-model:value="ledgerFilters.occurred_to"
          class="w-52"
          type="datetime-local"
          @change="queryCurrentView"
        />
      </template>
      <Button title="应用筛选" @click="queryCurrentView"
        ><Search class="size-4"
      /></Button>
      <Button title="清除筛选" @click="resetFilters"
        ><RotateCw class="size-4"
      /></Button>
    </div>

    <BalanceGrid v-if="view === 'balance'" table-title="库存余额">
      <template #operation="{ row }">
        <VbenTableAction
          :actions="[
            { auth: ['erp:stock-record:list'], icon: 'lucide:eye', onClick: openLedger.bind(null, row), text: '明细', variant: 'link' },
          ]"
        />
      </template>
    </BalanceGrid>
    <LedgerGrid v-else table-title="库存流水">
      <template #sourceDocument="{ row }">
        <LedgerSourceDocument
          :document-id="row.source_document_id"
          :document-no="row.source_document_no"
          :document-type="row.source_document_type"
        />
      </template>
    </LedgerGrid>
  </Page>
</template>
