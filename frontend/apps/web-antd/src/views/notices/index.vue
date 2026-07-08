<script setup lang="ts">
import type { TableColumnsType } from 'ant-design-vue';

import type { NoticePayload, NoticeRecord } from '#/api';

import { onMounted, reactive, ref } from 'vue';

import {
  createNoticeApi,
  deleteNoticeApi,
  listNoticesApi,
  publishNoticeApi,
  updateNoticeApi,
  withdrawNoticeApi,
} from '#/api';

import {
  Button as AButton,
  Form as AForm,
  FormItem as AFormItem,
  Input as AInput,
  InputNumber as AInputNumber,
  InputSearch as AInputSearch,
  Modal as AModal,
  Select as ASelect,
  SelectOption as ASelectOption,
  Space as ASpace,
  Table as ATable,
  Tag as ATag,
  Textarea as ATextarea,
  message,
} from 'ant-design-vue';

const loading = ref(false);
const modalOpen = ref(false);
const saving = ref(false);
const editingNotice = ref<NoticeRecord | null>(null);
const notices = ref<NoticeRecord[]>([]);

const query = reactive({
  keyword: '',
  page: 1,
  pageSize: 20,
  status: undefined as string | undefined,
  total: 0,
});

type NoticeFormState = NoticePayload;

const formState = reactive<NoticeFormState>({
  content: '',
  priority: 0,
  title: '',
  type: 'notice',
});

const columns: TableColumnsType<NoticeRecord> = [
  { dataIndex: 'title', title: '标题' },
  { dataIndex: 'type', title: '类型', width: 100 },
  { dataIndex: 'priority', title: '优先级', width: 100 },
  { dataIndex: 'status', title: '状态', width: 110 },
  { dataIndex: 'published_at', title: '发布时间', width: 220 },
  { dataIndex: 'updated_at', title: '更新时间', width: 220 },
  { dataIndex: 'actions', fixed: 'right', title: '操作', width: 260 },
];

function resetForm() {
  formState.content = '';
  formState.priority = 0;
  formState.title = '';
  formState.type = 'notice';
}

function statusColor(status: string) {
  if (status === 'published') return 'green';
  if (status === 'withdrawn') return 'red';
  return 'default';
}

function statusText(status: string) {
  if (status === 'published') return '已发布';
  if (status === 'withdrawn') return '已撤回';
  return '草稿';
}

async function loadNotices() {
  loading.value = true;
  try {
    const result = await listNoticesApi({
      keyword: query.keyword || undefined,
      page: query.page,
      page_size: query.pageSize,
      status: query.status,
    });
    notices.value = result.items;
    query.total = result.total;
  } finally {
    loading.value = false;
  }
}

function openCreate() {
  editingNotice.value = null;
  resetForm();
  modalOpen.value = true;
}

function openEdit(notice: NoticeRecord) {
  editingNotice.value = notice;
  formState.content = notice.content;
  formState.priority = notice.priority;
  formState.title = notice.title;
  formState.type = notice.type;
  modalOpen.value = true;
}

async function saveNotice() {
  if (!formState.title || !formState.content) {
    message.warning('请输入公告标题和内容');
    return;
  }

  saving.value = true;
  try {
    if (editingNotice.value) {
      await updateNoticeApi(editingNotice.value.id, { ...formState });
      message.success('公告已更新');
    } else {
      await createNoticeApi({ ...formState });
      message.success('公告已创建');
    }
    modalOpen.value = false;
    await loadNotices();
  } finally {
    saving.value = false;
  }
}

async function publishNotice(notice: NoticeRecord) {
  await publishNoticeApi(notice.id);
  message.success('公告已发布');
  await loadNotices();
}

async function withdrawNotice(notice: NoticeRecord) {
  await withdrawNoticeApi(notice.id);
  message.success('公告已撤回');
  await loadNotices();
}

function confirmDelete(notice: NoticeRecord) {
  AModal.confirm({
    content: `确认删除 ${notice.title}？`,
    okText: '删除',
    okType: 'danger',
    title: '删除公告',
    async onOk() {
      await deleteNoticeApi(notice.id);
      message.success('公告已删除');
      await loadNotices();
    },
  });
}

function asNoticeRecord(record: Record<string, any>) {
  return record as NoticeRecord;
}

function handleTableChange(pagination: { current?: number; pageSize?: number }) {
  query.page = pagination.current || 1;
  query.pageSize = pagination.pageSize || 20;
  void loadNotices();
}

function search() {
  query.page = 1;
  void loadNotices();
}

onMounted(loadNotices);
</script>

<template>
  <div class="p-4">
    <div class="mb-4 flex flex-wrap items-center gap-3">
      <a-input-search
        v-model:value="query.keyword"
        allow-clear
        class="max-w-80"
        placeholder="搜索标题或内容"
        @search="search"
      />
      <a-select
        v-model:value="query.status"
        allow-clear
        class="w-32"
        placeholder="状态"
        @change="search"
      >
        <a-select-option value="draft">草稿</a-select-option>
        <a-select-option value="published">已发布</a-select-option>
        <a-select-option value="withdrawn">已撤回</a-select-option>
      </a-select>
      <a-button type="primary" @click="openCreate">新增公告</a-button>
      <a-button @click="loadNotices">刷新</a-button>
    </div>

    <a-table
      :columns="columns"
      :data-source="notices"
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
        <template v-if="column.dataIndex === 'status'">
          <a-tag :color="statusColor(record.status)">
            {{ statusText(record.status) }}
          </a-tag>
        </template>
        <template v-else-if="column.dataIndex === 'published_at'">
          {{ record.published_at || '-' }}
        </template>
        <template v-else-if="column.dataIndex === 'updated_at'">
          {{ record.updated_at || '-' }}
        </template>
        <template v-else-if="column.dataIndex === 'actions'">
          <a-space>
            <a-button size="small" type="link" @click="openEdit(asNoticeRecord(record))">
              编辑
            </a-button>
            <a-button
              v-if="record.status !== 'published'"
              size="small"
              type="link"
              @click="publishNotice(asNoticeRecord(record))"
            >
              发布
            </a-button>
            <a-button
              v-if="record.status === 'published'"
              size="small"
              type="link"
              @click="withdrawNotice(asNoticeRecord(record))"
            >
              撤回
            </a-button>
            <a-button
              danger
              size="small"
              type="link"
              @click="confirmDelete(asNoticeRecord(record))"
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
      :title="editingNotice ? '编辑公告' : '新增公告'"
      width="720px"
      @ok="saveNotice"
    >
      <a-form :label-col="{ span: 4 }" :model="formState">
        <a-form-item label="标题" required>
          <a-input v-model:value="formState.title" />
        </a-form-item>
        <a-form-item label="类型">
          <a-input v-model:value="formState.type" />
        </a-form-item>
        <a-form-item label="优先级">
          <a-input-number v-model:value="formState.priority" class="w-full" />
        </a-form-item>
        <a-form-item label="内容" required>
          <a-textarea v-model:value="formState.content" :rows="8" />
        </a-form-item>
      </a-form>
    </a-modal>
  </div>
</template>
