<script lang="ts" setup>
import type { VxeTableGridOptions } from '#/adapter/vxe-table';
import type {
  CounterpartyRecord,
  DocumentQuery,
  FinancePaymentRecord,
  FinanceReceiptRecord,
  SettlementAccountRecord,
} from '#/modules/erp/api/erp';

import { computed, onBeforeUnmount, onMounted, ref } from 'vue';

import { Page } from '@vben/common-ui';
import { Plus } from '@vben/icons';
import { Button, Checkbox, Drawer, Input, InputNumber, Tag } from 'ant-design-vue';

import { useVbenVxeGrid } from '#/adapter/vxe-table';
import DocumentListFilters from '#/modules/erp/components/document-list-filters.vue';
import DocumentTableActions from '#/modules/erp/components/document-table-actions.vue';
import ErpRemoteSelect from '#/modules/erp/components/erp-remote-select.vue';
import ExportCsvButton from '#/modules/erp/components/export-csv-button.vue';
import ReverseDocumentDialog from '#/modules/erp/components/reverse-document-dialog.vue';
import {
  approveFinancePaymentApi,
  approveFinanceReceiptApi,
  createFinancePaymentApi,
  createFinanceReceiptApi,
  deleteFinancePaymentApi,
  deleteFinanceReceiptApi,
  listCounterpartiesApi,
  listFinancePaymentsApi,
  listFinanceReceiptsApi,
  listPurchaseInsApi,
  listPurchaseReturnsApi,
  listSaleOutsApi,
  listSaleReturnsApi,
  listSettlementAccountsApi,
  reverseFinancePaymentApi,
  reverseFinanceReceiptApi,
  updateFinancePaymentApi,
  updateFinanceReceiptApi,
} from '#/modules/erp/api/erp';
import {
  compareDecimal,
  formatDecimal,
  normalizeDecimal,
  subtractDecimal,
} from '#/modules/erp/utils/decimal';

const props = defineProps<{ flow: 'payment' | 'receipt' }>();

type RecordType = FinancePaymentRecord | FinanceReceiptRecord;
type SourceType = 'purchase_in' | 'purchase_return' | 'sale_out' | 'sale_return';

interface SourceOption {
  counterpartyId: string;
  id: string;
  label: string;
  remaining: string;
  type: SourceType;
}

interface SettlementLine {
  amount: string;
  key: string;
}

const drawerOpen = ref(false);
const saving = ref(false);
const reverseOpen = ref(false);
const reverseTarget = ref<RecordType>();
const editingDocument = ref<RecordType>();
const counterpartyId = ref<string>();
const accountId = ref<string>();
const discountAmount = ref('0');
const sourceKeyword = ref('');
const sourceKeys = ref<string[]>([]);
const lines = ref<SettlementLine[]>([]);
const counterparties = ref<CounterpartyRecord[]>([]);
const accounts = ref<SettlementAccountRecord[]>([]);
const sources = ref<SourceOption[]>([]);
const selectedSourceIndex = ref<Record<string, SourceOption>>({});
let sourceSearchRequest = 0;
let sourceSearchTimer: number | undefined;
const listQuery = ref<DocumentQuery>({});
const exportQuery = computed(() =>
  Object.fromEntries(
    Object.entries(listQuery.value).filter(
      (entry): entry is [string, string] =>
        typeof entry[1] === 'string' && Boolean(entry[1]),
    ),
  ),
);

const isPayment = computed(() => props.flow === 'payment');
const title = computed(() => (isPayment.value ? '付款单' : '收款单'));
const counterpartyLabel = computed(() => (isPayment.value ? '供应商' : '客户'));
const permissionPrefix = computed(() => (isPayment.value ? 'erp:finance-payment' : 'erp:finance-receipt'));

const [Grid, gridApi] = useVbenVxeGrid({
  gridOptions: {
    columns: [
      { field: 'no', minWidth: 190, title: '单据编号' },
      { field: 'counterparty', minWidth: 180, slots: { default: 'counterparty' }, title: '往来单位' },
      { field: 'total_settlement_amount', title: '核销金额', width: 120 },
      { field: 'discount_amount', title: '优惠', width: 110 },
      { field: 'cash_amount', slots: { default: 'cashAmount' }, title: '现金金额', width: 120 },
      { field: 'status', slots: { default: 'status' }, title: '状态', width: 90 },
      { align: 'center', field: 'operation', fixed: 'right', slots: { default: 'operation' }, title: '操作', width: 320 },
    ],
    height: 'auto',
    proxyConfig: {
      ajax: {
        query: async ({ page }) =>
          (isPayment.value
            ? await listFinancePaymentsApi({ ...listQuery.value, page: page.currentPage, page_size: page.pageSize })
            : await listFinanceReceiptsApi({ ...listQuery.value, page: page.currentPage, page_size: page.pageSize })) as any,
      },
    },
    rowConfig: { keyField: 'id' },
    toolbarConfig: { custom: true, refresh: true, zoom: true },
  } as VxeTableGridOptions<RecordType>,
});

async function loadFilterReferences() {
  const result = await listCounterpartiesApi(
    isPayment.value ? 'supplier' : 'customer',
    { page: 1, page_size: 50 },
  );
  counterparties.value = result.items.filter((item) => item.is_active);
}

onMounted(() => void loadFilterReferences());

function sourceKey(source: Pick<SourceOption, 'id' | 'type'>) {
  return `${source.type}|${source.id}`;
}

function formatAccount(account: SettlementAccountRecord) {
  return { label: `${account.name} (${account.account_no_masked})`, value: account.id };
}

function formatCounterparty(counterparty: CounterpartyRecord) {
  return { label: counterparty.name, value: counterparty.id };
}

async function loadCounterparties(keyword: string) {
  const result = await listCounterpartiesApi(
    isPayment.value ? 'supplier' : 'customer',
    { keyword, page: 1, page_size: 50 },
  );
  counterparties.value = result.items.filter((item) => item.is_active);
  return counterparties.value;
}

async function loadAccounts(keyword: string) {
  const result = await listSettlementAccountsApi({ keyword, page: 1, page_size: 50 });
  accounts.value = result.items.filter((account) => account.is_active);
  return accounts.value;
}

function updateSources(value: unknown) {
  const keys = Array.isArray(value)
    ? value.filter((item): item is string => typeof item === 'string')
    : [];
  sourceKeys.value = keys;
  lines.value = keys.map((key) => {
    const existing = lines.value.find((line) => line.key === key);
    const source = selectedSourceIndex.value[key] ?? sources.value.find((entry) => sourceKey(entry) === key);
    return { amount: existing?.amount ?? source?.remaining ?? '0', key };
  });
}

function counterpartyName(record: RecordType) {
  return isPayment.value
    ? (record as FinancePaymentRecord).supplier_name
    : (record as FinanceReceiptRecord).customer_name;
}

function cashAmount(record: RecordType) {
  return isPayment.value
    ? (record as FinancePaymentRecord).payment_amount
    : (record as FinanceReceiptRecord).receipt_amount;
}

function sourceForLine(line: SettlementLine) {
  return selectedSourceIndex.value[line.key] ?? sources.value.find((source) => sourceKey(source) === line.key);
}

async function loadSources(keyword: string) {
  if (!counterpartyId.value) return [];
  const request = ++sourceSearchRequest;
  const filters = {
    [isPayment.value ? 'supplier_id' : 'customer_id']: counterpartyId.value,
    keyword,
    page: 1,
    page_size: 50,
  };
  const [first, second] = await Promise.all([
    isPayment.value ? listPurchaseInsApi(filters) : listSaleOutsApi(filters),
    isPayment.value ? listPurchaseReturnsApi(filters) : listSaleReturnsApi(filters),
  ]);
  const positiveType: SourceType = isPayment.value ? 'purchase_in' : 'sale_out';
  const creditType: SourceType = isPayment.value ? 'purchase_return' : 'sale_return';
  const firstItems = first.items as any[];
  const secondItems = second.items as any[];
  const nextSources = [
    ...firstItems.filter((item) => item.status === 'approved' && compareDecimal(item.total_amount, item.settled_amount) > 0).map((item) => ({
      counterpartyId: isPayment.value ? item.supplier_id : item.customer_id,
      id: item.id,
      label: `${item.no} | ${formatDecimal(subtractDecimal(item.total_amount, item.settled_amount))}`,
      remaining: subtractDecimal(item.total_amount, item.settled_amount),
      type: positiveType,
    })),
    ...secondItems.filter((item) => item.status === 'approved' && compareDecimal(item.total_amount, item.settled_amount) > 0).map((item) => ({
      counterpartyId: isPayment.value ? item.supplier_id : item.customer_id,
      id: item.id,
      label: `${item.no} | 退货信用 ${formatDecimal(subtractDecimal(item.total_amount, item.settled_amount))}`,
      remaining: subtractDecimal(item.total_amount, item.settled_amount),
      type: creditType,
    })),
  ];
  if (request !== sourceSearchRequest) return sources.value;
  sources.value = nextSources;
  for (const source of nextSources) {
    selectedSourceIndex.value[sourceKey(source)] = source;
  }
  return sources.value;
}

function searchSources(value: string) {
  sourceKeyword.value = value;
  if (sourceSearchTimer) window.clearTimeout(sourceSearchTimer);
  sourceSearchTimer = window.setTimeout(() => void loadSources(value), 250);
}

onBeforeUnmount(() => {
  if (sourceSearchTimer) window.clearTimeout(sourceSearchTimer);
});

async function openCreate() {
  counterpartyId.value = undefined;
  accountId.value = undefined;
  discountAmount.value = '0';
  sourceKeyword.value = '';
  sourceKeys.value = [];
  lines.value = [];
  selectedSourceIndex.value = {};
  editingDocument.value = undefined;
  drawerOpen.value = true;
}

async function openEdit(record: RecordType) {
  await openCreate();
  editingDocument.value = record;
  counterpartyId.value = isPayment.value
    ? (record as FinancePaymentRecord).supplier_id
    : (record as FinanceReceiptRecord).customer_id;
  accountId.value = record.settlement_account_id;
  discountAmount.value = normalizeDecimal(record.discount_amount);
  sourceKeys.value = (record.items || []).map((item) => sourceKey({ id: item.source_document_id, type: item.source_type as SourceType }));
  lines.value = (record.items || []).map((item) => ({ amount: normalizeDecimal(item.settlement_signed), key: sourceKey({ id: item.source_document_id, type: item.source_type as SourceType }) }));
}

async function submit() {
  if (!counterpartyId.value || !accountId.value || lines.value.length === 0 || lines.value.some((line) => !sourceForLine(line) || compareDecimal(line.amount, 0) <= 0)) return;
  saving.value = true;
  try {
    const items = lines.value.map((line) => {
      const source = sourceForLine(line)!;
      return { settlement_amount: normalizeDecimal(line.amount), source_document_id: source.id, source_type: source.type };
    });
    if (isPayment.value) {
      const payload = {
        discount_amount: normalizeDecimal(discountAmount.value),
        items,
        settlement_account_id: accountId.value,
        supplier_id: counterpartyId.value,
      };
      if (editingDocument.value) await updateFinancePaymentApi(editingDocument.value.id, payload, editingDocument.value.version);
      else await createFinancePaymentApi(payload, crypto.randomUUID());
    } else {
      const payload = {
        customer_id: counterpartyId.value,
        discount_amount: normalizeDecimal(discountAmount.value),
        items,
        settlement_account_id: accountId.value,
      };
      if (editingDocument.value) await updateFinanceReceiptApi(editingDocument.value.id, payload, editingDocument.value.version);
      else await createFinanceReceiptApi(payload, crypto.randomUUID());
    }
    drawerOpen.value = false;
    gridApi.query();
  } finally { saving.value = false; }
}

async function approve(record: RecordType) {
  if (isPayment.value) await approveFinancePaymentApi(record.id, record.version, crypto.randomUUID());
  else await approveFinanceReceiptApi(record.id, record.version, crypto.randomUUID());
  gridApi.query();
}

function openReverse(record: RecordType) {
  reverseTarget.value = record;
  reverseOpen.value = true;
}

async function confirmReverse(reason: string) {
  const record = reverseTarget.value;
  if (!record) return;
  if (isPayment.value) await reverseFinancePaymentApi(record.id, record.version, reason.trim(), crypto.randomUUID());
  else await reverseFinanceReceiptApi(record.id, record.version, reason.trim(), crypto.randomUUID());
  gridApi.query();
}

async function remove(record: RecordType) {
  if (isPayment.value) await deleteFinancePaymentApi(record.id);
  else await deleteFinanceReceiptApi(record.id);
  gridApi.query();
}
</script>

<template>
  <Page auto-content-height>
    <ReverseDocumentDialog v-model:open="reverseOpen" impact="反审核会释放已占用的来源单据余额，并将该单据恢复为草稿。" :on-confirm="confirmReverse" :title="`反审核${title}`" />
    <Drawer v-model:open="drawerOpen" :confirm-loading="saving" :title="`${editingDocument ? '编辑' : '新增'}${title}`" class="w-[min(980px,calc(100vw-24px))]" placement="right">
      <div class="grid gap-4 md:grid-cols-3">
        <div>
          <div class="mb-1 text-sm font-medium">{{ counterpartyLabel }}</div>
          <ErpRemoteSelect
            v-model:value="counterpartyId"
            class="w-full"
            :format-option="formatCounterparty"
            :load="loadCounterparties"
            @change="() => { sourceKeyword = ''; updateSources([]); sources = []; selectedSourceIndex = {}; }"
          />
        </div>
        <div>
          <div class="mb-1 text-sm font-medium">结算账户</div>
          <ErpRemoteSelect v-model:value="accountId" class="w-full" :format-option="formatAccount" :load="loadAccounts" />
        </div>
        <div>
          <div class="mb-1 text-sm font-medium">优惠金额</div>
          <InputNumber v-model:value="discountAmount" :min="'0'" :precision="4" class="w-full" string-mode />
        </div>
      </div>
      <div class="mt-4">
        <div class="mb-1 text-sm font-medium">核销来源</div>
        <Input
          :disabled="!counterpartyId"
          placeholder="按来源单号检索"
          :value="sourceKeyword"
          @update:value="searchSources"
        />
        <div v-if="sources.length" class="mt-2 max-h-44 overflow-y-auto rounded border border-[var(--vben-border-color)]">
          <Checkbox
            v-for="source in sources"
            :key="sourceKey(source)"
            :checked="sourceKeys.includes(sourceKey(source))"
            class="flex w-full px-3 py-2 hover:bg-[var(--vben-bg-color-overlay)]"
            @update:checked="(checked) => updateSources(checked ? [...sourceKeys, sourceKey(source)] : sourceKeys.filter((key) => key !== sourceKey(source)))"
          >
            {{ source.label }}
          </Checkbox>
        </div>
      </div>
      <div class="mt-4 overflow-x-auto rounded border border-[var(--vben-border-color)]"><table class="min-w-[680px] w-full text-left text-sm"><thead><tr><th class="p-2">来源单据</th><th class="p-2">类型</th><th class="p-2">剩余金额</th><th class="p-2">本次金额</th></tr></thead><tbody><tr v-for="line in lines" :key="line.key" class="border-t border-[var(--vben-border-color)]"><td class="p-2">{{ sourceForLine(line)?.label }}</td><td class="p-2">{{ sourceForLine(line)?.type.includes('return') ? '退货信用' : '正向单据' }}</td><td class="p-2">{{ sourceForLine(line)?.remaining }}</td><td class="p-2"><InputNumber v-model:value="line.amount" :max="sourceForLine(line)?.remaining" :min="'0.0001'" :precision="4" string-mode /></td></tr></tbody></table></div>
      <template #footer><div class="flex justify-end gap-2"><Button @click="drawerOpen = false">取消</Button><Button :loading="saving" type="primary" @click="submit">{{ editingDocument ? '保存修改' : '保存草稿' }}</Button></div></template>
    </Drawer>
    <DocumentListFilters v-model="listQuery" :counterparties="counterparties" :counterparty-loader="loadCounterparties" :counterparty-key="isPayment ? 'supplier_id' : 'customer_id'" :counterparty-label="counterpartyLabel" @query="gridApi.query()" />
    <Grid :table-title="`${title}列表`">
      <template #toolbar-tools><div class="flex items-center gap-1"><Button v-access:code="`${permissionPrefix}:create`" class="gap-1" type="primary" @click="openCreate"><Plus class="size-5" /><span>新增{{ title }}</span></Button><ExportCsvButton :file-name="`${title}列表.csv`" :permission="`${permissionPrefix}:export`" :query="exportQuery" :resource="isPayment ? 'finance-payment' : 'finance-receipt'" /></div></template>
      <template #counterparty="{ row }">{{ counterpartyName(row) }}</template>
      <template #cashAmount="{ row }">{{ cashAmount(row) }}</template>
      <template #status="{ row }"><Tag :color="row.status === 'approved' ? 'success' : 'default'">{{ row.status === 'approved' ? '已审批' : '草稿' }}</Tag></template>
      <template #operation="{ row }"><DocumentTableActions approve-impact="审批后将占用来源单据余额，确认继续吗？" :approve-permission="`${permissionPrefix}:approve`" :delete-permission="`${permissionPrefix}:delete`" :document-id="row.id" :document-no="row.no" :document-type="isPayment ? 'finance_payment' : 'finance_receipt'" :reverse-permission="`${permissionPrefix}:reverse`" :status="row.status" :update-permission="`${permissionPrefix}:update`" @approve="approve(row)" @delete="remove(row)" @edit="openEdit(row)" @reverse="openReverse(row)" /></template>
    </Grid>
  </Page>
</template>
