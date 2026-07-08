<script setup lang="ts">
import type { TableColumnsType } from 'ant-design-vue';

import type { SystemSettingRecord } from '#/api';

import { onMounted, reactive, ref } from 'vue';

import { listSettingsApi, updateSettingApi } from '#/api';

import {
  Button as AButton,
  Form as AForm,
  FormItem as AFormItem,
  Input as AInput,
  InputSearch as AInputSearch,
  Modal as AModal,
  Select as ASelect,
  SelectOption as ASelectOption,
  Space as ASpace,
  Switch as ASwitch,
  Table as ATable,
  Tag as ATag,
  Textarea as ATextarea,
  message,
} from 'ant-design-vue';

const loading = ref(false);
const modalOpen = ref(false);
const saving = ref(false);
const editingSetting = ref<SystemSettingRecord | null>(null);
const settings = ref<SystemSettingRecord[]>([]);

const query = reactive({
  group: '',
  keyword: '',
  page: 1,
  pageSize: 50,
  total: 0,
});

const formState = reactive({
  description: '',
  group: '',
  is_public: false,
  is_system: false,
  name: '',
  value: '',
  value_type: 'string',
});

const columns: TableColumnsType<SystemSettingRecord> = [
  { dataIndex: 'name', title: '参数名称' },
  { dataIndex: 'key', title: '参数键' },
  { dataIndex: 'value', title: '参数值' },
  { dataIndex: 'value_type', title: '类型', width: 100 },
  { dataIndex: 'group', title: '分组', width: 120 },
  { dataIndex: 'is_public', title: '公开', width: 90 },
  { dataIndex: 'is_system', title: '内置', width: 90 },
  { dataIndex: 'updated_at', title: '更新时间' },
  { dataIndex: 'actions', fixed: 'right', title: '操作', width: 100 },
];

function resetForm() {
  formState.description = '';
  formState.group = '';
  formState.is_public = false;
  formState.is_system = false;
  formState.name = '';
  formState.value = '';
  formState.value_type = 'string';
}

async function loadSettings() {
  loading.value = true;
  try {
    const result = await listSettingsApi({
      group: query.group || undefined,
      keyword: query.keyword || undefined,
      page: query.page,
      page_size: query.pageSize,
    });
    settings.value = result.items;
    query.total = result.total;
  } finally {
    loading.value = false;
  }
}

function openEdit(setting: SystemSettingRecord) {
  editingSetting.value = setting;
  resetForm();
  formState.description = setting.description || '';
  formState.group = setting.group || '';
  formState.is_public = !!setting.is_public;
  formState.is_system = !!setting.is_system;
  formState.name = setting.name;
  formState.value = setting.value || '';
  formState.value_type = setting.value_type || 'string';
  modalOpen.value = true;
}

async function saveSetting() {
  if (!editingSetting.value) return;
  if (!formState.name || !formState.value_type) {
    message.warning('请输入参数名称和类型');
    return;
  }

  saving.value = true;
  try {
    await updateSettingApi(editingSetting.value.key, {
      description: formState.description || undefined,
      group: formState.group,
      is_public: formState.is_public,
      is_system: formState.is_system,
      name: formState.name,
      value: formState.value,
      value_type: formState.value_type,
    });
    message.success('参数已更新');
    modalOpen.value = false;
    await loadSettings();
  } finally {
    saving.value = false;
  }
}

function asSettingRecord(record: Record<string, any>) {
  return record as SystemSettingRecord;
}

function handleTableChange(pagination: { current?: number; pageSize?: number }) {
  query.page = pagination.current || 1;
  query.pageSize = pagination.pageSize || 50;
  void loadSettings();
}

function search() {
  query.page = 1;
  void loadSettings();
}

onMounted(loadSettings);
</script>

<template>
  <div class="p-4">
    <div class="mb-4 flex flex-wrap items-center gap-3">
      <a-input-search
        v-model:value="query.keyword"
        allow-clear
        class="max-w-80"
        placeholder="搜索参数名称或键"
        @search="search"
      />
      <a-select
        v-model:value="query.group"
        allow-clear
        class="w-40"
        placeholder="参数分组"
        @change="search"
      >
        <a-select-option value="system">system</a-select-option>
        <a-select-option value="auth">auth</a-select-option>
        <a-select-option value="upload">upload</a-select-option>
      </a-select>
      <a-button @click="loadSettings">刷新</a-button>
    </div>

    <a-table
      :columns="columns"
      :data-source="settings"
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
        <template v-if="column.dataIndex === 'value'">
          <span class="break-all">{{ record.value }}</span>
        </template>
        <template v-else-if="column.dataIndex === 'value_type'">
          <a-tag>{{ record.value_type }}</a-tag>
        </template>
        <template v-else-if="column.dataIndex === 'is_public'">
          <a-tag :color="record.is_public ? 'green' : 'default'">
            {{ record.is_public ? '是' : '否' }}
          </a-tag>
        </template>
        <template v-else-if="column.dataIndex === 'is_system'">
          <a-tag :color="record.is_system ? 'blue' : 'default'">
            {{ record.is_system ? '是' : '否' }}
          </a-tag>
        </template>
        <template v-else-if="column.dataIndex === 'updated_at'">
          {{ record.updated_at || '-' }}
        </template>
        <template v-else-if="column.dataIndex === 'actions'">
          <a-space>
            <a-button size="small" type="link" @click="openEdit(asSettingRecord(record))">
              编辑
            </a-button>
          </a-space>
        </template>
      </template>
    </a-table>

    <a-modal
      v-model:open="modalOpen"
      :confirm-loading="saving"
      :title="editingSetting ? `编辑参数 - ${editingSetting.key}` : '编辑参数'"
      width="640px"
      @ok="saveSetting"
    >
      <a-form :label-col="{ span: 6 }" :model="formState">
        <a-form-item label="参数名称" required>
          <a-input v-model:value="formState.name" />
        </a-form-item>
        <a-form-item label="参数值">
          <a-textarea v-model:value="formState.value" :rows="4" />
        </a-form-item>
        <a-form-item label="参数类型" required>
          <a-select v-model:value="formState.value_type">
            <a-select-option value="string">string</a-select-option>
            <a-select-option value="number">number</a-select-option>
            <a-select-option value="boolean">boolean</a-select-option>
            <a-select-option value="json">json</a-select-option>
          </a-select>
        </a-form-item>
        <a-form-item label="分组">
          <a-input v-model:value="formState.group" />
        </a-form-item>
        <a-form-item label="描述">
          <a-textarea v-model:value="formState.description" :rows="3" />
        </a-form-item>
        <a-form-item label="公开">
          <a-switch v-model:checked="formState.is_public" />
        </a-form-item>
        <a-form-item label="内置参数">
          <a-switch v-model:checked="formState.is_system" :disabled="editingSetting?.is_system" />
        </a-form-item>
      </a-form>
    </a-modal>
  </div>
</template>
