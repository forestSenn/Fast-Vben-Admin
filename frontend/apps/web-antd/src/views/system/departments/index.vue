<script setup lang="ts">
import type { TableColumnsType } from 'ant-design-vue';

import type { DepartmentRecord } from '#/api';

import { computed, onMounted, reactive, ref } from 'vue';

import {
  createDepartmentApi,
  deleteDepartmentApi,
  listDepartmentsApi,
  updateDepartmentApi,
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
  Space as ASpace,
  Switch as ASwitch,
  Table as ATable,
  Tag as ATag,
  message,
} from 'ant-design-vue';

const loading = ref(false);
const modalOpen = ref(false);
const saving = ref(false);
const editingDepartment = ref<DepartmentRecord | null>(null);
const departments = ref<DepartmentRecord[]>([]);

const query = reactive({
  keyword: '',
  page: 1,
  pageSize: 200,
  total: 0,
});

interface DepartmentFormState {
  code: string;
  is_active: boolean;
  leader_user_id?: string;
  name: string;
  parent_id?: string;
  sort: number;
}

const formState = reactive<DepartmentFormState>({
  code: '',
  is_active: true,
  leader_user_id: undefined,
  name: '',
  parent_id: undefined,
  sort: 0,
});

const columns: TableColumnsType<DepartmentRecord> = [
  { dataIndex: 'name', title: '部门名称' },
  { dataIndex: 'code', title: '部门编码' },
  { dataIndex: 'parent_id', title: '上级部门' },
  { dataIndex: 'leader_user_id', title: '负责人' },
  { dataIndex: 'is_active', title: '状态', width: 100 },
  { dataIndex: 'sort', title: '排序', width: 90 },
  { dataIndex: 'updated_at', title: '更新时间' },
  { dataIndex: 'actions', fixed: 'right', title: '操作', width: 160 },
];

const departmentNameMap = computed(() => {
  return new Map(departments.value.map((department) => [department.id, department.name]));
});

const parentOptions = computed(() =>
  departments.value
    .filter((department) => department.id !== editingDepartment.value?.id)
    .map((department) => ({
      label: department.name,
      value: department.id,
    })),
);

function resetForm() {
  formState.code = '';
  formState.is_active = true;
  formState.leader_user_id = undefined;
  formState.name = '';
  formState.parent_id = undefined;
  formState.sort = 0;
}

async function loadDepartments() {
  loading.value = true;
  try {
    const result = await listDepartmentsApi({
      keyword: query.keyword || undefined,
      page: query.page,
      page_size: query.pageSize,
    });
    departments.value = result.items;
    query.total = result.total;
  } finally {
    loading.value = false;
  }
}

function openCreate() {
  editingDepartment.value = null;
  resetForm();
  modalOpen.value = true;
}

function openEdit(department: DepartmentRecord) {
  editingDepartment.value = department;
  formState.code = department.code;
  formState.is_active = !!department.is_active;
  formState.leader_user_id = department.leader_user_id || undefined;
  formState.name = department.name;
  formState.parent_id = department.parent_id || undefined;
  formState.sort = department.sort ?? 0;
  modalOpen.value = true;
}

async function saveDepartment() {
  if (!formState.code || !formState.name) {
    message.warning('请输入部门名称和编码');
    return;
  }

  saving.value = true;
  try {
    const payload = {
      ...formState,
      leader_user_id: formState.leader_user_id || undefined,
      parent_id: formState.parent_id || undefined,
    };
    if (editingDepartment.value) {
      await updateDepartmentApi(editingDepartment.value.id, payload);
      message.success('部门已更新');
    } else {
      await createDepartmentApi(payload);
      message.success('部门已创建');
    }
    modalOpen.value = false;
    await loadDepartments();
  } finally {
    saving.value = false;
  }
}

function confirmDelete(department: DepartmentRecord) {
  AModal.confirm({
    content: `确认删除部门 ${department.name}？`,
    okText: '删除',
    okType: 'danger',
    title: '删除部门',
    async onOk() {
      await deleteDepartmentApi(department.id);
      message.success('部门已删除');
      await loadDepartments();
    },
  });
}

function asDepartmentRecord(record: Record<string, any>) {
  return record as DepartmentRecord;
}

function handleTableChange(pagination: { current?: number; pageSize?: number }) {
  query.page = pagination.current || 1;
  query.pageSize = pagination.pageSize || 200;
  void loadDepartments();
}

function search() {
  query.page = 1;
  void loadDepartments();
}

onMounted(loadDepartments);
</script>

<template>
  <div class="p-4">
    <div class="mb-4 flex flex-wrap items-center gap-3">
      <a-input-search
        v-model:value="query.keyword"
        allow-clear
        class="max-w-80"
        placeholder="搜索部门名称或编码"
        @search="search"
      />
      <a-button type="primary" @click="openCreate">新增部门</a-button>
      <a-button @click="loadDepartments">刷新</a-button>
    </div>

    <a-table
      :columns="columns"
      :data-source="departments"
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
        <template v-if="column.dataIndex === 'parent_id'">
          {{ record.parent_id ? departmentNameMap.get(record.parent_id) || '-' : '-' }}
        </template>
        <template v-else-if="column.dataIndex === 'leader_user_id'">
          {{ record.leader_user_id || '-' }}
        </template>
        <template v-else-if="column.dataIndex === 'is_active'">
          <a-tag :color="record.is_active ? 'green' : 'red'">
            {{ record.is_active ? '启用' : '禁用' }}
          </a-tag>
        </template>
        <template v-else-if="column.dataIndex === 'updated_at'">
          {{ record.updated_at || '-' }}
        </template>
        <template v-else-if="column.dataIndex === 'actions'">
          <a-space>
            <a-button
              size="small"
              type="link"
              @click="openEdit(asDepartmentRecord(record))"
            >
              编辑
            </a-button>
            <a-button
              danger
              size="small"
              type="link"
              @click="confirmDelete(asDepartmentRecord(record))"
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
      :title="editingDepartment ? '编辑部门' : '新增部门'"
      @ok="saveDepartment"
    >
      <a-form :label-col="{ span: 6 }" :model="formState">
        <a-form-item label="部门名称" required>
          <a-input v-model:value="formState.name" />
        </a-form-item>
        <a-form-item label="部门编码" required>
          <a-input v-model:value="formState.code" />
        </a-form-item>
        <a-form-item label="上级部门">
          <a-select
            v-model:value="formState.parent_id"
            allow-clear
            :options="parentOptions"
            placeholder="不选择则为顶级"
          />
        </a-form-item>
        <a-form-item label="负责人ID">
          <a-input v-model:value="formState.leader_user_id" />
        </a-form-item>
        <a-form-item label="排序">
          <a-input-number v-model:value="formState.sort" class="w-full" />
        </a-form-item>
        <a-form-item label="启用">
          <a-switch v-model:checked="formState.is_active" />
        </a-form-item>
      </a-form>
    </a-modal>
  </div>
</template>
