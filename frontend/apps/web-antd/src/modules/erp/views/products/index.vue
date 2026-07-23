<script lang="ts" setup>
import type { VxeTableGridOptions } from '#/adapter/vxe-table';
import type { FormInstance } from 'ant-design-vue';
import type {
  ProductCategoryRecord,
  ProductRecord,
  ProductUnitRecord,
} from '#/modules/erp/api/erp';

import { reactive, ref } from 'vue';

import { Page } from '@vben/common-ui';
import { Plus } from '@vben/icons';

import {
  Button,
  Drawer,
  Form,
  Input,
  InputNumber,
  Switch,
  Tag,
} from 'ant-design-vue';

import { useVbenVxeGrid, VbenTableAction } from '#/adapter/vxe-table';
import ExportCsvButton from '#/modules/erp/components/export-csv-button.vue';
import ErpRemoteSelect from '#/modules/erp/components/erp-remote-select.vue';
import {
  createProductApi,
  deleteProductApi,
  listProductCategoriesApi,
  listProductsApi,
  listProductUnitsApi,
  updateProductApi,
} from '#/modules/erp/api/erp';
import { buildKeyword } from '#/views/system/shared/utils';

interface ProductFormValues {
  barcode?: string;
  category_id?: string;
  code: string;
  expiry_days: number;
  is_active: boolean;
  min_sale_price: number;
  name: string;
  purchase_reference_price: number;
  remark?: string;
  sale_reference_price: number;
  specification?: string;
  unit_id?: string;
  weight: number;
}

const formRef = ref<FormInstance>();
const drawerOpen = ref(false);
const saving = ref(false);
const editingId = ref<string>();
const exportQuery = ref<Record<string, string>>({});
const units = ref<ProductUnitRecord[]>([]);
const categories = ref<ProductCategoryRecord[]>([]);
const productForm = reactive<ProductFormValues>({
  barcode: undefined,
  category_id: undefined,
  code: '',
  expiry_days: 0,
  is_active: true,
  min_sale_price: 0,
  name: '',
  purchase_reference_price: 0,
  remark: undefined,
  sale_reference_price: 0,
  specification: undefined,
  unit_id: undefined,
  weight: 0,
});

const [Grid, gridApi] = useVbenVxeGrid({
  formOptions: {
    schema: [
      {
        component: 'Input',
        componentProps: { placeholder: '按编码、名称或条码检索' },
        fieldName: 'keyword',
        label: '检索',
      },
    ],
    submitOnChange: true,
  },
  gridOptions: {
    columns: [
      { field: 'code', minWidth: 150, title: '商品编码' },
      { field: 'name', minWidth: 220, showOverflow: true, title: '商品名称' },
      { field: 'barcode', minWidth: 160, title: '条码' },
      { field: 'specification', minWidth: 180, title: '规格' },
      { field: 'purchase_reference_price', title: '采购参考价', width: 120 },
      { field: 'sale_reference_price', title: '销售参考价', width: 120 },
      { field: 'category_id', minWidth: 210, title: '分类 ID' },
      { field: 'unit_id', minWidth: 210, title: '单位 ID' },
      {
        field: 'is_active',
        slots: { default: 'status' },
        title: '状态',
        width: 96,
      },
      { field: 'updated_at', title: '最近更新', width: 180 },
      {
        align: 'center',
        field: 'operation',
        fixed: 'right',
        slots: { default: 'operation' },
        title: '操作',
        width: 180,
      },
    ],
    height: 'auto',
    keepSource: true,
    proxyConfig: {
      ajax: {
        query: async ({ page }, values) => {
          const keyword = buildKeyword(values.keyword);
          exportQuery.value = keyword ? { keyword } : {};
          return await listProductsApi({
            keyword: keyword || undefined,
            page: page.currentPage,
            page_size: page.pageSize,
          });
        },
      },
    },
    rowConfig: { keyField: 'id' },
    toolbarConfig: { custom: true, refresh: true, search: true, zoom: true },
  } as VxeTableGridOptions<ProductRecord>,
});

function formatUnit(unit: ProductUnitRecord) { return { label: `${unit.name} (${unit.code})`, value: unit.id }; }
function formatCategory(category: ProductCategoryRecord) { return { label: `${category.name} (${category.code})`, value: category.id }; }
async function loadUnits(keyword: string) {
  const result = await listProductUnitsApi({ keyword, page: 1, page_size: 50 });
  units.value = result.items.filter((unit) => unit.is_active);
  return units.value;
}
async function loadCategories(keyword: string) {
  const result = await listProductCategoriesApi({ keyword, page: 1, page_size: 50 });
  categories.value = result.items.filter((category) => category.is_active);
  return categories.value;
}

function resetForm() {
  Object.assign(productForm, {
    barcode: undefined,
    category_id: undefined,
    code: '',
    expiry_days: 0,
    is_active: true,
    min_sale_price: 0,
    name: '',
    purchase_reference_price: 0,
    remark: undefined,
    sale_reference_price: 0,
    specification: undefined,
    unit_id: undefined,
    weight: 0,
  });
  formRef.value?.clearValidate();
}

async function openCreate() {
  editingId.value = undefined;
  resetForm();
  drawerOpen.value = true;
}

async function openEdit(row: ProductRecord) {
  editingId.value = row.id;
  Object.assign(productForm, {
    barcode: row.barcode || undefined,
    category_id: row.category_id || undefined,
    code: row.code,
    expiry_days: row.expiry_days,
    is_active: row.is_active,
    min_sale_price: Number(row.min_sale_price),
    name: row.name,
    purchase_reference_price: Number(row.purchase_reference_price),
    remark: row.remark || undefined,
    sale_reference_price: Number(row.sale_reference_price),
    specification: row.specification || undefined,
    unit_id: row.unit_id,
    weight: Number(row.weight),
  });
  drawerOpen.value = true;
}

async function submit() {
  await formRef.value?.validate();
  if (!productForm.category_id || !productForm.unit_id) return;

  saving.value = true;
  try {
    const payload = {
      ...productForm,
      barcode: productForm.barcode || null,
      category_id: productForm.category_id,
      min_sale_price: String(productForm.min_sale_price),
      purchase_reference_price: String(productForm.purchase_reference_price),
      remark: productForm.remark || null,
      sale_reference_price: String(productForm.sale_reference_price),
      specification: productForm.specification || null,
      unit_id: productForm.unit_id,
      weight: String(productForm.weight),
    };
    if (editingId.value) {
      await updateProductApi(editingId.value, payload);
    } else {
      await createProductApi(payload);
    }
    drawerOpen.value = false;
    gridApi.query();
  } finally {
    saving.value = false;
  }
}

async function removeProduct(row: ProductRecord) {
  await deleteProductApi(row.id);
  gridApi.query();
}

</script>

<template>
  <Page auto-content-height>
    <Drawer
      v-model:open="drawerOpen"
      :confirm-loading="saving"
      :title="editingId ? '编辑商品' : '新增商品'"
      class="w-[min(720px,calc(100vw-24px))]"
      placement="right"
      @close="resetForm"
    >
      <Form ref="formRef" class="mx-3" :model="productForm" layout="vertical">
        <div class="grid grid-cols-1 gap-x-4 md:grid-cols-2">
          <Form.Item
            label="商品编码"
            name="code"
            :rules="[{ required: true, message: '请输入商品编码' }]"
          >
            <Input v-model:value="productForm.code" :maxlength="100" />
          </Form.Item>
          <Form.Item
            label="商品名称"
            name="name"
            :rules="[{ required: true, message: '请输入商品名称' }]"
          >
            <Input v-model:value="productForm.name" :maxlength="200" />
          </Form.Item>
          <Form.Item
            label="商品单位"
            name="unit_id"
            :rules="[{ required: true, message: '请选择商品单位' }]"
          >
            <ErpRemoteSelect
              v-model:value="productForm.unit_id"
              :format-option="formatUnit"
              :load="loadUnits"
              placeholder="选择已启用单位"
            />
          </Form.Item>
          <Form.Item
            label="商品分类"
            name="category_id"
            :rules="[{ required: true, message: '请选择商品分类' }]"
          >
            <ErpRemoteSelect
              v-model:value="productForm.category_id"
              :format-option="formatCategory"
              :load="loadCategories"
              placeholder="选择启用的末级分类"
            />
          </Form.Item>
          <Form.Item label="条码" name="barcode">
            <Input v-model:value="productForm.barcode" :maxlength="100" />
          </Form.Item>
          <Form.Item label="重量" name="weight">
            <InputNumber v-model:value="productForm.weight" :min="0" :precision="6" class="w-full" />
          </Form.Item>
          <Form.Item label="保质天数" name="expiry_days">
            <InputNumber v-model:value="productForm.expiry_days" :min="0" :precision="0" class="w-full" />
          </Form.Item>
          <Form.Item label="采购参考价" name="purchase_reference_price">
            <InputNumber
              v-model:value="productForm.purchase_reference_price"
              :min="0"
              :precision="4"
              class="w-full"
            />
          </Form.Item>
          <Form.Item label="销售参考价" name="sale_reference_price">
            <InputNumber
              v-model:value="productForm.sale_reference_price"
              :min="0"
              :precision="4"
              class="w-full"
            />
          </Form.Item>
          <Form.Item label="最低销售价" name="min_sale_price">
            <InputNumber
              v-model:value="productForm.min_sale_price"
              :min="0"
              :precision="4"
              class="w-full"
            />
          </Form.Item>
          <Form.Item label="状态" name="is_active">
            <Switch
              v-model:checked="productForm.is_active"
              checked-children="启用"
              un-checked-children="停用"
            />
          </Form.Item>
        </div>
        <Form.Item label="规格" name="specification">
          <Input v-model:value="productForm.specification" :maxlength="500" />
        </Form.Item>
        <Form.Item label="备注" name="remark">
          <Input.TextArea v-model:value="productForm.remark" :maxlength="500" :rows="3" show-count />
        </Form.Item>
      </Form>
      <template #footer>
        <div class="flex justify-end gap-2">
          <Button @click="drawerOpen = false">取消</Button>
          <Button :loading="saving" type="primary" @click="submit">保存商品</Button>
        </div>
      </template>
    </Drawer>

    <Grid table-title="商品主数据">
      <template #toolbar-tools>
        <div class="flex items-center gap-1">
          <Button
            v-access:code="'erp:product:create'"
            class="gap-1"
            type="primary"
            @click="openCreate"
          >
            <Plus class="size-5" />
            <span>新增商品</span>
          </Button>
          <ExportCsvButton
            file-name="商品列表.csv"
            permission="erp:product:export"
            :query="exportQuery"
            resource="product"
          />
        </div>
      </template>
      <template #status="{ row }">
        <Tag :color="row.is_active ? 'success' : 'default'">
          {{ row.is_active ? '启用' : '停用' }}
        </Tag>
      </template>
      <template #operation="{ row }">
        <VbenTableAction
          :actions="[
            {
              auth: ['erp:product:update'],
              icon: 'lucide:square-pen',
              onClick: openEdit.bind(null, row),
              text: '编辑',
              variant: 'link',
            },
            {
              auth: ['erp:product:delete'],
              danger: true,
              icon: 'lucide:trash-2',
              popConfirm: {
                cancelText: '取消',
                confirm: removeProduct.bind(null, row),
                okText: '确认',
                title: `确认删除商品 ${row.name} 吗？`,
              },
              text: '删除',
              variant: 'link',
            },
          ]"
        />
      </template>
    </Grid>
  </Page>
</template>
