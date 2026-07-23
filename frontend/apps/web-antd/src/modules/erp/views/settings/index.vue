<script lang="ts" setup>
import type { VxeTableGridOptions } from '#/adapter/vxe-table';
import type { FormInstance } from 'ant-design-vue';
import type {
  ProductCategoryRecord,
  ProductUnitRecord,
  WarehouseRecord,
} from '#/modules/erp/api/erp';
import type { UserRecord } from '#/api';

import { computed, reactive, ref, watch } from 'vue';
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
  Switch,
  Tag,
} from 'ant-design-vue';

import { useVbenVxeGrid, VbenTableAction } from '#/adapter/vxe-table';
import ExportCsvButton from '#/modules/erp/components/export-csv-button.vue';
import ErpRemoteSelect from '#/modules/erp/components/erp-remote-select.vue';
import {
  createMasterDataApi,
  deleteMasterDataApi,
  listMasterDataApi,
  listProductCategoriesApi,
  updateMasterDataApi,
  listWarehouseUsersApi,
  replaceWarehouseUsersApi,
} from '#/modules/erp/api/erp';
import { listUsersApi } from '#/api';
import { buildKeyword } from '#/views/system/shared/utils';

type MasterDataKind = 'category' | 'unit' | 'warehouse';
type MasterDataRecord =
  | ProductCategoryRecord
  | ProductUnitRecord
  | WarehouseRecord;

const route = useRoute();

function kindForPath(path: string): MasterDataKind {
  if (path === '/erp/product/categories') return 'category';
  if (path === '/erp/stock/warehouses') return 'warehouse';
  return 'unit';
}

const isDedicatedPage = computed(() => route.path !== '/erp/settings');

interface MasterDataForm {
  address?: string;
  code: string;
  contact_name?: string;
  contact_phone?: string;
  is_active: boolean;
  is_default: boolean;
  name: string;
  parent_id?: string;
  remark?: string;
  sort: number;
  symbol?: string;
  storage_fee_reference: number;
  transport_fee_reference: number;
}

const kind = ref<MasterDataKind>(kindForPath(route.path));
const drawerOpen = ref(false);
const saving = ref(false);
const editingId = ref<string>();
const exportQuery = ref<Record<string, string>>({});
const formRef = ref<FormInstance>();
const categories = ref<ProductCategoryRecord[]>([]);
const grantOpen = ref(false);
const grantSaving = ref(false);
const grantWarehouse = ref<WarehouseRecord>();
const users = ref<UserRecord[]>([]);
const grantedUserIds = ref<string[]>([]);
const form = reactive<MasterDataForm>({
  address: undefined,
  code: '',
  contact_name: undefined,
  contact_phone: undefined,
  is_active: true,
  is_default: false,
  name: '',
  parent_id: undefined,
  remark: undefined,
  sort: 0,
  symbol: undefined,
  storage_fee_reference: 0,
  transport_fee_reference: 0,
});

const labels: Record<MasterDataKind, string> = {
  category: '商品分类',
  unit: '商品单位',
  warehouse: '仓库',
};

const permissionPrefix: Record<MasterDataKind, string> = {
  category: 'erp:product-category',
  unit: 'erp:product-unit',
  warehouse: 'erp:warehouse',
};

const drawerTitle = computed(
  () => `${editingId.value ? '编辑' : '新增'}${labels[kind.value]}`,
);

const [Grid, gridApi] = useVbenVxeGrid({
  formOptions: {
    schema: [
      {
        component: 'Input',
        componentProps: { placeholder: '按编码或名称检索' },
        fieldName: 'keyword',
        label: '检索',
      },
    ],
    submitOnChange: true,
  },
  gridOptions: {
    columns: [
      { field: 'code', minWidth: 160, title: '编码' },
      { field: 'name', minWidth: 220, title: '名称' },
      { field: 'symbol', minWidth: 110, title: '单位符号' },
      { field: 'parent_id', minWidth: 210, title: '上级分类 ID' },
      { field: 'contact_name', minWidth: 140, title: '联系人' },
      { field: 'contact_phone', minWidth: 150, title: '联系电话' },
      { field: 'address', minWidth: 240, showOverflow: true, title: '地址' },
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
        width: 260,
      },
    ],
    height: 'auto',
    keepSource: true,
    proxyConfig: {
      ajax: {
        query: async ({ page }, values) => {
          const keyword = buildKeyword(values.keyword);
          exportQuery.value = keyword ? { keyword } : {};
          return await listMasterDataApi(kind.value, {
            keyword: keyword || undefined,
            page: page.currentPage,
            page_size: page.pageSize,
          });
        },
      },
    },
    rowConfig: { keyField: 'id' },
    toolbarConfig: { custom: true, refresh: true, search: true, zoom: true },
  } as VxeTableGridOptions<MasterDataRecord>,
});

function resetForm() {
  Object.assign(form, {
    address: undefined,
    code: '',
    contact_name: undefined,
    contact_phone: undefined,
    is_active: true,
    is_default: false,
    name: '',
    parent_id: undefined,
    remark: undefined,
    sort: 0,
    symbol: undefined,
    storage_fee_reference: 0,
    transport_fee_reference: 0,
  });
  formRef.value?.clearValidate();
}

function formatCategory(category: ProductCategoryRecord) {
  return { label: `${category.name} (${category.code})`, value: category.id };
}

async function loadCategories(keyword: string) {
  const result = await listProductCategoriesApi({ keyword, page: 1, page_size: 50 });
  categories.value = result.items.filter((category) => category.id !== editingId.value);
  return categories.value;
}

function formatUser(user: UserRecord) {
  return { label: `${user.full_name || user.email} (${user.email})`, value: user.id };
}

async function loadUsers(keyword: string) {
  const result = await listUsersApi({ is_active: true, keyword, page: 1, page_size: 50 });
  users.value = result.items;
  return users.value;
}

async function openCreate() {
  editingId.value = undefined;
  resetForm();
  drawerOpen.value = true;
}

async function openEdit(row: MasterDataRecord) {
  editingId.value = row.id;
  Object.assign(form, {
    address: 'address' in row ? row.address || undefined : undefined,
    code: row.code,
    contact_name:
      'contact_name' in row ? row.contact_name || undefined : undefined,
    contact_phone:
      'contact_phone' in row ? row.contact_phone || undefined : undefined,
    is_active: row.is_active,
    is_default: 'is_default' in row ? row.is_default : false,
    name: row.name,
    parent_id: 'parent_id' in row ? row.parent_id || undefined : undefined,
    remark: 'remark' in row ? row.remark || undefined : undefined,
    sort: 'sort' in row ? row.sort : 0,
    symbol: 'symbol' in row ? row.symbol || undefined : undefined,
    storage_fee_reference: 'storage_fee_reference' in row ? Number(row.storage_fee_reference) : 0,
    transport_fee_reference: 'transport_fee_reference' in row ? Number(row.transport_fee_reference) : 0,
  });
  drawerOpen.value = true;
}

async function openWarehouseUsers(row: MasterDataRecord) {
  if (!('contact_name' in row)) return;
  grantWarehouse.value = row;
  const grantResult = await listWarehouseUsersApi(row.id);
  grantedUserIds.value = grantResult.items.map((item) => item.user_id);
  grantOpen.value = true;
}

async function saveWarehouseUsers() {
  if (!grantWarehouse.value) return;
  grantSaving.value = true;
  try {
    await replaceWarehouseUsersApi(
      grantWarehouse.value.id,
      grantedUserIds.value,
    );
    grantOpen.value = false;
  } finally {
    grantSaving.value = false;
  }
}

function payload() {
  const shared = {
    code: form.code,
    is_active: form.is_active,
    name: form.name,
  };
  if (kind.value === 'unit') return { ...shared, symbol: form.symbol || null };
  if (kind.value === 'category') {
    return { ...shared, parent_id: form.parent_id || null, sort: form.sort };
  }
  return {
    ...shared,
    address: form.address || null,
    contact_name: form.contact_name || null,
    contact_phone: form.contact_phone || null,
    is_default: form.is_default,
    remark: form.remark || null,
    sort: form.sort,
    storage_fee_reference: String(form.storage_fee_reference),
    transport_fee_reference: String(form.transport_fee_reference),
  };
}

async function submit() {
  await formRef.value?.validate();
  saving.value = true;
  try {
    if (editingId.value) {
      await updateMasterDataApi(kind.value, editingId.value, payload());
    } else {
      await createMasterDataApi(kind.value, payload());
    }
    drawerOpen.value = false;
    gridApi.query();
  } finally {
    saving.value = false;
  }
}

async function removeRecord(row: MasterDataRecord) {
  await deleteMasterDataApi(kind.value, row.id);
  gridApi.query();
}

function changeKind(value: MasterDataKind) {
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
    <Drawer
      v-model:open="grantOpen"
      :confirm-loading="grantSaving"
      class="w-[min(620px,calc(100vw-24px))]"
      title="仓库授权用户"
      placement="right"
    >
      <ErpRemoteSelect
        v-model:value="grantedUserIds"
        class="w-full"
        :format-option="formatUser"
        :load="loadUsers"
        mode="multiple"
        placeholder="选择可访问该仓库的启用用户"
      />
      <template #footer>
        <div class="flex justify-end gap-2">
          <Button @click="grantOpen = false">取消</Button>
          <Button :loading="grantSaving" type="primary" @click="saveWarehouseUsers">保存授权</Button>
        </div>
      </template>
    </Drawer>
    <Drawer
      v-model:open="drawerOpen"
      :confirm-loading="saving"
      :title="drawerTitle"
      class="w-[min(720px,calc(100vw-24px))]"
      placement="right"
      @close="resetForm"
    >
      <Form ref="formRef" class="mx-3" :model="form" layout="vertical">
        <div class="grid grid-cols-1 gap-x-4 md:grid-cols-2">
          <Form.Item
            label="编码"
            name="code"
            :rules="[{ required: true, message: '请输入编码' }]"
          >
            <Input v-model:value="form.code" :maxlength="50" />
          </Form.Item>
          <Form.Item
            label="名称"
            name="name"
            :rules="[{ required: true, message: '请输入名称' }]"
          >
            <Input v-model:value="form.name" :maxlength="100" />
          </Form.Item>
          <Form.Item v-if="kind === 'unit'" label="单位符号" name="symbol">
            <Input v-model:value="form.symbol" :maxlength="20" />
          </Form.Item>
          <Form.Item
            v-if="kind === 'category'"
            label="上级分类"
            name="parent_id"
          >
            <ErpRemoteSelect
              v-model:value="form.parent_id"
              allow-clear
              :format-option="formatCategory"
              :load="loadCategories"
              placeholder="不选则为一级分类"
            />
          </Form.Item>
          <Form.Item v-if="kind === 'category'" label="排序" name="sort">
            <InputNumber v-model:value="form.sort" :min="0" class="w-full" />
          </Form.Item>
          <Form.Item
            v-if="kind === 'warehouse'"
            label="联系人"
            name="contact_name"
          >
            <Input v-model:value="form.contact_name" :maxlength="100" />
          </Form.Item>
          <Form.Item
            v-if="kind === 'warehouse'"
            label="联系电话"
            name="contact_phone"
          >
            <Input v-model:value="form.contact_phone" :maxlength="50" />
          </Form.Item>
          <Form.Item v-if="kind === 'warehouse'" label="排序" name="sort">
            <InputNumber v-model:value="form.sort" :min="0" class="w-full" />
          </Form.Item>
          <Form.Item v-if="kind === 'warehouse'" label="仓储费参考" name="storage_fee_reference">
            <InputNumber v-model:value="form.storage_fee_reference" :min="0" :precision="4" class="w-full" />
          </Form.Item>
          <Form.Item v-if="kind === 'warehouse'" label="运输费参考" name="transport_fee_reference">
            <InputNumber v-model:value="form.transport_fee_reference" :min="0" :precision="4" class="w-full" />
          </Form.Item>
          <Form.Item
            v-if="kind === 'warehouse'"
            label="默认仓库"
            name="is_default"
          >
            <Switch
              v-model:checked="form.is_default"
              checked-children="默认"
              un-checked-children="普通"
            />
          </Form.Item>
          <Form.Item label="状态" name="is_active">
            <Switch
              v-model:checked="form.is_active"
              checked-children="启用"
              un-checked-children="停用"
            />
          </Form.Item>
        </div>
        <Form.Item v-if="kind === 'warehouse'" label="地址" name="address">
          <Input.TextArea
            v-model:value="form.address"
            :maxlength="500"
            :rows="3"
            show-count
          />
        </Form.Item>
        <Form.Item v-if="kind === 'warehouse'" label="备注" name="remark">
          <Input.TextArea
            v-model:value="form.remark"
            :maxlength="500"
            :rows="2"
            show-count
          />
        </Form.Item>
      </Form>
      <template #footer>
        <div class="flex justify-end gap-2">
          <Button @click="drawerOpen = false">取消</Button>
          <Button :loading="saving" type="primary" @click="submit">保存</Button>
        </div>
      </template>
    </Drawer>

    <div
      class="mb-3 flex flex-wrap items-center justify-between gap-3 border-b border-[var(--vben-border-color)] pb-3"
    >
      <div>
        <div class="text-base font-semibold">{{ isDedicatedPage ? labels[kind] : '基础资料' }}</div>
        <div class="mt-1 text-sm text-[var(--vben-text-color-2)]">
          {{ isDedicatedPage ? `维护${labels[kind]}资料` : '维护商品单位、分类和库存仓库' }}
        </div>
      </div>
      <Segmented
        v-if="!isDedicatedPage"
        :options="[
          { label: '商品单位', value: 'unit' },
          { label: '商品分类', value: 'category' },
          { label: '仓库', value: 'warehouse' },
        ]"
        :value="kind"
        @change="changeKind($event as MasterDataKind)"
      />
    </div>
    <Grid :table-title="labels[kind]">
      <template #toolbar-tools>
        <div class="flex items-center gap-1">
          <Button
            v-access:code="`${permissionPrefix[kind]}:create`"
            class="gap-1"
            type="primary"
            @click="openCreate"
          >
            <Plus class="size-5" />
            <span>新增{{ labels[kind] }}</span>
          </Button>
          <ExportCsvButton
            :file-name="`${labels[kind]}列表.csv`"
            :permission="`${permissionPrefix[kind]}:export`"
            :query="exportQuery"
            :resource="
              kind === 'unit'
                ? 'product-unit'
                : kind === 'category'
                  ? 'product-category'
                  : 'warehouse'
            "
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
            { auth: ['erp:warehouse:assign'], icon: 'lucide:users', ifShow: () => kind === 'warehouse', onClick: openWarehouseUsers.bind(null, row), text: '授权用户', variant: 'link' },
            { auth: [`${permissionPrefix[kind]}:update`], icon: 'lucide:square-pen', onClick: openEdit.bind(null, row), text: '编辑', variant: 'link' },
            { auth: [`${permissionPrefix[kind]}:delete`], danger: true, icon: 'lucide:trash-2', popConfirm: { cancelText: '取消', confirm: removeRecord.bind(null, row), okText: '确认', title: `确认删除${labels[kind]} ${row.name} 吗？` }, text: '删除', variant: 'link' },
          ]"
        />
      </template>
    </Grid>
  </Page>
</template>
