<script lang="ts" setup>
import type { VxeTableGridOptions } from '#/adapter/vxe-table';
import type {
  CounterpartyRecord,
  DocumentQuery,
  ProductRecord,
  PurchaseInRecord,
  PurchaseReturnRecord,
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
  approvePurchaseReturnApi,
  createPurchaseReturnApi,
  deletePurchaseReturnApi,
  listCounterpartiesApi,
  getPurchaseInApi,
  listPurchaseInsApi,
  listPurchaseReturnsApi,
  listProductsApi,
  listSettlementAccountsApi,
  reversePurchaseReturnApi,
  updatePurchaseReturnApi,
} from '#/modules/erp/api/erp';
import ErpRemoteSelect from '#/modules/erp/components/erp-remote-select.vue';
import { compareDecimal, normalizeDecimal, subtractDecimal, QUANTITY_DECIMAL_PLACES } from '#/modules/erp/utils/decimal';

interface ReturnLine {
  purchase_in_item_id: string;
  quantity: string;
}

const drawerOpen = ref(false);
const saving = ref(false);
const reverseOpen = ref(false);
const reverseTarget = ref<PurchaseReturnRecord>();
const editingReturn = ref<PurchaseReturnRecord>();
const selectedReceiptId = ref<string>();
const settlementAccountId = ref<string>();
const businessAt = ref<string>();
const discountRate = ref(0);
const discountAmount = ref<number>();
const otherFee = ref(0);
const receipts = ref<PurchaseInRecord[]>([]);
const settlementAccounts = ref<SettlementAccountRecord[]>([]);
const returnLines = ref<ReturnLine[]>([]);
const products = ref<ProductRecord[]>([]);
const suppliers = ref<CounterpartyRecord[]>([]);
const listQuery = ref<DocumentQuery>({});
const exportQuery = computed(() =>
  Object.fromEntries(
    Object.entries(listQuery.value).filter(
      (entry): entry is [string, string] =>
        typeof entry[1] === 'string' && Boolean(entry[1]),
    ),
  ),
);
const selectedReceipt = computed(() => receipts.value.find((receipt) => receipt.id === selectedReceiptId.value));

const [Grid, gridApi] = useVbenVxeGrid({
  gridOptions: {
    columns: [
      { field: 'no', minWidth: 190, title: '采购退货单号' }, { field: 'purchase_in_no', minWidth: 190, title: '来源采购入库' },
      { field: 'supplier_name', minWidth: 160, title: '供应商' }, { field: 'business_at', title: '退货日期', width: 180 },
      { field: 'total_quantity', title: '退货数量', width: 110 }, { field: 'status', slots: { default: 'status' }, title: '状态', width: 90 },
      { field: 'version', title: '版本', width: 70 }, { align: 'center', field: 'operation', fixed: 'right', slots: { default: 'operation' }, title: '操作', width: 320 },
    ], height: 'auto',
    proxyConfig: { ajax: { query: async ({ page }) => await listPurchaseReturnsApi({ ...listQuery.value, page: page.currentPage, page_size: page.pageSize }) } },
    rowConfig: { keyField: 'id' }, toolbarConfig: { custom: true, refresh: true, zoom: true },
  } as VxeTableGridOptions<PurchaseReturnRecord>,
});

async function loadFilterReferences() {
  const [supplierResult, productResult] = await Promise.all([
    listCounterpartiesApi('supplier', { page: 1, page_size: 50 }),
    listProductsApi({ page: 1, page_size: 50 }),
  ]);
  suppliers.value = supplierResult.items.filter((item) => item.is_active);
  products.value = productResult.items.filter((item) => item.is_active);
}

onMounted(() => void loadFilterReferences());

async function loadSuppliers(keyword: string) {
  const result = await listCounterpartiesApi('supplier', { keyword, page: 1, page_size: 50 });
  suppliers.value = result.items.filter((item) => item.is_active);
  return suppliers.value;
}

async function loadProducts(keyword: string) {
  const result = await listProductsApi({ keyword, page: 1, page_size: 50 });
  products.value = result.items.filter((item) => item.is_active);
  return products.value;
}

function remainingQuantity(item: NonNullable<PurchaseInRecord['items']>[number]) {
  return subtractDecimal(item.quantity, item.returned_quantity, QUANTITY_DECIMAL_PLACES);
}

function formatReceipt(receipt: PurchaseInRecord) { return { label: `${receipt.no} - ${receipt.supplier_name}`, value: receipt.id }; }
function formatSettlementAccount(account: SettlementAccountRecord) { return { label: account.name, value: account.id }; }
async function loadReceipts(keyword: string) {
  const result = await listPurchaseInsApi({ keyword, page: 1, page_size: 50 });
  receipts.value = result.items.filter((receipt) => receipt.status === 'approved' && (receipt.items ?? []).some((item) => compareDecimal(remainingQuantity(item), 0) > 0));
  return receipts.value;
}
async function loadSettlementAccounts(keyword: string) {
  const result = await listSettlementAccountsApi({ keyword, page: 1, page_size: 50 });
  settlementAccounts.value = result.items.filter((account) => account.is_active);
  return settlementAccounts.value;
}

function selectReceipt(receiptId: unknown) {
  if (typeof receiptId !== 'string') return;
  const receipt = receipts.value.find((entry) => entry.id === receiptId);
  settlementAccountId.value = receipt?.settlement_account_id || undefined;
  returnLines.value = (receipt?.items ?? []).filter((item) => compareDecimal(remainingQuantity(item), 0) > 0).map((item) => ({ purchase_in_item_id: item.id, quantity: remainingQuantity(item) }));
}

async function openCreate() {
  selectedReceiptId.value = undefined;
  settlementAccountId.value = undefined;
  businessAt.value = undefined;
  discountRate.value = 0;
  discountAmount.value = undefined;
  otherFee.value = 0;
  returnLines.value = [];
  editingReturn.value = undefined;
  drawerOpen.value = true;
}

async function openEdit(row: PurchaseReturnRecord) {
  await openCreate();
  editingReturn.value = row;
  const receipt = await getPurchaseInApi(row.purchase_in_id);
  receipts.value = [receipt];
  selectedReceiptId.value = row.purchase_in_id;
  settlementAccountId.value = row.settlement_account_id || undefined;
  businessAt.value = new Date(row.business_at).toISOString().slice(0, 16);
  discountRate.value = Number(row.discount_rate);
  discountAmount.value = Number(row.discount_amount);
  otherFee.value = Number(row.other_fee);
  returnLines.value = (row.items || []).map((line) => ({ purchase_in_item_id: line.purchase_in_item_id, quantity: normalizeDecimal(line.quantity, QUANTITY_DECIMAL_PLACES) }));
}

async function submit() {
  if (!selectedReceipt.value || returnLines.value.length === 0 || returnLines.value.some((line) => compareDecimal(line.quantity, 0) <= 0)) return;
  saving.value = true;
  try {
    const payload = { purchase_in_id: selectedReceipt.value.id, settlement_account_id: settlementAccountId.value, business_at: businessAt.value ? new Date(businessAt.value).toISOString() : undefined, discount_rate: String(discountRate.value || 0), discount_amount: discountAmount.value === undefined ? undefined : String(discountAmount.value), other_fee: String(otherFee.value || 0), items: returnLines.value.map((line) => ({ purchase_in_item_id: line.purchase_in_item_id, quantity: normalizeDecimal(line.quantity, QUANTITY_DECIMAL_PLACES) })) };
    if (editingReturn.value) await updatePurchaseReturnApi(editingReturn.value.id, payload, editingReturn.value.version);
    else await createPurchaseReturnApi(payload);
    drawerOpen.value = false;
    gridApi.query();
  } finally { saving.value = false; }
}

async function approve(row: PurchaseReturnRecord) { await approvePurchaseReturnApi(row.id, row.version); gridApi.query(); }
function openReverse(row: PurchaseReturnRecord) { reverseTarget.value = row; reverseOpen.value = true; }
async function confirmReverse(reason: string) { const row = reverseTarget.value; if (!row) return; await reversePurchaseReturnApi(row.id, row.version, reason); gridApi.query(); }
async function remove(row: PurchaseReturnRecord) { await deletePurchaseReturnApi(row.id); gridApi.query(); }
</script>

<template>
  <Page auto-content-height>
    <ReverseDocumentDialog v-model:open="reverseOpen" impact="反审核会恢复本次采购退货涉及的库存。" :on-confirm="confirmReverse" title="反审核采购退货" />
    <Drawer v-model:open="drawerOpen" :confirm-loading="saving" :title="editingReturn ? '编辑采购退货' : '新增采购退货'" class="w-[min(960px,calc(100vw-24px))]" placement="right">
      <div class="mb-4"><div class="mb-1 text-sm font-medium">来源采购入库单</div><ErpRemoteSelect v-model:value="selectedReceiptId" class="w-full" :format-option="formatReceipt" :load="loadReceipts" placeholder="选择已审核且可退货的采购入库单" @change="selectReceipt" /></div>
      <div v-if="selectedReceipt" class="mb-3 text-sm text-[var(--vben-text-color-secondary)]">供应商：{{ selectedReceipt.supplier_name }}，单据：{{ selectedReceipt.no }}</div>
      <div class="mb-4 grid gap-3 md:grid-cols-4"><Input v-model:value="businessAt" type="datetime-local" /><ErpRemoteSelect v-model:value="settlementAccountId" allow-clear :format-option="formatSettlementAccount" :load="loadSettlementAccounts" placeholder="结算账户" /><InputNumber v-model:value="discountRate" :max="100" :min="0" :precision="4" placeholder="优惠率 (%)" /><InputNumber v-model:value="discountAmount" :min="0" :precision="4" placeholder="优惠金额" /></div>
      <div class="mb-4 max-w-56"><InputNumber v-model:value="otherFee" :min="0" :precision="4" class="w-full" placeholder="其他费用" /></div>
      <div class="overflow-x-auto rounded border border-[var(--vben-border-color)]"><table class="min-w-[680px] w-full text-left text-sm"><thead><tr><th class="p-2">商品</th><th class="p-2">入库数量</th><th class="p-2">可退数量</th><th class="p-2">本次退货</th></tr></thead><tbody><tr v-for="line in returnLines" :key="line.purchase_in_item_id" class="border-t border-[var(--vben-border-color)]"><td class="p-2">{{ selectedReceipt?.items?.find((item) => item.id === line.purchase_in_item_id)?.product_name }}</td><td class="p-2">{{ selectedReceipt?.items?.find((item) => item.id === line.purchase_in_item_id)?.quantity }}</td><td class="p-2">{{ remainingQuantity(selectedReceipt?.items?.find((item) => item.id === line.purchase_in_item_id)!) }}</td><td class="p-2"><InputNumber v-model:value="line.quantity" :max="remainingQuantity(selectedReceipt?.items?.find((item) => item.id === line.purchase_in_item_id)!)" :min="'0.000001'" :precision="6" string-mode /></td></tr></tbody></table></div>
      <template #footer><div class="flex justify-end gap-2"><Button @click="drawerOpen = false">取消</Button><Button :loading="saving" type="primary" @click="submit">{{ editingReturn ? '保存修改' : '保存草稿' }}</Button></div></template>
    </Drawer>
    <DocumentListFilters v-model="listQuery" :counterparties="suppliers" :counterparty-loader="loadSuppliers" counterparty-key="supplier_id" counterparty-label="供应商" :products="products" :product-loader="loadProducts" @query="gridApi.query()" />
    <Grid table-title="采购退货列表">
      <template #toolbar-tools>
        <div class="flex items-center gap-1"><Button v-access:code="'erp:purchase-return:create'" class="gap-1" type="primary" @click="openCreate"><Plus class="size-5" /><span>新增采购退货</span></Button><ExportCsvButton file-name="采购退货列表.csv" permission="erp:purchase-return:export" :query="exportQuery" resource="purchase-return" /></div>
      </template>
      <template #status="{ row }"><Tag :color="row.status === 'approved' ? 'success' : 'default'">{{ row.status === 'approved' ? '已审批' : '草稿' }}</Tag></template>
      <template #operation="{ row }"><DocumentTableActions approve-impact="审批后将扣减库存并更新来源采购订单，确认继续吗？" approve-permission="erp:purchase-return:approve" delete-permission="erp:purchase-return:delete" :document-id="row.id" :document-no="row.no" document-type="purchase_return" reverse-permission="erp:purchase-return:reverse" :status="row.status" update-permission="erp:purchase-return:update" @approve="approve(row)" @delete="remove(row)" @edit="openEdit(row)" @reverse="openReverse(row)" /></template>
    </Grid>
  </Page>
</template>
