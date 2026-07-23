<script lang="ts" setup>
import type { VxeTableGridOptions } from '#/adapter/vxe-table';
import type {
  DocumentQuery,
  SaleOrderRecord,
  ProductRecord,
  SettlementAccountRecord,
  CounterpartyRecord,
} from '#/modules/erp/api/erp';

import { computed, onMounted, ref } from 'vue';
import { Page } from '@vben/common-ui';
import { Plus } from '@vben/icons';
import {
  Button,
  Drawer,
  Input,
  InputNumber,
  Tag,
} from 'ant-design-vue';
import { useVbenVxeGrid } from '#/adapter/vxe-table';
import DocumentListFilters from '#/modules/erp/components/document-list-filters.vue';
import DocumentTableActions from '#/modules/erp/components/document-table-actions.vue';
import ErpRemoteSelect from '#/modules/erp/components/erp-remote-select.vue';
import ExportCsvButton from '#/modules/erp/components/export-csv-button.vue';
import ReverseDocumentDialog from '#/modules/erp/components/reverse-document-dialog.vue';
import {
  approveSaleOrderApi,
  createSaleOrderApi,
  deleteSaleOrderApi,
  listCounterpartiesApi,
  listProductsApi,
  listSaleOrdersApi,
  listSettlementAccountsApi,
  reverseSaleOrderApi,
  updateSaleOrderApi,
} from '#/modules/erp/api/erp';

interface Line {
  product_id?: string;
  quantity?: number;
  remark?: string;
  tax_rate?: number;
  unit_price?: number;
}
const open = ref(false);
const saving = ref(false);
const customerId = ref<string>();
const settlementAccountId = ref<string>();
const businessAt = ref<string>();
const discountRate = ref<number>(0);
const discountAmount = ref<number>();
const depositAmount = ref<number>(0);
const orderRemark = ref<string>();
const lines = ref<Line[]>([{}]);
const editingOrder = ref<SaleOrderRecord>();
const products = ref<ProductRecord[]>([]);
const customers = ref<CounterpartyRecord[]>([]);
const settlementAccounts = ref<SettlementAccountRecord[]>([]);
const listQuery = ref<DocumentQuery>({});
const reverseOpen = ref(false);
const reverseTarget = ref<SaleOrderRecord>();
const exportQuery = computed(() =>
  Object.fromEntries(
    Object.entries(listQuery.value).filter(
      (entry): entry is [string, string] =>
        typeof entry[1] === 'string' && Boolean(entry[1]),
    ),
  ),
);
function queryParams() {
  return listQuery.value;
}

const [Grid, gridApi] = useVbenVxeGrid({
  gridOptions: {
    columns: [
      { field: 'no', minWidth: 190, title: '销售订单号' },
      { field: 'customer_name', minWidth: 180, title: '客户' },
      { field: 'business_at', title: '订单日期', width: 180 },
      { field: 'total_amount', title: '含税金额', width: 130 },
      {
        field: 'status',
        slots: { default: 'status' },
        title: '状态',
        width: 90,
      },
      { field: 'version', title: '版本', width: 70 },
      {
        align: 'center',
        field: 'operation',
        fixed: 'right',
        slots: { default: 'operation' },
        title: '操作',
        width: 320,
      },
    ],
    height: 'auto',
    proxyConfig: {
      ajax: {
        query: async ({ page }) =>
          await listSaleOrdersApi({
            ...queryParams(),
            page: page.currentPage,
            page_size: page.pageSize,
          }),
      },
    },
    rowConfig: { keyField: 'id' },
    toolbarConfig: { custom: true, refresh: true, zoom: true },
  } as VxeTableGridOptions<SaleOrderRecord>,
});

async function loadReferences() {
  const [customerResult, productResult, accountResult] = await Promise.all([
    listCounterpartiesApi('customer', { page: 1, page_size: 50 }),
    listProductsApi({ page: 1, page_size: 50 }),
    listSettlementAccountsApi({ page: 1, page_size: 50 }),
  ]);
  customers.value = customerResult.items.filter((item) => item.is_active);
  products.value = productResult.items.filter((item) => item.is_active);
  settlementAccounts.value = accountResult.items.filter((item) => item.is_active);
}
onMounted(() => void loadReferences());
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
async function loadSettlementAccounts(keyword: string) {
  const result = await listSettlementAccountsApi({ keyword, page: 1, page_size: 50 });
  settlementAccounts.value = result.items.filter((item) => item.is_active);
  return settlementAccounts.value;
}
function formatCustomer(item: CounterpartyRecord) { return { label: item.name, value: item.id }; }
function formatProduct(item: ProductRecord) { return { label: `${item.name} (${item.code})`, value: item.id }; }
function formatSettlementAccount(item: SettlementAccountRecord) { return { label: item.name, value: item.id }; }
async function openCreate() {
  editingOrder.value = undefined;
  customerId.value = undefined;
  settlementAccountId.value = undefined;
  businessAt.value = undefined;
  discountRate.value = 0;
  discountAmount.value = undefined;
  depositAmount.value = 0;
  orderRemark.value = undefined;
  lines.value = [{}];
  open.value = true;
}
async function openEdit(row: SaleOrderRecord) {
  await openCreate();
  editingOrder.value = row;
  customerId.value = row.customer_id;
  settlementAccountId.value = row.settlement_account_id || undefined;
  businessAt.value = row.business_at?.slice(0, 16);
  discountRate.value = Number(row.discount_rate);
  discountAmount.value = Number(row.discount_amount);
  depositAmount.value = Number(row.deposit_amount);
  orderRemark.value = row.remark || undefined;
  lines.value = (row.items ?? []).map((item) => ({
    product_id: item.product_id,
    quantity: Number(item.quantity),
    remark: item.remark || undefined,
    tax_rate: Number(item.tax_rate),
    unit_price: Number(item.unit_price),
  }));
}
function addLine() {
  lines.value.push({});
}
function removeLine(index: number) {
  lines.value.splice(index, 1);
}
function useSaleReferencePrice(line: Line, productId: unknown) {
  if (typeof productId !== 'string') return;
  const product = products.value.find((item) => item.id === productId);
  if (product && line.unit_price === undefined)
    line.unit_price = Number(product.sale_reference_price);
}
async function submit() {
  if (
    !customerId.value ||
    lines.value.some(
      (line) =>
        !line.product_id || !line.quantity || line.unit_price === undefined,
    )
  )
    return;
  saving.value = true;
  try {
    const payload = {
      customer_id: customerId.value,
      settlement_account_id: settlementAccountId.value,
      business_at: businessAt.value ? new Date(businessAt.value).toISOString() : undefined,
      discount_amount: discountAmount.value === undefined ? undefined : String(discountAmount.value),
      discount_rate: String(discountRate.value || 0),
      deposit_amount: String(depositAmount.value || 0),
      remark: orderRemark.value || undefined,
      items: lines.value.map((line) => ({
        product_id: line.product_id!,
        quantity: String(line.quantity),
        remark: line.remark || undefined,
        unit_price: String(line.unit_price),
        tax_rate: String(line.tax_rate || 0),
      })),
    };
    if (editingOrder.value)
      await updateSaleOrderApi(
        editingOrder.value.id,
        payload,
        editingOrder.value.version,
      );
    else await createSaleOrderApi(payload);
    open.value = false;
    gridApi.query();
  } finally {
    saving.value = false;
  }
}
async function approve(row: SaleOrderRecord) {
  await approveSaleOrderApi(row.id, row.version);
  gridApi.query();
}
function openReverse(row: SaleOrderRecord) {
  reverseTarget.value = row;
  reverseOpen.value = true;
}
async function confirmReverse(reason: string) {
  const row = reverseTarget.value;
  if (!row) return;
  await reverseSaleOrderApi(row.id, row.version, reason);
  gridApi.query();
}
async function remove(row: SaleOrderRecord) {
  await deleteSaleOrderApi(row.id);
  gridApi.query();
}
</script>

<template>
  <Page auto-content-height>
    <ReverseDocumentDialog
      v-model:open="reverseOpen"
      impact="反审核后，销售订单将恢复为草稿，不能再作为已审核销售依据。"
      :on-confirm="confirmReverse"
      title="反审核销售订单"
    />
    <Drawer
      v-model:open="open"
      :confirm-loading="saving"
      :title="editingOrder ? '编辑销售订单' : '新增销售订单'"
      class="w-[min(1080px,calc(100vw-24px))]"
      placement="right"
    >
      <div class="mb-4">
        <div class="mb-1 text-sm font-medium">客户</div>
        <ErpRemoteSelect
          v-model:value="customerId"
          class="w-full"
          :format-option="formatCustomer"
          :load="loadCustomers"
          placeholder="选择客户"
        />
      </div>
      <div class="mb-4">
        <div class="mb-1 text-sm font-medium">结算账户</div>
        <ErpRemoteSelect
          v-model:value="settlementAccountId"
          allow-clear
          class="w-full"
          :format-option="formatSettlementAccount"
          :load="loadSettlementAccounts"
          placeholder="选择结算账户"
        />
      </div>
      <div class="mb-4 grid gap-3 md:grid-cols-4">
        <Input v-model:value="businessAt" type="datetime-local" />
        <InputNumber v-model:value="discountRate" :max="100" :min="0" :precision="4" placeholder="优惠率 (%)" />
        <InputNumber v-model:value="discountAmount" :min="0" :precision="4" placeholder="优惠金额" />
        <InputNumber v-model:value="depositAmount" :min="0" :precision="4" placeholder="订金" />
      </div>
      <Input v-model:value="orderRemark" class="mb-4" :maxlength="500" placeholder="订单备注" />
      <div
        class="overflow-x-auto rounded border border-[var(--vben-border-color)]"
      >
        <table class="min-w-[760px] w-full text-left text-sm">
          <thead>
            <tr>
              <th class="p-2">商品</th>
              <th class="p-2">数量</th>
              <th class="p-2">行备注</th>
              <th class="p-2">销售单价</th>
              <th class="p-2">税率 (%)</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            <tr
              v-for="(line, index) in lines"
              :key="index"
              class="border-t border-[var(--vben-border-color)]"
            >
              <td class="p-2">
                <ErpRemoteSelect
                  v-model:value="line.product_id"
                  class="min-w-72"
                  :format-option="formatProduct"
                  :load="loadProducts"
                  @change="useSaleReferencePrice(line, $event)"
                />
              </td>
              <td class="p-2">
                <InputNumber
                  v-model:value="line.quantity"
                  :min="0.000001"
                  :precision="6"
                />
              </td>
              <td class="p-2"><Input v-model:value="line.remark" :maxlength="500" placeholder="行备注" /></td>
              <td class="p-2">
                <InputNumber
                  v-model:value="line.unit_price"
                  :min="0"
                  :precision="4"
                />
              </td>
              <td class="p-2">
                <InputNumber
                  v-model:value="line.tax_rate"
                  :min="0"
                  :max="100"
                  :precision="4"
                />
              </td>
              <td>
                <Button
                  :disabled="lines.length === 1"
                  danger
                  size="small"
                  type="link"
                  @click="removeLine(index)"
                  >删除</Button
                >
              </td>
            </tr>
          </tbody>
        </table>
      </div>
      <Button class="mt-3" type="dashed" @click="addLine">新增明细行</Button>
      <template #footer>
        <div class="flex justify-end gap-2">
          <Button @click="open = false">取消</Button>
          <Button :loading="saving" type="primary" @click="submit">保存草稿</Button>
        </div>
      </template>
    </Drawer>
    <DocumentListFilters
      v-model="listQuery"
      :counterparties="customers"
      :counterparty-loader="loadCustomers"
      counterparty-key="customer_id"
      counterparty-label="客户"
      :products="products"
      :product-loader="loadProducts"
      @query="gridApi.query()"
    />
    <Grid table-title="销售订单列表">
      <template #toolbar-tools>
        <div class="flex items-center gap-1">
          <Button v-access:code="'erp:sale-order:create'" class="gap-1" type="primary" @click="openCreate"><Plus class="size-5" /><span>新增销售订单</span></Button>
          <ExportCsvButton file-name="销售订单列表.csv" permission="erp:sale-order:export" :query="exportQuery" resource="sale-order" />
        </div>
      </template>
      <template #status="{ row }">
        <Tag :color="row.status === 'approved' ? 'success' : 'default'">{{
          row.status === 'approved' ? '已审批' : '草稿'
        }}</Tag>
      </template>
      <template #operation="{ row }">
        <DocumentTableActions approve-impact="审批后可用于销售出库，确认继续吗？" approve-permission="erp:sale-order:approve" delete-permission="erp:sale-order:delete" :document-id="row.id" :document-no="row.no" document-type="sale_order" reverse-permission="erp:sale-order:reverse" :status="row.status" update-permission="erp:sale-order:update" @approve="approve(row)" @delete="remove(row)" @edit="openEdit(row)" @reverse="openReverse(row)" />
      </template>
    </Grid>
  </Page>
</template>
