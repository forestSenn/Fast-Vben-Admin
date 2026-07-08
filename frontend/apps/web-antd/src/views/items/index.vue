<script setup lang="ts">
import type { TableColumnsType } from 'ant-design-vue';
import type { UploadProps } from 'ant-design-vue';

import type { ItemPayload, ItemRecord } from '#/api';

import { onMounted, reactive, ref } from 'vue';

import {
  createItemApi,
  deleteItemApi,
  downloadApi,
  importItemsApi,
  itemsExportPath,
  itemsImportTemplatePath,
  listItemsApi,
  updateItemApi,
} from '#/api';

import {
  Button as AButton,
  Form as AForm,
  FormItem as AFormItem,
  Input as AInput,
  InputSearch as AInputSearch,
  Modal as AModal,
  Space as ASpace,
  Table as ATable,
  Textarea as ATextarea,
  message,
} from 'ant-design-vue';

const loading = ref(false);
const modalOpen = ref(false);
const saving = ref(false);
const importOpen = ref(false);
const importing = ref(false);
const editingItem = ref<ItemRecord | null>(null);
const items = ref<ItemRecord[]>([]);

const query = reactive({
  keyword: '',
  page: 1,
  pageSize: 20,
  total: 0,
});

type ItemFormState = Omit<ItemPayload, 'description'> & {
  description: string;
};

const formState = reactive<ItemFormState>({
  description: '',
  title: '',
});

const columns: TableColumnsType<ItemRecord> = [
  { dataIndex: 'title', title: '标题' },
  { dataIndex: 'description', title: '描述' },
  { dataIndex: 'updated_at', title: '更新时间' },
  { dataIndex: 'actions', fixed: 'right', title: '操作', width: 160 },
];

function resetForm() {
  formState.title = '';
  formState.description = '';
}

async function loadItems() {
  loading.value = true;
  try {
    const result = await listItemsApi({
      keyword: query.keyword || undefined,
      page: query.page,
      page_size: query.pageSize,
    });
    items.value = result.items;
    query.total = result.total;
  } finally {
    loading.value = false;
  }
}

function openCreate() {
  editingItem.value = null;
  resetForm();
  modalOpen.value = true;
}

function openEdit(item: ItemRecord) {
  editingItem.value = item;
  formState.title = item.title;
  formState.description = item.description || '';
  modalOpen.value = true;
}

async function saveItem() {
  if (!formState.title) {
    message.warning('请输入标题');
    return;
  }

  saving.value = true;
  try {
    if (editingItem.value) {
      await updateItemApi(editingItem.value.id, { ...formState });
      message.success('资源已更新');
    } else {
      await createItemApi({ ...formState });
      message.success('资源已创建');
    }
    modalOpen.value = false;
    await loadItems();
  } finally {
    saving.value = false;
  }
}

function confirmDelete(item: ItemRecord) {
  AModal.confirm({
    content: `确认删除 ${item.title}？`,
    okText: '删除',
    okType: 'danger',
    title: '删除资源',
    async onOk() {
      await deleteItemApi(item.id);
      message.success('资源已删除');
      await loadItems();
    },
  });
}

function asItemRecord(record: Record<string, any>) {
  return record as ItemRecord;
}

function handleTableChange(pagination: { current?: number; pageSize?: number }) {
  query.page = pagination.current || 1;
  query.pageSize = pagination.pageSize || 20;
  void loadItems();
}

function search() {
  query.page = 1;
  void loadItems();
}

async function exportItems() {
  await downloadApi(itemsExportPath, 'items.csv');
}

async function downloadTemplate() {
  await downloadApi(itemsImportTemplatePath, 'items-import-template.csv');
}

const beforeImportUpload: UploadProps['beforeUpload'] = async (file) => {
  importing.value = true;
  try {
    const result = await importItemsApi(file);
    if (result.failed > 0) {
      message.warning(`导入完成：成功 ${result.success} 条，失败 ${result.failed} 条`);
    } else {
      message.success(`导入成功：${result.success} 条`);
    }
    importOpen.value = false;
    await loadItems();
  } finally {
    importing.value = false;
  }
  return false;
};

onMounted(loadItems);
</script>

<template>
  <div class="p-4">
    <div class="mb-4 flex flex-wrap items-center gap-3">
      <a-input-search
        v-model:value="query.keyword"
        allow-clear
        class="max-w-80"
        placeholder="搜索标题或描述"
        @search="search"
      />
      <a-button type="primary" @click="openCreate">新增资源</a-button>
      <a-button @click="exportItems">导出</a-button>
      <a-button @click="downloadTemplate">模板</a-button>
      <a-button @click="importOpen = true">导入</a-button>
      <a-button @click="loadItems">刷新</a-button>
    </div>

    <a-table
      :columns="columns"
      :data-source="items"
      :loading="loading"
      :pagination="{
        current: query.page,
        pageSize: query.pageSize,
        showSizeChanger: true,
        total: query.total,
      }"
      row-key="id"
      @change="handleTableChange"
    >
      <template #bodyCell="{ column, record }">
        <template v-if="column.dataIndex === 'description'">
          {{ record.description || '-' }}
        </template>
        <template v-else-if="column.dataIndex === 'updated_at'">
          {{ record.updated_at || '-' }}
        </template>
        <template v-else-if="column.dataIndex === 'actions'">
          <a-space>
            <a-button size="small" type="link" @click="openEdit(asItemRecord(record))">
              编辑
            </a-button>
            <a-button
              danger
              size="small"
              type="link"
              @click="confirmDelete(asItemRecord(record))"
            >
              删除
            </a-button>
          </a-space>
        </template>
      </template>
    </a-table>

    <a-modal
      v-model:open="modalOpen"
      :confirm-loading="saving"
      :title="editingItem ? '编辑资源' : '新增资源'"
      @ok="saveItem"
    >
      <a-form :label-col="{ span: 5 }" :model="formState">
        <a-form-item label="标题" required>
          <a-input v-model:value="formState.title" />
        </a-form-item>
        <a-form-item label="描述">
          <a-textarea v-model:value="formState.description" :rows="4" />
        </a-form-item>
      </a-form>
    </a-modal>

    <a-modal
      v-model:open="importOpen"
      :confirm-loading="importing"
      :footer="null"
      title="导入资源"
    >
      <a-upload-dragger :before-upload="beforeImportUpload" :max-count="1" accept=".csv">
        <div class="py-8">
          <p class="text-base">点击或拖拽 CSV 文件到此处上传</p>
        </div>
      </a-upload-dragger>
    </a-modal>
  </div>
</template>
