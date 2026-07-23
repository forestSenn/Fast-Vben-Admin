<script lang="ts" setup>
import type { VxeTableGridOptions } from '#/adapter/vxe-table';
import type { FormInstance } from 'ant-design-vue';
import type {
  ProductRecord,
  CounterpartyRecord,
  DocumentQuery,
  StockDocumentRecord,
  WarehouseRecord,
} from '#/modules/erp/api/erp';

import { computed, onMounted, reactive, ref, watch } from 'vue';
import { useRoute } from 'vue-router';

import { Page } from '@vben/common-ui';
import { Plus } from '@vben/icons';

import {
  Button,
  Drawer,
  Form,
  Input,
  InputNumber,
  Segmented,
  Tag,
} from 'ant-design-vue';

import { useVbenVxeGrid } from '#/adapter/vxe-table';
import DocumentListFilters from '#/modules/erp/components/document-list-filters.vue';
import DocumentTableActions from '#/modules/erp/components/document-table-actions.vue';
import ErpRemoteSelect from '#/modules/erp/components/erp-remote-select.vue';
import ExportCsvButton from '#/modules/erp/components/export-csv-button.vue';
import ReverseDocumentDialog from '#/modules/erp/components/reverse-document-dialog.vue';
import {
  approveStockDocumentApi,
  createStockDocumentApi,
  deleteStockDocumentApi,
  listProductsApi,
  listCounterpartiesApi,
  listStockDocumentsApi,
  listWarehousesApi,
  reverseStockDocumentApi,
  updateStockDocumentApi,
} from '#/modules/erp/api/erp';

type DocumentKind = 'check' | 'in' | 'move' | 'out';

interface DocumentLine {
  actual_quantity?: number;
  from_warehouse_id?: string;
  product_id?: string;
  quantity?: number;
  reference_price?: number;
  remark?: string;
  to_warehouse_id?: string;
  warehouse_id?: string;
}

interface DocumentFormValues {
  business_at?: string;
  counterparty_id?: string;
  remark?: string;
}

type StockDocumentItem = NonNullable<StockDocumentRecord['items']>[number];

const route = useRoute();

function kindForPath(path: string): DocumentKind {
  if (path === '/erp/stock/other-out') return 'out';
  if (path === '/erp/stock/move') return 'move';
  if (path === '/erp/stock/check') return 'check';
  return 'in';
}

const kind = ref<DocumentKind>(kindForPath(route.path));
const isDedicatedPage = computed(() => route.path !== '/erp/stock/documents');
const drawerOpen = ref(false);
const saving = ref(false);
const reverseOpen = ref(false);
const reverseTarget = ref<StockDocumentRecord>();
const formRef = ref<FormInstance>();
const products = ref<ProductRecord[]>([]);
const warehouses = ref<WarehouseRecord[]>([]);
const counterparties = ref<CounterpartyRecord[]>([]);
const documentForm = reactive<DocumentFormValues>({ remark: undefined });
const lines = ref<DocumentLine[]>([]);
const editingDocument = ref<StockDocumentRecord>();
const listQuery = ref<DocumentQuery>({});
const exportQuery = computed(() =>
  Object.fromEntries(
    Object.entries(listQuery.value).filter(
      (entry): entry is [string, string] =>
        typeof entry[1] === 'string' && Boolean(entry[1]),
    ),
  ),
);

const kindLabels: Record<DocumentKind, string> = {
  check: '库存盘点',
  in: '其他入库',
  move: '库存调拨',
  out: '其他出库',
};

const permissionPrefix: Record<DocumentKind, string> = {
  check: 'erp:stock-check',
  in: 'erp:stock-in',
  move: 'erp:stock-move',
  out: 'erp:stock-out',
};

const drawerTitle = computed(() => `${editingDocument.value ? '编辑' : '新增'}${kindLabels[kind.value]}`);
const lineQuantityLabel = computed(() =>
  kind.value === 'check' ? '实盘数量' : '数量',
);

const [Grid, gridApi] = useVbenVxeGrid({
  gridOptions: {
    columns: [
      { field: 'no', minWidth: 200, title: '单据编号' },
      { field: 'business_at', title: '业务日期', width: 180 },
      {
        field: 'status',
        slots: { default: 'status' },
        title: '状态',
        width: 96,
      },
      { field: 'total_quantity', title: '总数量', width: 120 },
      { field: 'total_amount', title: '总金额', width: 120 },
      { field: 'remark', minWidth: 240, showOverflow: true, title: '备注' },
      { field: 'version', title: '版本', width: 76 },
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
    keepSource: true,
    proxyConfig: {
      ajax: {
        query: async ({ page }) =>
          await listStockDocumentsApi(kind.value, {
            ...listQuery.value,
            page: page.currentPage,
            page_size: page.pageSize,
          }),
      },
    },
    rowConfig: { keyField: 'id' },
    toolbarConfig: { custom: true, refresh: true, search: true, zoom: true },
  } as VxeTableGridOptions<StockDocumentRecord>,
});

async function loadFilterReferences() {
  const [productResult, warehouseResult, counterpartyResult] = await Promise.all([
    listProductsApi({ page: 1, page_size: 50 }),
    listWarehousesApi({ page: 1, page_size: 50 }),
    listCounterpartiesApi(kind.value === 'in' ? 'supplier' : 'customer', { page: 1, page_size: 50 }),
  ]);
  products.value = productResult.items.filter((product) => product.is_active);
  warehouses.value = warehouseResult.items.filter((warehouse) => warehouse.is_active);
  counterparties.value = counterpartyResult.items.filter((counterparty) => counterparty.is_active);
}

onMounted(() => void loadFilterReferences());

function formatProduct(product: ProductRecord) { return { label: `${product.name} (${product.code})`, value: product.id }; }
function formatWarehouse(warehouse: WarehouseRecord) { return { label: `${warehouse.name} (${warehouse.code})`, value: warehouse.id }; }
function formatCounterparty(counterparty: CounterpartyRecord) { return { label: counterparty.name, value: counterparty.id }; }
async function loadProducts(keyword: string) {
  const result = await listProductsApi({ keyword, page: 1, page_size: 50 });
  products.value = result.items.filter((product) => product.is_active);
  return products.value;
}
async function loadWarehouses(keyword: string) {
  const result = await listWarehousesApi({ keyword, page: 1, page_size: 50 });
  warehouses.value = result.items.filter((warehouse) => warehouse.is_active);
  return warehouses.value;
}
async function loadCounterparties(keyword: string) {
  const result = await listCounterpartiesApi(kind.value === 'in' ? 'supplier' : 'customer', { keyword, page: 1, page_size: 50 });
  counterparties.value = result.items.filter((counterparty) => counterparty.is_active);
  return counterparties.value;
}

function resetDocument() {
  documentForm.business_at = undefined;
  documentForm.remark = undefined;
  documentForm.counterparty_id = undefined;
  lines.value = [{}];
  formRef.value?.clearValidate();
}

function numberOrUndefined(value: null | number | string | undefined) {
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : undefined;
}

function toDocumentLine(line: StockDocumentItem): DocumentLine {
  return {
    actual_quantity:
      'actual_quantity' in line ? numberOrUndefined(line.actual_quantity) : undefined,
    from_warehouse_id:
      'from_warehouse_id' in line ? line.from_warehouse_id : undefined,
    product_id: line.product_id,
    quantity: 'quantity' in line ? numberOrUndefined(line.quantity) : undefined,
    reference_price: numberOrUndefined(line.reference_price),
    remark: line.remark ?? undefined,
    to_warehouse_id: 'to_warehouse_id' in line ? line.to_warehouse_id : undefined,
    warehouse_id: 'warehouse_id' in line ? line.warehouse_id : undefined,
  };
}

async function openCreate() {
  resetDocument();
  editingDocument.value = undefined;
  drawerOpen.value = true;
}

async function openEdit(row: StockDocumentRecord) {
  editingDocument.value = row;
  documentForm.business_at = new Date(row.business_at).toISOString().slice(0, 16);
  documentForm.remark = row.remark || undefined;
  documentForm.counterparty_id = 'supplier_id' in row ? row.supplier_id || undefined : 'customer_id' in row ? row.customer_id || undefined : undefined;
  lines.value = row.items?.map(toDocumentLine) ?? [];
  drawerOpen.value = true;
}

function addLine() {
  lines.value.push({});
}

function removeLine(index: number) {
  lines.value.splice(index, 1);
}

function documentPayload() {
  const items = lines.value.map((line) => {
    if (!line.product_id) throw new Error('请选择商品');
    if (kind.value === 'move') {
      if (!line.from_warehouse_id || !line.to_warehouse_id || !line.quantity) {
        throw new Error('请完整填写调拨行');
      }
      return {
        from_warehouse_id: line.from_warehouse_id,
        product_id: line.product_id,
        quantity: String(line.quantity),
        reference_price: String(line.reference_price || 0),
        remark: line.remark || undefined,
        to_warehouse_id: line.to_warehouse_id,
      };
    }
    if (!line.warehouse_id) throw new Error('请选择仓库');
    if (kind.value === 'check') {
      if (line.actual_quantity === undefined || line.actual_quantity < 0) {
        throw new Error('请填写有效的实盘数量');
      }
      return {
        actual_quantity: String(line.actual_quantity),
        product_id: line.product_id,
        reference_price: String(line.reference_price || 0),
        remark: line.remark || undefined,
        warehouse_id: line.warehouse_id,
      };
    }
    if (!line.quantity || line.quantity <= 0) throw new Error('数量必须大于 0');
    return {
      product_id: line.product_id,
      quantity: String(line.quantity),
      reference_price: String(line.reference_price || 0),
      remark: line.remark || undefined,
      warehouse_id: line.warehouse_id,
    };
  });
  return {
    ...(kind.value === 'in' && documentForm.counterparty_id ? { supplier_id: documentForm.counterparty_id } : {}),
    ...(kind.value === 'out' && documentForm.counterparty_id ? { customer_id: documentForm.counterparty_id } : {}),
    business_at: documentForm.business_at ? new Date(documentForm.business_at).toISOString() : undefined,
    items,
    remark: documentForm.remark || undefined,
  };
}

async function submit() {
  await formRef.value?.validate();
  saving.value = true;
  try {
    if (editingDocument.value) {
      await updateStockDocumentApi(kind.value, editingDocument.value.id, documentPayload(), editingDocument.value.version);
    } else {
      await createStockDocumentApi(kind.value, documentPayload());
    }
    drawerOpen.value = false;
    gridApi.query();
  } finally {
    saving.value = false;
  }
}

async function remove(row: StockDocumentRecord) {
  await deleteStockDocumentApi(kind.value, row.id);
  gridApi.query();
}

async function approve(row: StockDocumentRecord) {
  await approveStockDocumentApi(kind.value, row.id, row.version);
  gridApi.query();
}

function openReverse(row: StockDocumentRecord) {
  reverseTarget.value = row;
  reverseOpen.value = true;
}

async function confirmReverse(reason: string) {
  const row = reverseTarget.value;
  if (!row) return;
  await reverseStockDocumentApi(kind.value, row.id, row.version, reason);
  gridApi.query();
}

function changeKind(value: DocumentKind) {
  kind.value = value;
  gridApi.query();
}

watch(
  () => route.path,
  (path) => {
    if (!isDedicatedPage.value) return;
    kind.value = kindForPath(path);
    gridApi.query();
  },
);

</script>

<template>
  <Page auto-content-height>
    <ReverseDocumentDialog
      v-model:open="reverseOpen"
      impact="反审核会生成冲销库存流水，并恢复该单据为草稿。"
      :on-confirm="confirmReverse"
      title="反审核库存单据"
    />
    <Drawer
      v-model:open="drawerOpen"
      :confirm-loading="saving"
      :title="drawerTitle"
      class="w-[min(1080px,calc(100vw-24px))]"
      placement="right"
      @close="() => { resetDocument(); editingDocument = undefined; }"
    >
      <Form ref="formRef" :model="documentForm" layout="vertical">
        <Form.Item label="业务时间" name="business_at">
          <Input v-model:value="documentForm.business_at" type="datetime-local" />
        </Form.Item>
        <Form.Item v-if="kind === 'in' || kind === 'out'" :label="kind === 'in' ? '供应商（可选）' : '客户（可选）'" name="counterparty_id">
          <ErpRemoteSelect v-model:value="documentForm.counterparty_id" allow-clear :format-option="formatCounterparty" :load="loadCounterparties" placeholder="选择往来单位" />
        </Form.Item>
        <div class="mb-4 overflow-x-auto rounded border border-[var(--vben-border-color)]">
          <table class="min-w-[800px] w-full border-collapse text-left text-sm">
            <thead class="bg-[var(--vben-bg-color-overlay)] text-[var(--vben-text-color-2)]">
              <tr>
                <th class="px-3 py-2 font-medium">商品</th>
                <th v-if="kind === 'move'" class="px-3 py-2 font-medium">调出仓库</th>
                <th v-if="kind === 'move'" class="px-3 py-2 font-medium">调入仓库</th>
                <th v-if="kind !== 'move'" class="px-3 py-2 font-medium">仓库</th>
                <th class="w-32 px-3 py-2 font-medium">{{ lineQuantityLabel }}</th>
                <th class="w-32 px-3 py-2 font-medium">参考单价</th>
                <th class="min-w-44 px-3 py-2 font-medium">行备注</th>
                <th class="w-16 px-3 py-2 font-medium"></th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="(line, index) in lines" :key="index" class="border-t border-[var(--vben-border-color)]">
                <td class="px-3 py-2">
                  <ErpRemoteSelect v-model:value="line.product_id" class="min-w-52" :format-option="formatProduct" :load="loadProducts" placeholder="选择商品" />
                </td>
                <td v-if="kind === 'move'" class="px-3 py-2">
                  <ErpRemoteSelect v-model:value="line.from_warehouse_id" class="min-w-44" :format-option="formatWarehouse" :load="loadWarehouses" placeholder="调出仓库" />
                </td>
                <td v-if="kind === 'move'" class="px-3 py-2">
                  <ErpRemoteSelect v-model:value="line.to_warehouse_id" class="min-w-44" :format-option="formatWarehouse" :load="loadWarehouses" placeholder="调入仓库" />
                </td>
                <td v-if="kind !== 'move'" class="px-3 py-2">
                  <ErpRemoteSelect v-model:value="line.warehouse_id" class="min-w-44" :format-option="formatWarehouse" :load="loadWarehouses" placeholder="选择仓库" />
                </td>
                <td class="px-3 py-2">
                  <InputNumber
                    v-if="kind === 'check'"
                    v-model:value="line.actual_quantity"
                    :min="0"
                    :precision="6"
                    class="w-full"
                  />
                  <InputNumber
                    v-else
                    v-model:value="line.quantity"
                    :min="0.000001"
                    :precision="6"
                    class="w-full"
                  />
                </td>
                <td class="px-3 py-2">
                  <InputNumber v-model:value="line.reference_price" :min="0" :precision="4" class="w-full" />
                </td>
                <td class="px-3 py-2">
                  <Input v-model:value="line.remark" :maxlength="500" placeholder="行备注" />
                </td>
                <td class="px-3 py-2 text-right">
                  <Button :disabled="lines.length === 1" danger size="small" type="link" @click="removeLine(index)">
                    删除
                  </Button>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
        <Button type="dashed" @click="addLine">新增明细行</Button>
        <Form.Item class="mt-5" label="备注" name="remark">
          <Input.TextArea v-model:value="documentForm.remark" :maxlength="500" :rows="3" show-count />
        </Form.Item>
      </Form>
      <template #footer>
        <div class="flex justify-end gap-2">
          <Button @click="drawerOpen = false">取消</Button>
          <Button :loading="saving" type="primary" @click="submit">{{ editingDocument ? '保存修改' : '保存草稿' }}</Button>
        </div>
      </template>
    </Drawer>

    <div class="mb-3 flex flex-wrap items-center justify-between gap-3 border-b border-[var(--vben-border-color)] pb-3">
      <div>
        <div class="text-base font-semibold">{{ isDedicatedPage ? kindLabels[kind] : '库存单据' }}</div>
        <div class="mt-1 text-sm text-[var(--vben-text-color-2)]">制单后审核记账；反审核会生成冲销流水</div>
      </div>
      <Segmented
        v-if="!isDedicatedPage"
        :options="[
          { label: '其他入库', value: 'in' },
          { label: '其他出库', value: 'out' },
          { label: '库存调拨', value: 'move' },
          { label: '库存盘点', value: 'check' },
        ]"
        :value="kind"
        @change="changeKind($event as DocumentKind)"
      />
    </div>
    <DocumentListFilters
      v-model="listQuery"
      :products="products"
      :product-loader="loadProducts"
      :warehouses="warehouses"
      :warehouse-loader="loadWarehouses"
      @query="gridApi.query()"
    />
    <Grid :table-title="kindLabels[kind]">
      <template #toolbar-tools>
        <div class="flex items-center gap-1">
          <Button v-access:code="`${permissionPrefix[kind]}:create`" class="gap-1" type="primary" @click="openCreate">
            <Plus class="size-5" />
            <span>新增{{ kindLabels[kind] }}</span>
          </Button>
          <ExportCsvButton :file-name="`${kindLabels[kind]}列表.csv`" :permission="`${permissionPrefix[kind]}:export`" :query="exportQuery" :resource="kind === 'in' ? 'stock-in' : kind === 'out' ? 'stock-out' : kind === 'move' ? 'stock-move' : 'stock-check'" />
        </div>
      </template>
      <template #status="{ row }">
        <Tag :color="row.status === 'approved' ? 'success' : 'default'">
          {{ row.status === 'approved' ? '已审批' : '草稿' }}
        </Tag>
      </template>
      <template #operation="{ row }">
        <DocumentTableActions
          approve-impact="审批将立即记账并更新库存余额，确认继续吗？"
          :approve-permission="`${permissionPrefix[kind]}:approve`"
          :delete-permission="`${permissionPrefix[kind]}:delete`"
          :document-id="row.id"
          :document-no="row.no"
          :document-type="`stock_${kind}`"
          :reverse-permission="`${permissionPrefix[kind]}:reverse`"
          :status="row.status"
          :update-permission="`${permissionPrefix[kind]}:update`"
          @approve="approve(row)"
          @delete="remove(row)"
          @edit="openEdit(row)"
          @reverse="openReverse(row)"
        />
      </template>
    </Grid>
  </Page>
</template>
