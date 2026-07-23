<script lang="ts" setup>
import type { UserRecord } from '#/api';
import type { VbenFormSchema } from '#/adapter/form';
import type {
  CounterpartyRecord,
  DocumentQuery,
  ProductRecord,
  WarehouseRecord,
} from '#/modules/erp/api/erp';

import { onMounted, watch } from 'vue';

import { useVbenForm } from '#/adapter/form';
import { listUsersApi } from '#/api';

const props = withDefaults(
  defineProps<{
    counterparties?: CounterpartyRecord[];
    counterpartyLoader?: (keyword: string) => Promise<CounterpartyRecord[]>;
    counterpartyKey?: 'customer_id' | 'supplier_id';
    counterpartyLabel?: string;
    modelValue: DocumentQuery;
    products?: ProductRecord[];
    productLoader?: (keyword: string) => Promise<ProductRecord[]>;
    showFulfillmentStatus?: boolean;
    warehouses?: WarehouseRecord[];
    warehouseLoader?: (keyword: string) => Promise<WarehouseRecord[]>;
  }>(),
  { counterparties: () => [], products: () => [], warehouses: () => [] },
);

const emit = defineEmits<{
  query: [];
  'update:modelValue': [value: DocumentQuery];
}>();

async function getCounterpartyOptions() {
  return props.counterpartyLoader
    ? await props.counterpartyLoader('')
    : props.counterparties;
}

async function getOwnerOptions(): Promise<UserRecord[]> {
  try {
    const result = await listUsersApi({
      is_active: true,
      page: 1,
      page_size: 200,
    });
    return result.items;
  } catch {
    // Some document roles may not have access to the user directory.
    return [];
  }
}

async function getProductOptions() {
  return props.productLoader ? await props.productLoader('') : props.products;
}

async function getWarehouseOptions() {
  return props.warehouseLoader
    ? await props.warehouseLoader('')
    : props.warehouses;
}

function normalizeDate(value: unknown) {
  if (!value) return undefined;
  const date = new Date(String(value));
  return Number.isNaN(date.getTime()) ? String(value) : date.toISOString();
}

function buildSchema(): VbenFormSchema[] {
  const schema: VbenFormSchema[] = [
    {
      component: 'Input',
      componentProps: {
        allowClear: true,
        placeholder: '请输入单据编号',
      },
      fieldName: 'keyword',
      label: '单据编号',
    },
  ];

  if (props.productLoader || props.products.length > 0) {
    schema.push({
      component: 'ApiSelect',
      componentProps: {
        allowClear: true,
        api: getProductOptions,
        class: 'w-full',
        labelFn: (item: ProductRecord) => `${item.code} - ${item.name}`,
        placeholder: '请选择产品名称',
        showSearch: true,
        valueField: 'id',
      },
      fieldName: 'product_id',
      label: '产品名称',
    });
  }

  schema.push({
    component: 'RangePicker',
    componentProps: {
      allowClear: true,
      class: 'w-full',
      format: 'YYYY-MM-DD HH:mm:ss',
      placeholder: ['开始时间', '结束时间'],
      showTime: true,
      valueFormat: 'YYYY-MM-DDTHH:mm:ss',
    },
    fieldName: 'business_range',
    label: '业务时间',
  });

  if (props.counterpartyKey) {
    schema.push({
      component: 'ApiSelect',
      componentProps: {
        allowClear: true,
        api: getCounterpartyOptions,
        class: 'w-full',
        labelField: 'name',
        placeholder: `请选择${props.counterpartyLabel || '往来单位'}`,
        showSearch: true,
        valueField: 'id',
      },
      fieldName: props.counterpartyKey,
      label: props.counterpartyLabel || '往来单位',
    });
  }

  schema.push(
    {
      component: 'ApiSelect',
      componentProps: {
        allowClear: true,
        api: getOwnerOptions,
        class: 'w-full',
        labelFn: (item: UserRecord) => item.full_name || item.email,
        placeholder: '请选择制单人',
        showSearch: true,
        valueField: 'id',
      },
      fieldName: 'owner_id',
      label: '制单人',
    },
    {
      component: 'Select',
      componentProps: {
        allowClear: true,
        options: [
          { label: '草稿', value: 'draft' },
          { label: '已审核', value: 'approved' },
        ],
        placeholder: '请选择审批状态',
      },
      fieldName: 'status',
      label: '审批状态',
    },
    {
      component: 'Input',
      componentProps: { allowClear: true, placeholder: '请输入备注' },
      fieldName: 'remark',
      label: '备注',
    },
  );

  if (props.warehouseLoader || props.warehouses.length > 0) {
    schema.push({
      component: 'ApiSelect',
      componentProps: {
        allowClear: true,
        api: getWarehouseOptions,
        class: 'w-full',
        labelFn: (item: WarehouseRecord) => `${item.code} - ${item.name}`,
        placeholder: '请选择仓库',
        showSearch: true,
        valueField: 'id',
      },
      fieldName: 'warehouse_id',
      label: '仓库',
    });
  }

  if (props.showFulfillmentStatus) {
    schema.push(
      {
        component: 'Select',
        componentProps: {
          allowClear: true,
          options: [
            { label: '未入库', value: 'none' },
            { label: '部分入库', value: 'partial' },
            { label: '全部入库', value: 'completed' },
          ],
          placeholder: '请选择入库状态',
        },
        fieldName: 'receipt_status',
        label: '入库状态',
      },
      {
        component: 'Select',
        componentProps: {
          allowClear: true,
          options: [
            { label: '未退货', value: 'none' },
            { label: '部分退货', value: 'partial' },
            { label: '全部退货', value: 'completed' },
          ],
          placeholder: '请选择退货状态',
        },
        fieldName: 'return_status',
        label: '退货状态',
      },
    );
  }

  return schema;
}

function toFormValues(query: DocumentQuery) {
  const { business_from: businessFrom, business_to: businessTo, ...values } =
    query;
  return {
    ...values,
    business_range:
      businessFrom && businessTo ? [businessFrom, businessTo] : undefined,
  };
}

function toQuery(values: Record<string, unknown>): DocumentQuery {
  const { business_range: businessRange, ...query } = values;
  const range = Array.isArray(businessRange) ? businessRange : [];
  return {
    ...(query as DocumentQuery),
    business_from: normalizeDate(range[0]),
    business_to: normalizeDate(range[1]),
  };
}

async function handleReset() {
  await formApi.resetForm();
  emit('update:modelValue', {});
  emit('query');
}

function handleSubmit(values: Record<string, unknown>) {
  emit('update:modelValue', toQuery(values));
  emit('query');
}

const [Form, formApi] = useVbenForm({
  collapsed: true,
  compact: true,
  commonConfig: {
    componentProps: {
      class: 'w-full',
    },
  },
  handleReset,
  handleSubmit,
  schema: buildSchema(),
  showCollapseButton: true,
  submitButtonOptions: {
    content: '搜索',
  },
  wrapperClass: 'grid-cols-1 md:grid-cols-2 lg:grid-cols-3',
});

onMounted(() => {
  void formApi.setValues(toFormValues(props.modelValue));
});

watch(
  () => props.modelValue,
  (value) => {
    void formApi.setValues(toFormValues(value));
  },
  { deep: true },
);
</script>

<template>
  <div class="mb-3 rounded-sm bg-card px-2 pt-3">
    <Form />
  </div>
</template>
