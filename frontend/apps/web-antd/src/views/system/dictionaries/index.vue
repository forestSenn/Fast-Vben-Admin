<script setup lang="ts">
import type { TableColumnsType } from 'ant-design-vue';

import type {
  DictionaryItemRecord,
  DictionaryTypeRecord,
} from '#/api';

import { onMounted, reactive, ref } from 'vue';

import {
  createDictionaryItemApi,
  createDictionaryTypeApi,
  deleteDictionaryItemApi,
  deleteDictionaryTypeApi,
  listDictionaryItemsApi,
  listDictionaryTypesApi,
  updateDictionaryItemApi,
  updateDictionaryTypeApi,
} from '#/api';

import {
  Button as AButton,
  Form as AForm,
  FormItem as AFormItem,
  Input as AInput,
  InputNumber as AInputNumber,
  InputSearch as AInputSearch,
  Modal as AModal,
  Space as ASpace,
  Switch as ASwitch,
  Table as ATable,
  Tag as ATag,
  Textarea as ATextarea,
  message,
} from 'ant-design-vue';

const typeLoading = ref(false);
const itemLoading = ref(false);
const typeModalOpen = ref(false);
const itemModalOpen = ref(false);
const saving = ref(false);
const editingType = ref<DictionaryTypeRecord | null>(null);
const editingItem = ref<DictionaryItemRecord | null>(null);
const selectedType = ref<DictionaryTypeRecord | null>(null);
const dictionaryTypes = ref<DictionaryTypeRecord[]>([]);
const dictionaryItems = ref<DictionaryItemRecord[]>([]);

const typeQuery = reactive({
  keyword: '',
  page: 1,
  pageSize: 20,
  total: 0,
});

const itemQuery = reactive({
  keyword: '',
  page: 1,
  pageSize: 20,
  total: 0,
});

const typeForm = reactive({
  code: '',
  description: '',
  is_active: true,
  name: '',
});

const itemForm = reactive({
  color: '',
  extra_data: '',
  is_active: true,
  label: '',
  sort: 0,
  value: '',
});

const typeColumns: TableColumnsType<DictionaryTypeRecord> = [
  { dataIndex: 'name', title: '字典名称' },
  { dataIndex: 'code', title: '编码' },
  { dataIndex: 'is_active', title: '状态', width: 90 },
  { dataIndex: 'actions', fixed: 'right', title: '操作', width: 140 },
];

const itemColumns: TableColumnsType<DictionaryItemRecord> = [
  { dataIndex: 'label', title: '标签' },
  { dataIndex: 'value', title: '值' },
  { dataIndex: 'color', title: '颜色', width: 120 },
  { dataIndex: 'sort', title: '排序', width: 90 },
  { dataIndex: 'is_active', title: '状态', width: 90 },
  { dataIndex: 'actions', fixed: 'right', title: '操作', width: 140 },
];

function resetTypeForm() {
  typeForm.code = '';
  typeForm.description = '';
  typeForm.is_active = true;
  typeForm.name = '';
}

function resetItemForm() {
  itemForm.color = '';
  itemForm.extra_data = '';
  itemForm.is_active = true;
  itemForm.label = '';
  itemForm.sort = 0;
  itemForm.value = '';
}

async function loadTypes() {
  typeLoading.value = true;
  try {
    const result = await listDictionaryTypesApi({
      keyword: typeQuery.keyword || undefined,
      page: typeQuery.page,
      page_size: typeQuery.pageSize,
    });
    dictionaryTypes.value = result.items;
    typeQuery.total = result.total;
    if (!selectedType.value && result.items.length > 0) {
      selectedType.value = result.items[0]!;
      await loadItems();
    }
  } finally {
    typeLoading.value = false;
  }
}

async function loadItems() {
  if (!selectedType.value) {
    dictionaryItems.value = [];
    itemQuery.total = 0;
    return;
  }
  itemLoading.value = true;
  try {
    const result = await listDictionaryItemsApi({
      keyword: itemQuery.keyword || undefined,
      page: itemQuery.page,
      page_size: itemQuery.pageSize,
      type_id: selectedType.value.id,
    });
    dictionaryItems.value = result.items;
    itemQuery.total = result.total;
  } finally {
    itemLoading.value = false;
  }
}

function selectType(type: DictionaryTypeRecord) {
  selectedType.value = type;
  itemQuery.page = 1;
  void loadItems();
}

function openCreateType() {
  editingType.value = null;
  resetTypeForm();
  typeModalOpen.value = true;
}

function openEditType(type: DictionaryTypeRecord) {
  editingType.value = type;
  typeForm.code = type.code;
  typeForm.description = type.description || '';
  typeForm.is_active = !!type.is_active;
  typeForm.name = type.name;
  typeModalOpen.value = true;
}

async function saveType() {
  if (!typeForm.code || !typeForm.name) {
    message.warning('请输入字典名称和编码');
    return;
  }
  saving.value = true;
  try {
    if (editingType.value) {
      await updateDictionaryTypeApi(editingType.value.id, { ...typeForm });
      message.success('字典类型已更新');
    } else {
      await createDictionaryTypeApi({ ...typeForm });
      message.success('字典类型已创建');
    }
    typeModalOpen.value = false;
    await loadTypes();
  } finally {
    saving.value = false;
  }
}

function openCreateItem() {
  if (!selectedType.value) {
    message.warning('请先选择字典类型');
    return;
  }
  editingItem.value = null;
  resetItemForm();
  itemModalOpen.value = true;
}

function openEditItem(item: DictionaryItemRecord) {
  editingItem.value = item;
  itemForm.color = item.color || '';
  itemForm.extra_data = item.extra_data || '';
  itemForm.is_active = !!item.is_active;
  itemForm.label = item.label;
  itemForm.sort = item.sort ?? 0;
  itemForm.value = item.value;
  itemModalOpen.value = true;
}

async function saveItem() {
  if (!selectedType.value || !itemForm.label || !itemForm.value) {
    message.warning('请输入字典项标签和值');
    return;
  }
  saving.value = true;
  try {
    const payload = {
      ...itemForm,
      color: itemForm.color || undefined,
      extra_data: itemForm.extra_data || undefined,
      type_id: selectedType.value.id,
    };
    if (editingItem.value) {
      await updateDictionaryItemApi(editingItem.value.id, payload);
      message.success('字典项已更新');
    } else {
      await createDictionaryItemApi(payload);
      message.success('字典项已创建');
    }
    itemModalOpen.value = false;
    await loadItems();
  } finally {
    saving.value = false;
  }
}

function confirmDeleteType(type: DictionaryTypeRecord) {
  AModal.confirm({
    content: `确认删除字典类型 ${type.name}？`,
    okText: '删除',
    okType: 'danger',
    title: '删除字典类型',
    async onOk() {
      await deleteDictionaryTypeApi(type.id);
      if (selectedType.value?.id === type.id) selectedType.value = null;
      message.success('字典类型已删除');
      await loadTypes();
      await loadItems();
    },
  });
}

function confirmDeleteItem(item: DictionaryItemRecord) {
  AModal.confirm({
    content: `确认删除字典项 ${item.label}？`,
    okText: '删除',
    okType: 'danger',
    title: '删除字典项',
    async onOk() {
      await deleteDictionaryItemApi(item.id);
      message.success('字典项已删除');
      await loadItems();
    },
  });
}

function asTypeRecord(record: Record<string, any>) {
  return record as DictionaryTypeRecord;
}

function asItemRecord(record: Record<string, any>) {
  return record as DictionaryItemRecord;
}

function getTypeRowClass(record: DictionaryTypeRecord) {
  return record.id === selectedType.value?.id ? 'bg-primary/5' : '';
}

function getTypeRow(record: DictionaryTypeRecord) {
  return {
    onClick: () => selectType(record),
  };
}

onMounted(loadTypes);
</script>

<template>
  <div class="grid gap-4 p-4 xl:grid-cols-[minmax(360px,0.8fr)_1.2fr]">
    <section>
      <div class="mb-4 flex flex-wrap items-center gap-3">
        <a-input-search
          v-model:value="typeQuery.keyword"
          allow-clear
          class="max-w-72"
          placeholder="搜索字典名称或编码"
          @search="() => { typeQuery.page = 1; void loadTypes(); }"
        />
        <a-button type="primary" @click="openCreateType">新增类型</a-button>
        <a-button @click="loadTypes">刷新</a-button>
      </div>

      <a-table
        :columns="typeColumns"
        :data-source="dictionaryTypes"
        :loading="typeLoading"
        :pagination="{
          current: typeQuery.page,
          pageSize: typeQuery.pageSize,
          showSizeChanger: true,
          total: typeQuery.total,
        }"
        row-key="id"
        :row-class-name="getTypeRowClass"
        @change="(pagination) => {
          typeQuery.page = pagination.current || 1;
          typeQuery.pageSize = pagination.pageSize || 20;
          void loadTypes();
        }"
        @row="getTypeRow"
      >
        <template #bodyCell="{ column, record }">
          <template v-if="column.dataIndex === 'is_active'">
            <a-tag :color="record.is_active ? 'green' : 'red'">
              {{ record.is_active ? '启用' : '禁用' }}
            </a-tag>
          </template>
          <template v-else-if="column.dataIndex === 'actions'">
            <a-space>
              <a-button size="small" type="link" @click.stop="openEditType(asTypeRecord(record))">
                编辑
              </a-button>
              <a-button
                danger
                size="small"
                type="link"
                @click.stop="confirmDeleteType(asTypeRecord(record))"
              >
                删除
              </a-button>
            </a-space>
          </template>
        </template>
      </a-table>
    </section>

    <section>
      <div class="mb-4 flex flex-wrap items-center gap-3">
        <a-input-search
          v-model:value="itemQuery.keyword"
          allow-clear
          class="max-w-72"
          placeholder="搜索字典项标签或值"
          @search="() => { itemQuery.page = 1; void loadItems(); }"
        />
        <a-button type="primary" :disabled="!selectedType" @click="openCreateItem">
          新增字典项
        </a-button>
        <a-button :disabled="!selectedType" @click="loadItems">刷新</a-button>
        <span class="text-sm text-muted-foreground">
          当前字典：{{ selectedType?.name || '-' }}
        </span>
      </div>

      <a-table
        :columns="itemColumns"
        :data-source="dictionaryItems"
        :loading="itemLoading"
        :pagination="{
          current: itemQuery.page,
          pageSize: itemQuery.pageSize,
          showSizeChanger: true,
          total: itemQuery.total,
        }"
        row-key="id"
        @change="(pagination) => {
          itemQuery.page = pagination.current || 1;
          itemQuery.pageSize = pagination.pageSize || 20;
          void loadItems();
        }"
      >
        <template #bodyCell="{ column, record }">
          <template v-if="column.dataIndex === 'color'">
            <a-tag :color="record.color || 'default'">{{ record.color || '-' }}</a-tag>
          </template>
          <template v-else-if="column.dataIndex === 'is_active'">
            <a-tag :color="record.is_active ? 'green' : 'red'">
              {{ record.is_active ? '启用' : '禁用' }}
            </a-tag>
          </template>
          <template v-else-if="column.dataIndex === 'actions'">
            <a-space>
              <a-button size="small" type="link" @click="openEditItem(asItemRecord(record))">
                编辑
              </a-button>
              <a-button
                danger
                size="small"
                type="link"
                @click="confirmDeleteItem(asItemRecord(record))"
              >
                删除
              </a-button>
            </a-space>
          </template>
        </template>
      </a-table>
    </section>

    <a-modal
      v-model:open="typeModalOpen"
      :confirm-loading="saving"
      :title="editingType ? '编辑字典类型' : '新增字典类型'"
      @ok="saveType"
    >
      <a-form :label-col="{ span: 6 }" :model="typeForm">
        <a-form-item label="字典名称" required>
          <a-input v-model:value="typeForm.name" />
        </a-form-item>
        <a-form-item label="字典编码" required>
          <a-input v-model:value="typeForm.code" />
        </a-form-item>
        <a-form-item label="描述">
          <a-textarea v-model:value="typeForm.description" :rows="3" />
        </a-form-item>
        <a-form-item label="启用">
          <a-switch v-model:checked="typeForm.is_active" />
        </a-form-item>
      </a-form>
    </a-modal>

    <a-modal
      v-model:open="itemModalOpen"
      :confirm-loading="saving"
      :title="editingItem ? '编辑字典项' : '新增字典项'"
      @ok="saveItem"
    >
      <a-form :label-col="{ span: 6 }" :model="itemForm">
        <a-form-item label="标签" required>
          <a-input v-model:value="itemForm.label" />
        </a-form-item>
        <a-form-item label="值" required>
          <a-input v-model:value="itemForm.value" />
        </a-form-item>
        <a-form-item label="颜色">
          <a-input v-model:value="itemForm.color" />
        </a-form-item>
        <a-form-item label="排序">
          <a-input-number v-model:value="itemForm.sort" class="w-full" />
        </a-form-item>
        <a-form-item label="启用">
          <a-switch v-model:checked="itemForm.is_active" />
        </a-form-item>
        <a-form-item label="扩展数据">
          <a-textarea v-model:value="itemForm.extra_data" :rows="3" />
        </a-form-item>
      </a-form>
    </a-modal>
  </div>
</template>
