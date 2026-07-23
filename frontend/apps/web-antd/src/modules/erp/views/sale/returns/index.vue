<script lang="ts" setup>
import type { VxeTableGridOptions } from '#/adapter/vxe-table';
import type {
  CounterpartyRecord,
  DocumentQuery,
  ProductRecord,
  SaleOutRecord,
  SaleReturnRecord,
  SettlementAccountRecord,
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
  approveSaleReturnApi,
  createSaleReturnApi,
  deleteSaleReturnApi,
  listCounterpartiesApi,
  listProductsApi,
  getSaleOutApi,
  listSaleOutsApi,
  listSaleReturnsApi,
  listSettlementAccountsApi,
  reverseSaleReturnApi,
  updateSaleReturnApi,
} from '#/modules/erp/api/erp';
import ErpRemoteSelect from '#/modules/erp/components/erp-remote-select.vue';
import { compareDecimal, normalizeDecimal, subtractDecimal, QUANTITY_DECIMAL_PLACES } from '#/modules/erp/utils/decimal';

interface ReturnLine {
  sale_out_item_id: string;
  quantity: string;
}

const drawerOpen = ref(false);
const saving = ref(false);
const reverseOpen = ref(false);
const reverseTarget = ref<SaleReturnRecord>();
const editingReturn = ref<SaleReturnRecord>();
const selectedShipmentId = ref<string>();
const settlementAccountId = ref<string>();
const businessAt = ref<string>();
const discountRate = ref(0);
const discountAmount = ref<number>();
const otherDeduction = ref(0);
const shipments = ref<SaleOutRecord[]>([]);
const settlementAccounts = ref<SettlementAccountRecord[]>([]);
const returnLines = ref<ReturnLine[]>([]);
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
const selectedShipment = computed(() => shipments.value.find((shipment) => shipment.id === selectedShipmentId.value));

const [Grid, gridApi] = useVbenVxeGrid({
  gridOptions: {
    columns: [
      { field: 'no', minWidth: 190, title: '销售退货单号' }, { field: 'sale_out_no', minWidth: 190, title: '来源销售出库' },
      { field: 'customer_name', minWidth: 160, title: '客户' }, { field: 'business_at', title: '退货日期', width: 180 },
      { field: 'total_quantity', title: '退货数量', width: 110 }, { field: 'status', slots: { default: 'status' }, title: '状态', width: 90 },
      { field: 'version', title: '版本', width: 70 }, { align: 'center', field: 'operation', fixed: 'right', slots: { default: 'operation' }, title: '操作', width: 320 },
    ], height: 'auto',
    proxyConfig: { ajax: { query: async ({ page }) => await listSaleReturnsApi({ ...listQuery.value, page: page.currentPage, page_size: page.pageSize }) } },
    rowConfig: { keyField: 'id' }, toolbarConfig: { custom: true, refresh: true, zoom: true },
  } as VxeTableGridOptions<SaleReturnRecord>,
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

function remainingQuantity(item: NonNullable<SaleOutRecord['items']>[number]) {
  return subtractDecimal(item.quantity, item.returned_quantity, QUANTITY_DECIMAL_PLACES);
}

function formatShipment(shipment: SaleOutRecord) { return { label: `${shipment.no} - ${shipment.customer_name}`, value: shipment.id }; }
function formatSettlementAccount(account: SettlementAccountRecord) { return { label: account.name, value: account.id }; }
async function loadShipments(keyword: string) {
  const result = await listSaleOutsApi({ keyword, page: 1, page_size: 50 });
  shipments.value = result.items.filter((shipment) => shipment.status === 'approved' && (shipment.items ?? []).some((item) => compareDecimal(remainingQuantity(item), 0) > 0));
  return shipments.value;
}
async function loadSettlementAccounts(keyword: string) {
  const result = await listSettlementAccountsApi({ keyword, page: 1, page_size: 50 });
  settlementAccounts.value = result.items.filter((account) => account.is_active);
  return settlementAccounts.value;
}

function selectShipment(shipmentId: unknown) {
  if (typeof shipmentId !== 'string') return;
  const shipment = shipments.value.find((entry) => entry.id === shipmentId);
  settlementAccountId.value = shipment?.settlement_account_id || undefined;
  returnLines.value = (shipment?.items ?? []).filter((item) => compareDecimal(remainingQuantity(item), 0) > 0).map((item) => ({ sale_out_item_id: item.id, quantity: remainingQuantity(item) }));
}

async function openCreate() {
  selectedShipmentId.value = undefined;
  settlementAccountId.value = undefined;
  businessAt.value = undefined;
  discountRate.value = 0;
  discountAmount.value = undefined;
  otherDeduction.value = 0;
  returnLines.value = [];
  editingReturn.value = undefined;
  drawerOpen.value = true;
}

async function openEdit(row: SaleReturnRecord) {
  await openCreate();
  editingReturn.value = row;
  const shipment = await getSaleOutApi(row.sale_out_id);
  shipments.value = [shipment];
  selectedShipmentId.value = row.sale_out_id;
  settlementAccountId.value = row.settlement_account_id || undefined;
  businessAt.value = new Date(row.business_at).toISOString().slice(0, 16);
  discountRate.value = Number(row.discount_rate);
  discountAmount.value = Number(row.discount_amount);
  otherDeduction.value = Number(row.other_deduction);
  returnLines.value = (row.items || []).map((line) => ({ sale_out_item_id: line.sale_out_item_id, quantity: normalizeDecimal(line.quantity, QUANTITY_DECIMAL_PLACES) }));
}

async function submit() {
  if (!selectedShipment.value || returnLines.value.length === 0 || returnLines.value.some((line) => compareDecimal(line.quantity, 0) <= 0)) return;
  saving.value = true;
  try {
    const payload = { sale_out_id: selectedShipment.value.id, settlement_account_id: settlementAccountId.value, business_at: businessAt.value ? new Date(businessAt.value).toISOString() : undefined, discount_rate: String(discountRate.value || 0), discount_amount: discountAmount.value === undefined ? undefined : String(discountAmount.value), other_deduction: String(otherDeduction.value || 0), items: returnLines.value.map((line) => ({ sale_out_item_id: line.sale_out_item_id, quantity: normalizeDecimal(line.quantity, QUANTITY_DECIMAL_PLACES) })) };
    if (editingReturn.value) await updateSaleReturnApi(editingReturn.value.id, payload, editingReturn.value.version);
    else await createSaleReturnApi(payload);
    drawerOpen.value = false;
    gridApi.query();
  } finally { saving.value = false; }
}

async function approve(row: SaleReturnRecord) { await approveSaleReturnApi(row.id, row.version); gridApi.query(); }
function openReverse(row: SaleReturnRecord) { reverseTarget.value = row; reverseOpen.value = true; }
async function confirmReverse(reason: string) { const row = reverseTarget.value; if (!row) return; await reverseSaleReturnApi(row.id, row.version, reason); gridApi.query(); }
async function remove(row: SaleReturnRecord) { await deleteSaleReturnApi(row.id); gridApi.query(); }
</script>

<template>
  <Page auto-content-height>
    <ReverseDocumentDialog v-model:open="reverseOpen" impact="反审核会扣减本次销售退货恢复的库存。" :on-confirm="confirmReverse" title="反审核销售退货" />
    <Drawer v-model:open="drawerOpen" :confirm-loading="saving" :title="editingReturn ? '编辑销售退货' : '新增销售退货'" class="w-[min(960px,calc(100vw-24px))]" placement="right">
      <div class="mb-4"><div class="mb-1 text-sm font-medium">来源销售出库单</div><ErpRemoteSelect v-model:value="selectedShipmentId" class="w-full" :format-option="formatShipment" :load="loadShipments" placeholder="选择已审核且可退货的销售出库单" @change="selectShipment" /></div>
      <div v-if="selectedShipment" class="mb-3 text-sm text-[var(--vben-text-color-secondary)]">客户：{{ selectedShipment.customer_name }}，单据：{{ selectedShipment.no }}</div>
      <div class="mb-4 grid gap-3 md:grid-cols-4"><Input v-model:value="businessAt" type="datetime-local" /><ErpRemoteSelect v-model:value="settlementAccountId" allow-clear :format-option="formatSettlementAccount" :load="loadSettlementAccounts" placeholder="结算账户" /><InputNumber v-model:value="discountRate" :max="100" :min="0" :precision="4" placeholder="优惠率 (%)" /><InputNumber v-model:value="discountAmount" :min="0" :precision="4" placeholder="优惠金额" /></div>
      <div class="mb-4 max-w-56"><InputNumber v-model:value="otherDeduction" :min="0" :precision="4" class="w-full" placeholder="其他扣减" /></div>
      <div class="overflow-x-auto rounded border border-[var(--vben-border-color)]"><table class="min-w-[680px] w-full text-left text-sm"><thead><tr><th class="p-2">商品</th><th class="p-2">出库数量</th><th class="p-2">可退数量</th><th class="p-2">本次退货</th></tr></thead><tbody><tr v-for="line in returnLines" :key="line.sale_out_item_id" class="border-t border-[var(--vben-border-color)]"><td class="p-2">{{ selectedShipment?.items?.find((item) => item.id === line.sale_out_item_id)?.product_name }}</td><td class="p-2">{{ selectedShipment?.items?.find((item) => item.id === line.sale_out_item_id)?.quantity }}</td><td class="p-2">{{ remainingQuantity(selectedShipment?.items?.find((item) => item.id === line.sale_out_item_id)!) }}</td><td class="p-2"><InputNumber v-model:value="line.quantity" :max="remainingQuantity(selectedShipment?.items?.find((item) => item.id === line.sale_out_item_id)!)" :min="'0.000001'" :precision="6" string-mode /></td></tr></tbody></table></div>
      <template #footer><div class="flex justify-end gap-2"><Button @click="drawerOpen = false">取消</Button><Button :loading="saving" type="primary" @click="submit">{{ editingReturn ? '保存修改' : '保存草稿' }}</Button></div></template>
    </Drawer>
    <DocumentListFilters v-model="listQuery" :counterparties="customers" :counterparty-loader="loadCustomers" counterparty-key="customer_id" counterparty-label="客户" :products="products" :product-loader="loadProducts" @query="gridApi.query()" />
    <Grid table-title="销售退货列表">
      <template #toolbar-tools><div class="flex items-center gap-1"><Button v-access:code="'erp:sale-return:create'" class="gap-1" type="primary" @click="openCreate"><Plus class="size-5" /><span>新增销售退货</span></Button><ExportCsvButton file-name="销售退货列表.csv" permission="erp:sale-return:export" :query="exportQuery" resource="sale-return" /></div></template>
      <template #status="{ row }"><Tag :color="row.status === 'approved' ? 'success' : 'default'">{{ row.status === 'approved' ? '已审批' : '草稿' }}</Tag></template>
      <template #operation="{ row }"><DocumentTableActions approve-impact="审批后将增加库存并更新来源销售订单，确认继续吗？" approve-permission="erp:sale-return:approve" delete-permission="erp:sale-return:delete" :document-id="row.id" :document-no="row.no" document-type="sale_return" reverse-permission="erp:sale-return:reverse" :status="row.status" update-permission="erp:sale-return:update" @approve="approve(row)" @delete="remove(row)" @edit="openEdit(row)" @reverse="openReverse(row)" /></template>
    </Grid>
  </Page>
</template>
