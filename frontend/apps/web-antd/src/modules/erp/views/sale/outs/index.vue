<script lang="ts" setup>
import type { VxeTableGridOptions } from '#/adapter/vxe-table';
import type {
  CounterpartyRecord,
  DocumentQuery,
  ProductRecord,
  SettlementAccountRecord,
  SaleOutRecord,
  SaleOrderRecord,
  WarehouseRecord,
} from '#/modules/erp/api/erp';

import { computed, onMounted, ref } from 'vue';

import { Page } from '@vben/common-ui';
import { Plus } from '@vben/icons';
import { Button, Drawer, Input, InputNumber, Tag } from 'ant-design-vue';

import { useVbenVxeGrid } from '#/adapter/vxe-table';
import DocumentListFilters from '#/modules/erp/components/document-list-filters.vue';
import DocumentTableActions from '#/modules/erp/components/document-table-actions.vue';
import ExportCsvButton from '#/modules/erp/components/export-csv-button.vue';
import ReverseDocumentDialog from '#/modules/erp/components/reverse-document-dialog.vue';
import {
  approveSaleOutApi,
  createSaleOutApi,
  deleteSaleOutApi,
  listCounterpartiesApi,
  listProductsApi,
  getSaleOrderApi,
  listSaleOutsApi,
  listSaleOrdersApi,
  listSettlementAccountsApi,
  listWarehousesApi,
  reverseSaleOutApi,
  updateSaleOutApi,
} from '#/modules/erp/api/erp';
import ErpRemoteSelect from '#/modules/erp/components/erp-remote-select.vue';
import { compareDecimal, normalizeDecimal, subtractDecimal, QUANTITY_DECIMAL_PLACES } from '#/modules/erp/utils/decimal';

interface ShipmentLine {
  sale_order_item_id: string;
  quantity: string;
  warehouse_id?: string;
}

const drawerOpen = ref(false);
const saving = ref(false);
const reverseOpen = ref(false);
const reverseTarget = ref<SaleOutRecord>();
const editingShipment = ref<SaleOutRecord>();
const selectedOrderId = ref<string>();
const settlementAccountId = ref<string>();
const businessAt = ref<string>();
const discountRate = ref(0);
const discountAmount = ref<number>();
const otherDeduction = ref(0);
const saleOrders = ref<SaleOrderRecord[]>([]);
const warehouses = ref<WarehouseRecord[]>([]);
const settlementAccounts = ref<SettlementAccountRecord[]>([]);
const shipmentLines = ref<ShipmentLine[]>([]);
const products = ref<ProductRecord[]>([]);
const customers = ref<CounterpartyRecord[]>([]);
const listQuery = ref<DocumentQuery>({});
const exportQuery = computed(() =>
  Object.fromEntries(
    Object.entries(listQuery.value).filter(
      (entry): entry is [string, string] =>
        typeof entry[1] === 'string' && Boolean(entry[1]),
    ),
  ),
);

const selectedOrder = computed(() =>
  saleOrders.value.find((order) => order.id === selectedOrderId.value),
);

const [Grid, gridApi] = useVbenVxeGrid({
  gridOptions: {
    columns: [
      { field: 'no', minWidth: 190, title: '销售出库单号' },
      { field: 'sale_order_no', minWidth: 190, title: '来源销售订单' },
      { field: 'customer_name', minWidth: 160, title: '客户' },
      { field: 'business_at', title: '出库日期', width: 180 },
      { field: 'total_quantity', title: '出库数量', width: 110 },
      { field: 'status', slots: { default: 'status' }, title: '状态', width: 90 },
      { field: 'version', title: '版本', width: 70 },
      { align: 'center', field: 'operation', fixed: 'right', slots: { default: 'operation' }, title: '操作', width: 320 },
    ],
    height: 'auto',
    proxyConfig: { ajax: { query: async ({ page }) => await listSaleOutsApi({ ...listQuery.value, page: page.currentPage, page_size: page.pageSize }) } },
    rowConfig: { keyField: 'id' },
    toolbarConfig: { custom: true, refresh: true, zoom: true },
  } as VxeTableGridOptions<SaleOutRecord>,
});

async function loadFilterReferences() {
  const [customerResult, productResult] = await Promise.all([
    listCounterpartiesApi('customer', { page: 1, page_size: 50 }),
    listProductsApi({ page: 1, page_size: 50 }),
  ]);
  customers.value = customerResult.items.filter((item) => item.is_active);
  products.value = productResult.items.filter((item) => item.is_active);
}

onMounted(() => void loadFilterReferences());

async function loadCustomers(keyword: string) {
  const result = await listCounterpartiesApi('customer', { keyword, page: 1, page_size: 50 });
  customers.value = result.items.filter((item) => item.is_active);
  return customers.value;
}

async function loadProducts(keyword: string) {
  const result = await listProductsApi({ keyword, page: 1, page_size: 50 });
  products.value = result.items.filter((item) => item.is_active);
  return products.value;
}

function remainingQuantity(item: NonNullable<SaleOrderRecord['items']>[number]) {
  return subtractDecimal(item.quantity, item.shipped_quantity, QUANTITY_DECIMAL_PLACES);
}

function formatOrder(order: SaleOrderRecord) { return { label: `${order.no} - ${order.customer_name}`, value: order.id }; }
function formatWarehouse(warehouse: WarehouseRecord) { return { label: `${warehouse.name} (${warehouse.code})`, value: warehouse.id }; }
function formatSettlementAccount(account: SettlementAccountRecord) { return { label: account.name, value: account.id }; }
async function loadSaleOrders(keyword: string) {
  const result = await listSaleOrdersApi({ keyword, page: 1, page_size: 50 });
  saleOrders.value = result.items.filter((order) => order.status === 'approved' && (order.items ?? []).some((item) => compareDecimal(remainingQuantity(item), 0) > 0));
  return saleOrders.value;
}
async function loadWarehouses(keyword: string) {
  const result = await listWarehousesApi({ keyword, page: 1, page_size: 50 });
  warehouses.value = result.items.filter((warehouse) => warehouse.is_active);
  return warehouses.value;
}
async function loadSettlementAccounts(keyword: string) {
  const result = await listSettlementAccountsApi({ keyword, page: 1, page_size: 50 });
  settlementAccounts.value = result.items.filter((account) => account.is_active);
  return settlementAccounts.value;
}

function selectOrder(orderId: unknown) {
  if (typeof orderId !== 'string') return;
  const order = saleOrders.value.find((entry) => entry.id === orderId);
  settlementAccountId.value = order?.settlement_account_id || undefined;
  shipmentLines.value = (order?.items ?? [])
    .filter((item) => compareDecimal(remainingQuantity(item), 0) > 0)
    .map((item) => ({
      sale_order_item_id: item.id,
      quantity: remainingQuantity(item),
    }));
}

async function openCreate() {
  selectedOrderId.value = undefined;
  settlementAccountId.value = undefined;
  businessAt.value = undefined;
  discountRate.value = 0;
  discountAmount.value = undefined;
  otherDeduction.value = 0;
  shipmentLines.value = [];
  editingShipment.value = undefined;
  drawerOpen.value = true;
}

async function openEdit(row: SaleOutRecord) {
  await openCreate();
  editingShipment.value = row;
  const order = await getSaleOrderApi(row.sale_order_id);
  saleOrders.value = [order];
  selectedOrderId.value = row.sale_order_id;
  settlementAccountId.value = row.settlement_account_id || undefined;
  businessAt.value = new Date(row.business_at).toISOString().slice(0, 16);
  discountRate.value = Number(row.discount_rate);
  discountAmount.value = Number(row.discount_amount);
  otherDeduction.value = Number(row.other_deduction);
  shipmentLines.value = (row.items || []).map((line) => ({ sale_order_item_id: line.sale_order_item_id, quantity: normalizeDecimal(line.quantity, QUANTITY_DECIMAL_PLACES), warehouse_id: line.warehouse_id }));
}

async function submit() {
  if (!selectedOrder.value || shipmentLines.value.length === 0 || shipmentLines.value.some((line) => !line.warehouse_id || compareDecimal(line.quantity, 0) <= 0)) return;
  saving.value = true;
  try {
    const payload = {
      sale_order_id: selectedOrder.value.id,
      settlement_account_id: settlementAccountId.value,
      business_at: businessAt.value ? new Date(businessAt.value).toISOString() : undefined,
      discount_rate: String(discountRate.value || 0),
      discount_amount: discountAmount.value === undefined ? undefined : String(discountAmount.value),
      other_deduction: String(otherDeduction.value || 0),
      items: shipmentLines.value.map((line) => ({
        sale_order_item_id: line.sale_order_item_id,
        quantity: normalizeDecimal(line.quantity, QUANTITY_DECIMAL_PLACES),
        warehouse_id: line.warehouse_id!,
      })),
    };
    if (editingShipment.value) await updateSaleOutApi(editingShipment.value.id, payload, editingShipment.value.version);
    else await createSaleOutApi(payload);
    drawerOpen.value = false;
    gridApi.query();
  } finally {
    saving.value = false;
  }
}

async function remove(row: SaleOutRecord) { await deleteSaleOutApi(row.id); gridApi.query(); }

async function approve(row: SaleOutRecord) {
  await approveSaleOutApi(row.id, row.version);
  gridApi.query();
}

function openReverse(row: SaleOutRecord) {
  reverseTarget.value = row;
  reverseOpen.value = true;
}
async function confirmReverse(reason: string) {
  const row = reverseTarget.value;
  if (!row) return;
  await reverseSaleOutApi(row.id, row.version, reason);
  gridApi.query();
}
</script>

<template>
  <Page auto-content-height>
    <ReverseDocumentDialog v-model:open="reverseOpen" impact="反审核会恢复本次出库库存；已有销售退货时将被后端阻止。" :on-confirm="confirmReverse" title="反审核销售出库" />
    <Drawer v-model:open="drawerOpen" :confirm-loading="saving" :title="editingShipment ? '编辑销售出库' : '新增销售出库'" class="w-[min(1040px,calc(100vw-24px))]" placement="right">
      <div class="mb-4">
        <div class="mb-1 text-sm font-medium">来源销售订单</div>
        <ErpRemoteSelect v-model:value="selectedOrderId" class="w-full" :format-option="formatOrder" :load="loadSaleOrders" placeholder="选择已审核且有剩余数量的销售订单" @change="selectOrder" />
      </div>
      <div v-if="selectedOrder" class="mb-3 text-sm text-[var(--vben-text-color-secondary)]">客户：{{ selectedOrder.customer_name }}，单据：{{ selectedOrder.no }}</div>
      <div class="mb-4 grid gap-3 md:grid-cols-4"><Input v-model:value="businessAt" type="datetime-local" /><ErpRemoteSelect v-model:value="settlementAccountId" allow-clear :format-option="formatSettlementAccount" :load="loadSettlementAccounts" placeholder="结算账户" /><InputNumber v-model:value="discountRate" :max="100" :min="0" :precision="4" placeholder="优惠率 (%)" /><InputNumber v-model:value="discountAmount" :min="0" :precision="4" placeholder="优惠金额" /></div>
      <div class="mb-4 max-w-56"><InputNumber v-model:value="otherDeduction" :min="0" :precision="4" class="w-full" placeholder="其他扣减" /></div>
      <div class="overflow-x-auto rounded border border-[var(--vben-border-color)]">
        <table class="min-w-[820px] w-full text-left text-sm">
          <thead><tr><th class="p-2">商品</th><th class="p-2">订单数量</th><th class="p-2">可出库</th><th class="p-2">本次出库</th><th class="p-2">出库仓库</th></tr></thead>
          <tbody><tr v-for="line in shipmentLines" :key="line.sale_order_item_id" class="border-t border-[var(--vben-border-color)]"><td class="p-2">{{ selectedOrder?.items?.find((item) => item.id === line.sale_order_item_id)?.product_name }}</td><td class="p-2">{{ selectedOrder?.items?.find((item) => item.id === line.sale_order_item_id)?.quantity }}</td><td class="p-2">{{ remainingQuantity(selectedOrder?.items?.find((item) => item.id === line.sale_order_item_id)!) }}</td><td class="p-2"><InputNumber v-model:value="line.quantity" :max="remainingQuantity(selectedOrder?.items?.find((item) => item.id === line.sale_order_item_id)!)" :min="'0.000001'" :precision="6" string-mode /></td><td class="p-2"><ErpRemoteSelect v-model:value="line.warehouse_id" class="min-w-64" :format-option="formatWarehouse" :load="loadWarehouses" placeholder="选择仓库" /></td></tr></tbody>
        </table>
      </div>
      <template #footer><div class="flex justify-end gap-2"><Button @click="drawerOpen = false">取消</Button><Button :loading="saving" type="primary" @click="submit">{{ editingShipment ? '保存修改' : '保存草稿' }}</Button></div></template>
    </Drawer>
    <DocumentListFilters v-model="listQuery" :counterparties="customers" :counterparty-loader="loadCustomers" counterparty-key="customer_id" counterparty-label="客户" :products="products" :product-loader="loadProducts" @query="gridApi.query()" />
    <Grid table-title="销售出库列表">
      <template #toolbar-tools><div class="flex items-center gap-1"><Button v-access:code="'erp:sale-out:create'" class="gap-1" type="primary" @click="openCreate"><Plus class="size-5" /><span>新增销售出库</span></Button><ExportCsvButton file-name="销售出库列表.csv" permission="erp:sale-out:export" :query="exportQuery" resource="sale-out" /></div></template>
      <template #status="{ row }"><Tag :color="row.status === 'approved' ? 'success' : 'default'">{{ row.status === 'approved' ? '已审批' : '草稿' }}</Tag></template>
      <template #operation="{ row }"><DocumentTableActions approve-impact="审批后将扣减库存并占用销售订单剩余数量，确认继续吗？" approve-permission="erp:sale-out:approve" delete-permission="erp:sale-out:delete" :document-id="row.id" :document-no="row.no" document-type="sale_out" reverse-permission="erp:sale-out:reverse" :status="row.status" update-permission="erp:sale-out:update" @approve="approve(row)" @delete="remove(row)" @edit="openEdit(row)" @reverse="openReverse(row)" /></template>
    </Grid>
  </Page>
</template>
