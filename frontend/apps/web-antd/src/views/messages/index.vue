<script setup lang="ts">
import type { TableColumnsType } from 'ant-design-vue';

import type { UserMessageRecord } from '#/api';

import { onMounted, reactive, ref } from 'vue';

import { listMyMessagesApi, markMessageReadApi } from '#/api';

import {
  Button as AButton,
  Modal as AModal,
  Select as ASelect,
  SelectOption as ASelectOption,
  Space as ASpace,
  Table as ATable,
  Tag as ATag,
  message,
} from 'ant-design-vue';

const loading = ref(false);
const detailOpen = ref(false);
const selectedMessage = ref<UserMessageRecord | null>(null);
const messages = ref<UserMessageRecord[]>([]);

const query = reactive({
  isRead: undefined as number | undefined,
  page: 1,
  pageSize: 20,
  total: 0,
});

const columns: TableColumnsType<UserMessageRecord> = [
  { dataIndex: 'title', title: '标题' },
  { dataIndex: 'type', title: '类型', width: 110 },
  { dataIndex: 'is_read', title: '状态', width: 100 },
  { dataIndex: 'created_at', title: '创建时间', width: 220 },
  { dataIndex: 'read_at', title: '阅读时间', width: 220 },
  { dataIndex: 'actions', fixed: 'right', title: '操作', width: 150 },
];

async function loadMessages() {
  loading.value = true;
  try {
    const result = await listMyMessagesApi({
      is_read: query.isRead === undefined ? undefined : query.isRead === 1,
      page: query.page,
      page_size: query.pageSize,
    });
    messages.value = result.items;
    query.total = result.total;
  } finally {
    loading.value = false;
  }
}

async function openDetail(record: UserMessageRecord) {
  selectedMessage.value = record;
  detailOpen.value = true;
  if (!record.is_read) {
    const updated = await markMessageReadApi(record.id);
    Object.assign(record, updated);
  }
}

async function markRead(record: UserMessageRecord) {
  await markMessageReadApi(record.id);
  message.success('消息已标记为已读');
  await loadMessages();
}

function asMessageRecord(record: Record<string, any>) {
  return record as UserMessageRecord;
}

function handleTableChange(pagination: { current?: number; pageSize?: number }) {
  query.page = pagination.current || 1;
  query.pageSize = pagination.pageSize || 20;
  void loadMessages();
}

function search() {
  query.page = 1;
  void loadMessages();
}

onMounted(loadMessages);
</script>

<template>
  <div class="p-4">
    <div class="mb-4 flex flex-wrap items-center gap-3">
      <a-select
        v-model:value="query.isRead"
        allow-clear
        class="w-32"
        placeholder="状态"
        @change="search"
      >
        <a-select-option :value="0">未读</a-select-option>
        <a-select-option :value="1">已读</a-select-option>
      </a-select>
      <a-button @click="loadMessages">刷新</a-button>
    </div>

    <a-table
      :columns="columns"
      :data-source="messages"
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
        <template v-if="column.dataIndex === 'is_read'">
          <a-tag :color="record.is_read ? 'default' : 'blue'">
            {{ record.is_read ? '已读' : '未读' }}
          </a-tag>
        </template>
        <template v-else-if="column.dataIndex === 'created_at'">
          {{ record.created_at || '-' }}
        </template>
        <template v-else-if="column.dataIndex === 'read_at'">
          {{ record.read_at || '-' }}
        </template>
        <template v-else-if="column.dataIndex === 'actions'">
          <a-space>
            <a-button size="small" type="link" @click="openDetail(asMessageRecord(record))">
              详情
            </a-button>
            <a-button
              v-if="!record.is_read"
              size="small"
              type="link"
              @click="markRead(asMessageRecord(record))"
            >
              已读
            </a-button>
          </a-space>
        </template>
      </template>
    </a-table>

    <a-modal v-model:open="detailOpen" title="消息详情" width="680px" :footer="null">
      <div v-if="selectedMessage" class="space-y-3">
        <div><strong>标题：</strong>{{ selectedMessage.title }}</div>
        <div><strong>类型：</strong>{{ selectedMessage.type }}</div>
        <div><strong>内容：</strong>{{ selectedMessage.content }}</div>
        <div><strong>创建时间：</strong>{{ selectedMessage.created_at || '-' }}</div>
        <div><strong>阅读时间：</strong>{{ selectedMessage.read_at || '-' }}</div>
      </div>
    </a-modal>
  </div>
</template>
