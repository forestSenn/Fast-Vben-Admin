<script lang="ts" setup>
import type { VxeTableGridOptions } from '#/adapter/vxe-table';
import type {
  CounterpartyRecord,
  DocumentQuery,
  PurchaseInRecord,
  PurchaseOrderRecord,
  ProductRecord,
  SettlementAccountRecord,
  WarehouseRecord,
} from '#/modules/erp/api/erp';

import { computed, onMounted, ref, watch } from 'vue';
import { useRoute } from 'vue-router';

import { Page } from '@vben/common-ui';
import { Plus } from '@vben/icons';
import { Button, Drawer, Empty, Input, InputNumber, Tag } from 'ant-design-vue';
import BigNumber from 'bignumber.js';

import { useVbenVxeGrid } from '#/adapter/vxe-table';
import DocumentListFilters from '#/modules/erp/components/document-list-filters.vue';
import DocumentTableActions from '#/modules/erp/components/document-table-actions.vue';
import ExportCsvButton from '#/modules/erp/components/export-csv-button.vue';
import ReverseDocumentDialog from '#/modules/erp/components/reverse-document-dialog.vue';
import {
  approvePurchaseInApi,
  createPurchaseInApi,
  deletePurchaseInApi,
  listCounterpartiesApi,
  getPurchaseOrderApi,
  listPurchaseInsApi,
  listPurchaseOrdersApi,
  listProductsApi,
  listSettlementAccountsApi,
  listWarehousesApi,
  reversePurchaseInApi,
  updatePurchaseInApi,
} from '#/modules/erp/api/erp';
import ErpRemoteSelect from '#/modules/erp/components/erp-remote-select.vue';
import {
  compareDecimal,
  formatDecimal,
  normalizeDecimal,
  QUANTITY_DECIMAL_PLACES,
  subtractDecimal,
} from '#/modules/erp/utils/decimal';

interface ReceiptLine {
  purchase_order_item_id: string;
  quantity: string;
  warehouse_id?: string;
}

const drawerOpen = ref(false);
const saving = ref(false);
const reverseOpen = ref(false);
const reverseTarget = ref<PurchaseInRecord>();
const editingReceipt = ref<PurchaseInRecord>();
const selectedOrderId = ref<string>();
const settlementAccountId = ref<string>();
const businessAt = ref<string>();
const discountRate = ref(0);
const discountAmount = ref<number>();
const otherFee = ref(0);
const purchaseOrders = ref<PurchaseOrderRecord[]>([]);
const warehouses = ref<WarehouseRecord[]>([]);
const settlementAccounts = ref<SettlementAccountRecord[]>([]);
const receiptLines = ref<ReceiptLine[]>([]);
const products = ref<ProductRecord[]>([]);
const suppliers = ref<CounterpartyRecord[]>([]);
const listQuery = ref<DocumentQuery>({});
const route = useRoute();
const exportQuery = computed(() =>
  Object.fromEntries(
    Object.entries(listQuery.value).filter(
      (entry): entry is [string, string] =>
        typeof entry[1] === 'string' && Boolean(entry[1]),
    ),
  ),
);

const selectedOrder = computed(() =>
  purchaseOrders.value.find((order) => order.id === selectedOrderId.value),
);
const receiptLineRows = computed(() => {
  const orderItems = new Map(
    (selectedOrder.value?.items ?? []).map((item) => [item.id, item]),
  );
  return receiptLines.value.flatMap((line) => {
    const orderItem = orderItems.get(line.purchase_order_item_id);
    return orderItem
      ? [{ line, orderItem, remaining: remainingQuantity(orderItem) }]
      : [];
  });
});
const receiptSummary = computed(() => {
  let quantity = new BigNumber(0);
  let productAmount = new BigNumber(0);
  let taxAmount = new BigNumber(0);

  for (const { line, orderItem } of receiptLineRows.value) {
    const lineQuantity = toDecimal(line.quantity);
    const lineProductAmount = lineQuantity
      .times(toDecimal(orderItem.unit_price))
      .decimalPlaces(4, BigNumber.ROUND_HALF_UP);
    quantity = quantity.plus(lineQuantity);
    productAmount = productAmount.plus(lineProductAmount);
    taxAmount = taxAmount.plus(
      lineProductAmount
        .times(toDecimal(orderItem.tax_rate))
        .dividedBy(100)
        .decimalPlaces(4, BigNumber.ROUND_HALF_UP),
    );
  }

  return {
    productAmount,
    quantity,
    taxAmount,
    totalAmount: productAmount.plus(taxAmount),
  };
});

const [Grid, gridApi] = useVbenVxeGrid({
  gridOptions: {
    columns: [
      { field: 'no', minWidth: 190, title: '采购入库单号' },
      { field: 'purchase_order_no', minWidth: 190, title: '来源采购订单' },
      { field: 'supplier_name', minWidth: 160, title: '供应商' },
      { field: 'business_at', title: '入库日期', width: 180 },
      { field: 'total_quantity', title: '入库数量', width: 110 },
      { field: 'status', slots: { default: 'status' }, title: '状态', width: 90 },
      { field: 'version', title: '版本', width: 70 },
      { align: 'center', field: 'operation', fixed: 'right', slots: { default: 'operation' }, title: '操作', width: 320 },
    ],
    height: 'auto',
    proxyConfig: { ajax: { query: async ({ page }) => await listPurchaseInsApi({ ...listQuery.value, page: page.currentPage, page_size: page.pageSize }) } },
    rowConfig: { keyField: 'id' },
    toolbarConfig: { custom: true, refresh: true, zoom: true },
  } as VxeTableGridOptions<PurchaseInRecord>,
});

async function loadFilterReferences() {
  const [supplierResult, productResult] = await Promise.all([
    listCounterpartiesApi('supplier', { page: 1, page_size: 50 }),
    listProductsApi({ page: 1, page_size: 50 }),
  ]);
  suppliers.value = supplierResult.items.filter((item) => item.is_active);
  products.value = productResult.items.filter((item) => item.is_active);
}

onMounted(() => {
  void loadFilterReferences();
});

watch(
  () => route.query.purchase_order_id,
  (orderId) => {
    if (typeof orderId === 'string') void openCreateFromPurchaseOrder(orderId);
  },
  { immediate: true },
);

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

function remainingQuantity(item: NonNullable<PurchaseOrderRecord['items']>[number]) {
  return subtractDecimal(item.quantity, item.received_quantity, QUANTITY_DECIMAL_PLACES);
}

function toDecimal(value: null | number | string | undefined) {
  const decimal = new BigNumber(value ?? 0);
  return decimal.isFinite() ? decimal : new BigNumber(0);
}

function formatQuantity(value: null | number | string | undefined) {
  return normalizeDecimal(value, QUANTITY_DECIMAL_PLACES);
}

function formatMoney(value: BigNumber.Value | null | undefined) {
  return formatDecimal(value, 2);
}

function formatRate(value: null | number | string | undefined) {
  return normalizeDecimal(value, 4);
}

function formatOrder(order: PurchaseOrderRecord) { return { label: `${order.no} - ${order.supplier_name}`, value: order.id }; }
function formatWarehouse(warehouse: WarehouseRecord) { return { label: `${warehouse.name} (${warehouse.code})`, value: warehouse.id }; }
function formatSettlementAccount(account: SettlementAccountRecord) { return { label: account.name, value: account.id }; }
async function loadPurchaseOrders(keyword: string) {
  const result = await listPurchaseOrdersApi({ keyword, page: 1, page_size: 50 });
  purchaseOrders.value = result.items.filter((order) => order.status === 'approved' && (order.items ?? []).some((item) => compareDecimal(remainingQuantity(item), 0) > 0));
  return purchaseOrders.value;
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
  if (typeof orderId !== 'string') {
    settlementAccountId.value = undefined;
    receiptLines.value = [];
    return;
  }
  const order = purchaseOrders.value.find((entry) => entry.id === orderId);
  settlementAccountId.value = order?.settlement_account_id || undefined;
  receiptLines.value = (order?.items ?? [])
    .filter((item) => compareDecimal(remainingQuantity(item), 0) > 0)
    .map((item) => ({
      purchase_order_item_id: item.id,
      quantity: remainingQuantity(item),
    }));
}

async function openCreate() {
  selectedOrderId.value = undefined;
  settlementAccountId.value = undefined;
  businessAt.value = undefined;
  discountRate.value = 0;
  discountAmount.value = undefined;
  otherFee.value = 0;
  receiptLines.value = [];
  editingReceipt.value = undefined;
  drawerOpen.value = true;
}

async function openCreateFromPurchaseOrder(orderId: string) {
  await openCreate();
  const order = await getPurchaseOrderApi(orderId);
  purchaseOrders.value = [order];
  selectedOrderId.value = order.id;
  selectOrder(order.id);
}

async function openEdit(row: PurchaseInRecord) {
  await openCreate();
  editingReceipt.value = row;
  const order = await getPurchaseOrderApi(row.purchase_order_id);
  purchaseOrders.value = [order];
  selectedOrderId.value = row.purchase_order_id;
  settlementAccountId.value = row.settlement_account_id || undefined;
  businessAt.value = new Date(row.business_at).toISOString().slice(0, 16);
  discountRate.value = Number(row.discount_rate);
  discountAmount.value = Number(row.discount_amount);
  otherFee.value = Number(row.other_fee);
  receiptLines.value = (row.items || []).map((line) => ({ purchase_order_item_id: line.purchase_order_item_id, quantity: normalizeDecimal(line.quantity, QUANTITY_DECIMAL_PLACES), warehouse_id: line.warehouse_id }));
}

async function submit() {
  if (!selectedOrder.value || receiptLines.value.length === 0 || receiptLines.value.some((line) => !line.warehouse_id || compareDecimal(line.quantity, 0) <= 0)) return;
  saving.value = true;
  try {
    const payload = {
      purchase_order_id: selectedOrder.value.id,
      settlement_account_id: settlementAccountId.value,
      business_at: businessAt.value ? new Date(businessAt.value).toISOString() : undefined,
      discount_rate: String(discountRate.value || 0),
      discount_amount: discountAmount.value === undefined ? undefined : String(discountAmount.value),
      other_fee: String(otherFee.value || 0),
      items: receiptLines.value.map((line) => ({
        purchase_order_item_id: line.purchase_order_item_id,
        quantity: normalizeDecimal(line.quantity, QUANTITY_DECIMAL_PLACES),
        warehouse_id: line.warehouse_id!,
      })),
    };
    if (editingReceipt.value) await updatePurchaseInApi(editingReceipt.value.id, payload, editingReceipt.value.version);
    else await createPurchaseInApi(payload);
    drawerOpen.value = false;
    gridApi.query();
  } finally {
    saving.value = false;
  }
}

async function remove(row: PurchaseInRecord) { await deletePurchaseInApi(row.id); gridApi.query(); }

async function approve(row: PurchaseInRecord) {
  await approvePurchaseInApi(row.id, row.version);
  gridApi.query();
}

function openReverse(row: PurchaseInRecord) {
  reverseTarget.value = row;
  reverseOpen.value = true;
}
async function confirmReverse(reason: string) {
  const row = reverseTarget.value;
  if (!row) return;
  await reversePurchaseInApi(row.id, row.version, reason);
  gridApi.query();
}
</script>

<template>
  <Page auto-content-height>
    <ReverseDocumentDialog v-model:open="reverseOpen" impact="反审核会回退本次入库库存；已有采购退货时将被后端阻止。" :on-confirm="confirmReverse" title="反审核采购入库" />
    <Drawer
      v-model:open="drawerOpen"
      :confirm-loading="saving"
      placement="right"
      :title="editingReceipt ? '编辑采购入库' : '新增采购入库'"
      width="min(1040px, calc(100vw - 24px))"
    >
      <div class="mb-4">
        <div class="mb-1 text-sm font-medium">来源采购订单</div>
        <ErpRemoteSelect
          v-model:value="selectedOrderId"
          class="w-full"
          :format-option="formatOrder"
          :load="loadPurchaseOrders"
          placeholder="请选择已审核且有剩余数量的采购订单"
          @change="selectOrder"
        />
      </div>
      <div
        v-if="selectedOrder"
        class="mb-4 rounded bg-muted px-3 py-2 text-sm text-[var(--vben-text-color-secondary)]"
      >
        供应商：{{ selectedOrder.supplier_name }}，采购订单：{{ selectedOrder.no }}
      </div>
      <div class="mb-5 grid grid-cols-1 gap-x-4 gap-y-3 md:grid-cols-2 xl:grid-cols-3">
        <div>
          <div class="mb-1 text-sm font-medium">入库日期</div>
          <Input v-model:value="businessAt" class="w-full" type="datetime-local" />
        </div>
        <div>
          <div class="mb-1 text-sm font-medium">结算账户</div>
          <ErpRemoteSelect
            v-model:value="settlementAccountId"
            allow-clear
            class="w-full"
            :format-option="formatSettlementAccount"
            :load="loadSettlementAccounts"
            placeholder="请选择结算账户"
          />
        </div>
        <div>
          <div class="mb-1 text-sm font-medium">优惠率(%)</div>
          <InputNumber
            v-model:value="discountRate"
            :max="100"
            :min="0"
            :precision="4"
            placeholder="请输入优惠率"
            style="width: 100%"
          />
        </div>
        <div>
          <div class="mb-1 text-sm font-medium">优惠金额</div>
          <InputNumber
            v-model:value="discountAmount"
            :min="0"
            :precision="4"
            placeholder="请输入优惠金额"
            style="width: 100%"
          />
        </div>
        <div>
          <div class="mb-1 text-sm font-medium">其他费用</div>
          <InputNumber
            v-model:value="otherFee"
            :min="0"
            :precision="4"
            placeholder="请输入其他费用"
            style="width: 100%"
          />
        </div>
      </div>
      <div class="mb-2 text-sm font-medium">采购产品清单</div>
      <div
        v-if="!selectedOrder"
        class="rounded border border-[var(--vben-border-color)] py-10"
      >
        <Empty
          :image="Empty.PRESENTED_IMAGE_SIMPLE"
          description="请选择来源采购订单"
        />
      </div>
      <div
        v-else-if="receiptLineRows.length === 0"
        class="rounded border border-[var(--vben-border-color)] py-10"
      >
        <Empty
          :image="Empty.PRESENTED_IMAGE_SIMPLE"
          description="该采购订单没有可入库产品"
        />
      </div>
      <div v-else>
        <div
          class="overflow-x-auto rounded border border-[var(--vben-border-color)]"
        >
          <table class="w-full min-w-[1080px] text-left text-sm">
            <thead class="bg-muted text-[var(--vben-text-color-secondary)]">
              <tr>
                <th class="w-14 px-3 py-2.5 text-center font-medium">序号</th>
                <th class="w-56 px-3 py-2.5 font-medium">入库仓库</th>
                <th class="min-w-48 px-3 py-2.5 font-medium">商品</th>
                <th class="w-20 px-3 py-2.5 font-medium">单位</th>
                <th class="w-28 px-3 py-2.5 text-right font-medium">订单数量</th>
                <th class="w-28 px-3 py-2.5 text-right font-medium">已入库</th>
                <th class="w-28 px-3 py-2.5 text-right font-medium">剩余数量</th>
                <th class="w-40 px-3 py-2.5 font-medium">本次入库</th>
                <th class="w-32 px-3 py-2.5 text-right font-medium">单价 / 税率</th>
              </tr>
            </thead>
            <tbody>
              <tr
                v-for="({ line, orderItem, remaining }, index) in receiptLineRows"
                :key="line.purchase_order_item_id"
                class="border-t border-[var(--vben-border-color)]"
              >
                <td class="px-3 py-2.5 text-center text-[var(--vben-text-color-secondary)]">
                  {{ index + 1 }}
                </td>
                <td class="px-3 py-2.5">
                  <ErpRemoteSelect
                    v-model:value="line.warehouse_id"
                    class="w-full min-w-48"
                    :format-option="formatWarehouse"
                    :load="loadWarehouses"
                    placeholder="请选择仓库"
                  />
                </td>
                <td class="px-3 py-2.5">
                  <div class="font-medium">{{ orderItem.product_name }}</div>
                  <div class="mt-0.5 text-xs text-[var(--vben-text-color-secondary)]">
                    {{ orderItem.product_barcode || '无条码' }}
                  </div>
                </td>
                <td class="px-3 py-2.5">{{ orderItem.unit_name }}</td>
                <td class="px-3 py-2.5 text-right tabular-nums">
                  {{ formatQuantity(orderItem.quantity) }}
                </td>
                <td class="px-3 py-2.5 text-right tabular-nums">
                  {{ formatQuantity(orderItem.received_quantity) }}
                </td>
                <td class="px-3 py-2.5 text-right tabular-nums">
                  {{ formatQuantity(remaining) }}
                </td>
                <td class="px-3 py-2.5">
                  <InputNumber
                    v-model:value="line.quantity"
                    class="w-full"
                    :max="remaining"
                    :min="'0.000001'"
                    :precision="6"
                    string-mode
                  />
                </td>
                <td class="px-3 py-2.5 text-right tabular-nums">
                  <div>{{ formatMoney(orderItem.unit_price) }}</div>
                  <div class="mt-0.5 text-xs text-[var(--vben-text-color-secondary)]">
                    税率 {{ formatRate(orderItem.tax_rate) }}%
                  </div>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
        <div
          class="mt-2 flex flex-wrap items-center justify-between gap-x-4 gap-y-2 rounded border border-[var(--vben-border-color)] bg-muted px-3 py-2 text-sm"
        >
          <span class="font-medium">明细合计</span>
          <div
            class="flex flex-wrap justify-end gap-x-5 gap-y-1 text-[var(--vben-text-color-secondary)]"
          >
            <span>数量：{{ formatQuantity(receiptSummary.quantity.toFixed()) }}</span>
            <span>商品金额：{{ formatMoney(receiptSummary.productAmount) }}</span>
            <span>税额：{{ formatMoney(receiptSummary.taxAmount) }}</span>
            <span class="font-medium text-[var(--vben-text-color)]">
              价税合计：{{ formatMoney(receiptSummary.totalAmount) }}
            </span>
          </div>
        </div>
      </div>
      <template #footer><div class="flex justify-end gap-2"><Button @click="drawerOpen = false">取消</Button><Button :loading="saving" type="primary" @click="submit">{{ editingReceipt ? '保存修改' : '保存草稿' }}</Button></div></template>
    </Drawer>
    <DocumentListFilters
      v-model="listQuery"
      :counterparties="suppliers"
      :counterparty-loader="loadSuppliers"
      counterparty-key="supplier_id"
      counterparty-label="供应商"
      :products="products"
      :product-loader="loadProducts"
      @query="gridApi.query()"
    />
    <Grid table-title="采购入库列表">
      <template #toolbar-tools>
        <div class="flex items-center gap-1">
          <Button v-access:code="'erp:purchase-in:create'" class="gap-1" type="primary" @click="openCreate"><Plus class="size-5" /><span>新增采购入库</span></Button>
          <ExportCsvButton file-name="采购入库列表.csv" permission="erp:purchase-in:export" :query="exportQuery" resource="purchase-in" />
        </div>
      </template>
      <template #status="{ row }"><Tag :color="row.status === 'approved' ? 'success' : 'default'">{{ row.status === 'approved' ? '已审批' : '草稿' }}</Tag></template>
      <template #operation="{ row }">
        <DocumentTableActions
          approve-impact="审批后将增加库存并占用采购订单剩余数量，确认继续吗？"
          approve-permission="erp:purchase-in:approve"
          delete-permission="erp:purchase-in:delete"
          :document-id="row.id"
          :document-no="row.no"
          document-type="purchase_in"
          reverse-permission="erp:purchase-in:reverse"
          :status="row.status"
          update-permission="erp:purchase-in:update"
          @approve="approve(row)"
          @delete="remove(row)"
          @edit="openEdit(row)"
          @reverse="openReverse(row)"
        />
      </template>
    </Grid>
  </Page>
</template>
