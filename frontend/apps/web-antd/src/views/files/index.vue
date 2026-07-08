<script setup lang="ts">
import type { TableColumnsType, UploadProps } from 'ant-design-vue';

import type { FileAssetRecord } from '#/api';

import { onMounted, reactive, ref } from 'vue';

import {
  deleteFileApi,
  downloadApi,
  getFileDownloadUrl,
  listFilesApi,
  uploadFileApi,
} from '#/api';

import {
  Button as AButton,
  Checkbox as ACheckbox,
  InputSearch as AInputSearch,
  Modal as AModal,
  Space as ASpace,
  Table as ATable,
  Tag as ATag,
  message,
} from 'ant-design-vue';

const loading = ref(false);
const uploading = ref(false);
const uploadOpen = ref(false);
const uploadPublic = ref(false);
const files = ref<FileAssetRecord[]>([]);

const query = reactive({
  keyword: '',
  page: 1,
  pageSize: 20,
  total: 0,
});

const columns: TableColumnsType<FileAssetRecord> = [
  { dataIndex: 'original_name', title: '文件名' },
  { dataIndex: 'content_type', title: '类型', width: 180 },
  { dataIndex: 'size', title: '大小', width: 120 },
  { dataIndex: 'storage_provider', title: '存储', width: 100 },
  { dataIndex: 'is_public', title: '公开', width: 90 },
  { dataIndex: 'created_at', title: '上传时间', width: 220 },
  { dataIndex: 'actions', fixed: 'right', title: '操作', width: 150 },
];

function formatSize(size: number) {
  if (size < 1024) return `${size} B`;
  if (size < 1024 * 1024) return `${(size / 1024).toFixed(1)} KB`;
  return `${(size / 1024 / 1024).toFixed(1)} MB`;
}

async function loadFiles() {
  loading.value = true;
  try {
    const result = await listFilesApi({
      keyword: query.keyword || undefined,
      page: query.page,
      page_size: query.pageSize,
    });
    files.value = result.items;
    query.total = result.total;
  } finally {
    loading.value = false;
  }
}

const beforeUpload: UploadProps['beforeUpload'] = async (file) => {
  uploading.value = true;
  try {
    await uploadFileApi(file, uploadPublic.value);
    message.success('文件已上传');
    uploadOpen.value = false;
    await loadFiles();
  } finally {
    uploading.value = false;
  }
  return false;
};

function confirmDelete(file: FileAssetRecord) {
  AModal.confirm({
    content: `确认删除 ${file.original_name}？`,
    okText: '删除',
    okType: 'danger',
    title: '删除文件',
    async onOk() {
      await deleteFileApi(file.id);
      message.success('文件已删除');
      await loadFiles();
    },
  });
}

async function downloadFile(file: FileAssetRecord) {
  await downloadApi(getFileDownloadUrl(file.id), file.original_name);
}

function asFileRecord(record: Record<string, any>) {
  return record as FileAssetRecord;
}

function handleTableChange(pagination: { current?: number; pageSize?: number }) {
  query.page = pagination.current || 1;
  query.pageSize = pagination.pageSize || 20;
  void loadFiles();
}

function search() {
  query.page = 1;
  void loadFiles();
}

onMounted(loadFiles);
</script>

<template>
  <div class="p-4">
    <div class="mb-4 flex flex-wrap items-center gap-3">
      <a-input-search
        v-model:value="query.keyword"
        allow-clear
        class="max-w-80"
        placeholder="搜索文件名、类型或扩展名"
        @search="search"
      />
      <a-button type="primary" @click="uploadOpen = true">上传文件</a-button>
      <a-button @click="loadFiles">刷新</a-button>
    </div>

    <a-table
      :columns="columns"
      :data-source="files"
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
        <template v-if="column.dataIndex === 'content_type'">
          {{ record.content_type || '-' }}
        </template>
        <template v-else-if="column.dataIndex === 'size'">
          {{ formatSize(record.size) }}
        </template>
        <template v-else-if="column.dataIndex === 'is_public'">
          <a-tag :color="record.is_public ? 'green' : 'default'">
            {{ record.is_public ? '是' : '否' }}
          </a-tag>
        </template>
        <template v-else-if="column.dataIndex === 'created_at'">
          {{ record.created_at || '-' }}
        </template>
        <template v-else-if="column.dataIndex === 'actions'">
          <a-space>
            <a-button
              size="small"
              type="link"
              @click="downloadFile(asFileRecord(record))"
            >
              下载
            </a-button>
            <a-button
              danger
              size="small"
              type="link"
              @click="confirmDelete(asFileRecord(record))"
            >
              删除
            </a-button>
          </a-space>
        </template>
      </template>
    </a-table>

    <a-modal
      v-model:open="uploadOpen"
      :confirm-loading="uploading"
      :footer="null"
      title="上传文件"
    >
      <div class="space-y-4">
        <a-checkbox v-model:checked="uploadPublic">公开访问</a-checkbox>
        <a-upload-dragger :before-upload="beforeUpload" :max-count="1">
          <div class="py-8">
            <p class="text-base">点击或拖拽文件到此处上传</p>
          </div>
        </a-upload-dragger>
      </div>
    </a-modal>
  </div>
</template>
