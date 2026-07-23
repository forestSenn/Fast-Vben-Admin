<script lang="ts" setup>
import type { PurchaseOrderRecord } from '#/modules/erp/api/erp';

import { computed, ref } from 'vue';

import { Search } from '@vben/icons';
import { Button, Input, InputSearch, message, Modal, Table } from 'ant-design-vue';
import BigNumber from 'bignumber.js';

import { listPurchaseOrdersApi } from '#/modules/erp/api/erp';
import {
  compareDecimal,
  normalizeDecimal,
  QUANTITY_DECIMAL_PLACES,
  subtractDecimal,
} from '#/modules/erp/utils/decimal';

const props = withDefaults(
  defineProps<{
    disabled?: boolean;
    value?: PurchaseOrderRecord;
  }>(),
  { disabled: false, value: undefined },
);

const emit = defineEmits<{
  select: [order: PurchaseOrderRecord];
}>();

const open = ref(false);
const loading = ref(false);
const keyword = ref('');
const orders = ref<PurchaseOrderRecord[]>([]);
const pendingOrder = ref<PurchaseOrderRecord>();

const columns = [
  { dataIndex: 'no', minWidth: 180, title: '采购订单号' },
  { dataIndex: 'supplier_name', minWidth: 160, title: '供应商' },
  { dataIndex: 'business_at', title: '采购日期', width: 130 },
  { dataIndex: 'total_quantity', title: '订单数量', width: 110 },
  { key: 'remaining_quantity', title: '剩余可入库', width: 120 },
  { dataIndex: 'total_amount', title: '订单金额', width: 120 },
];

const rowSelection = computed(() => ({
  onChange: (
    _selectedRowKeys: Array<number | string>,
    selectedRows: PurchaseOrderRecord[],
  ) => {
    pendingOrder.value = selectedRows[0];
  },
  selectedRowKeys: pendingOrder.value ? [pendingOrder.value.id] : [],
  type: 'radio' as const,
}));

function remainingQuantity(
  item: NonNullable<PurchaseOrderRecord['items']>[number],
) {
  return subtractDecimal(
    item.quantity,
    item.received_quantity,
    QUANTITY_DECIMAL_PLACES,
  );
}

function remainingOrderQuantity(order: PurchaseOrderRecord) {
  return normalizeDecimal(
    (order.items ?? []).reduce(
      (total, item) => total.plus(remainingQuantity(item)),
      new BigNumber(0),
    ),
    QUANTITY_DECIMAL_PLACES,
  );
}

function formatQuantity(value: null | number | string | undefined) {
  return normalizeDecimal(value, QUANTITY_DECIMAL_PLACES);
}

function formatAmount(value: null | number | string | undefined) {
  return new BigNumber(value ?? 0).toFixed(2);
}

function formatDate(value: string) {
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? value : date.toLocaleDateString('zh-CN');
}

function selectRow(order: PurchaseOrderRecord) {
  pendingOrder.value = order;
}

function customRow(order: PurchaseOrderRecord) {
  return {
    onClick: () => selectRow(order),
  };
}

async function loadOrders() {
  loading.value = true;
  try {
    const result = await listPurchaseOrdersApi({
      keyword: keyword.value.trim() || undefined,
      page: 1,
      page_size: 100,
      status: 'approved',
    });
    orders.value = result.items.filter((order) =>
      (order.items ?? []).some(
        (item) => compareDecimal(remainingQuantity(item), 0) > 0,
      ),
    );
  } catch {
    orders.value = [];
  } finally {
    loading.value = false;
  }
}

function show() {
  if (props.disabled) return;
  pendingOrder.value = props.value;
  keyword.value = '';
  open.value = true;
  void loadOrders();
}

function confirm() {
  if (!pendingOrder.value) {
    message.warning('请选择一张采购订单');
    return;
  }
  emit('select', pendingOrder.value);
  open.value = false;
}
</script>

<template>
  <div class="flex w-full">
    <Input
      class="min-w-0 flex-1"
      :disabled="disabled"
      placeholder="请选择已审核且有剩余数量的采购订单"
      readonly
      :value="value ? `${value.no} - ${value.supplier_name}` : undefined"
      @click="show"
    />
    <Button :disabled="disabled" @click="show">
      <Search class="size-4" />
      <span>选择订单</span>
    </Button>
  </div>

  <Modal
    v-model:open="open"
    cancel-text="取消"
    destroy-on-close
    ok-text="确认选择"
    title="选择来源采购订单"
    width="min(960px, calc(100vw - 32px))"
    @ok="confirm"
  >
    <InputSearch
      v-model:value="keyword"
      allow-clear
      class="mb-3"
      enter-button="查询"
      placeholder="搜索采购订单号或供应商"
      @search="loadOrders"
    />
    <Table
      :columns="columns"
      :custom-row="customRow"
      :data-source="orders"
      :loading="loading"
      :pagination="{ pageSize: 8, showSizeChanger: false }"
      :row-selection="rowSelection"
      row-key="id"
      :scroll="{ x: 820, y: 420 }"
      size="small"
    >
      <template #bodyCell="{ column, record }">
        <template v-if="column.dataIndex === 'business_at'">
          {{ formatDate(record.business_at) }}
        </template>
        <template v-else-if="column.dataIndex === 'total_quantity'">
          {{ formatQuantity(record.total_quantity) }}
        </template>
        <template v-else-if="column.key === 'remaining_quantity'">
          {{ remainingOrderQuantity(record) }}
        </template>
        <template v-else-if="column.dataIndex === 'total_amount'">
          {{ formatAmount(record.total_amount) }}
        </template>
        <template v-else>
          {{ record[column.dataIndex] }}
        </template>
      </template>
    </Table>
  </Modal>
</template>
