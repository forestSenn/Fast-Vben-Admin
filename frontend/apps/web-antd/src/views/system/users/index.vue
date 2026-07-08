<script setup lang="ts">
import type { TableColumnsType } from 'ant-design-vue';

import type { DepartmentRecord, RoleRecord, UserCreatePayload, UserRecord } from '#/api';

import { onMounted, reactive, ref } from 'vue';

import {
  createUserApi,
  deleteUserApi,
  downloadApi,
  getUserRolesApi,
  listDepartmentsApi,
  listRolesApi,
  listUsersApi,
  updateUserApi,
  updateUserRolesApi,
  usersExportPath,
} from '#/api';

import {
  Button as AButton,
  Form as AForm,
  FormItem as AFormItem,
  Input as AInput,
  InputPassword as AInputPassword,
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
const editingUser = ref<null | UserRecord>(null);
const users = ref<UserRecord[]>([]);
const roles = ref<RoleRecord[]>([]);
const departments = ref<DepartmentRecord[]>([]);

const query = reactive({
  keyword: '',
  page: 1,
  pageSize: 20,
  total: 0,
});

type UserFormState = Omit<
  UserCreatePayload,
  'department_id' | 'full_name' | 'is_active' | 'is_superuser'
> & {
  department_id?: string;
  full_name: string;
  is_active: boolean;
  is_superuser: boolean;
  role_ids: string[];
};

const formState = reactive<UserFormState>({
  department_id: undefined,
  email: '',
  full_name: '',
  is_active: true,
  is_superuser: false,
  password: '',
  role_ids: [],
});

const columns: TableColumnsType<UserRecord> = [
  { dataIndex: 'email', title: '邮箱' },
  { dataIndex: 'full_name', title: '姓名' },
  { dataIndex: 'department_id', title: '部门' },
  { dataIndex: 'is_active', title: '状态' },
  { dataIndex: 'is_superuser', title: '角色' },
  { dataIndex: 'updated_at', title: '更新时间' },
  { dataIndex: 'actions', fixed: 'right', title: '操作', width: 160 },
];

function resetForm() {
  formState.department_id = undefined;
  formState.email = '';
  formState.full_name = '';
  formState.is_active = true;
  formState.is_superuser = false;
  formState.password = '';
  formState.role_ids = [];
}

async function loadUsers() {
  loading.value = true;
  try {
    const result = await listUsersApi({
      keyword: query.keyword || undefined,
      page: query.page,
      page_size: query.pageSize,
    });
    users.value = result.items;
    query.total = result.total;
  } finally {
    loading.value = false;
  }
}

async function loadOptions() {
  const [roleResult, departmentResult] = await Promise.all([
    listRolesApi({ page: 1, page_size: 200 }),
    listDepartmentsApi({ page: 1, page_size: 200 }),
  ]);
  roles.value = roleResult.items;
  departments.value = departmentResult.items;
}

function openCreate() {
  editingUser.value = null;
  resetForm();
  void loadOptions();
  modalOpen.value = true;
}

async function openEdit(user: UserRecord) {
  editingUser.value = user;
  await loadOptions();
  const userRoles = await getUserRolesApi(user.id);
  formState.department_id = user.department_id || undefined;
  formState.email = user.email;
  formState.full_name = user.full_name || '';
  formState.is_active = !!user.is_active;
  formState.is_superuser = !!user.is_superuser;
  formState.password = '';
  formState.role_ids = userRoles.map((role) => role.id);
  modalOpen.value = true;
}

async function saveUser() {
  if (!formState.email) {
    message.warning('请输入邮箱');
    return;
  }
  if (!editingUser.value && !formState.password) {
    message.warning('请输入初始密码');
    return;
  }

  saving.value = true;
  try {
    const payload = {
      department_id: formState.department_id || undefined,
      email: formState.email,
      full_name: formState.full_name,
      is_active: formState.is_active,
      is_superuser: formState.is_superuser,
      ...(formState.password ? { password: formState.password } : {}),
    };
    if (editingUser.value) {
      await updateUserApi(editingUser.value.id, payload);
      await updateUserRolesApi(editingUser.value.id, {
        role_ids: formState.role_ids,
      });
      message.success('用户已更新');
    } else {
      const user = await createUserApi({
        ...payload,
        password: formState.password,
      });
      if (formState.role_ids.length > 0) {
        await updateUserRolesApi(user.id, { role_ids: formState.role_ids });
      }
      message.success('用户已创建');
    }
    modalOpen.value = false;
    await loadUsers();
  } finally {
    saving.value = false;
  }
}

function confirmDelete(user: UserRecord) {
  AModal.confirm({
    content: `确认删除 ${user.email}？`,
    okText: '删除',
    okType: 'danger',
    title: '删除用户',
    async onOk() {
      await deleteUserApi(user.id);
      message.success('用户已删除');
      await loadUsers();
    },
  });
}

function asUserRecord(record: Record<string, any>) {
  return record as UserRecord;
}

function getDepartmentName(departmentId?: null | string) {
  if (!departmentId) return '-';
  return (
    departments.value.find((department) => department.id === departmentId)?.name ||
    departmentId
  );
}

function handleTableChange(pagination: { current?: number; pageSize?: number }) {
  query.page = pagination.current || 1;
  query.pageSize = pagination.pageSize || 20;
  void loadUsers();
}

function search() {
  query.page = 1;
  void loadUsers();
}

async function exportUsers() {
  await downloadApi(usersExportPath, 'users.csv');
}

onMounted(() => {
  void Promise.all([loadUsers(), loadOptions()]);
});
</script>

<template>
  <div class="p-4">
    <div class="mb-4 flex flex-wrap items-center gap-3">
      <a-input-search
        v-model:value="query.keyword"
        allow-clear
        class="max-w-80"
        placeholder="搜索邮箱或姓名"
        @search="search"
      />
      <a-button type="primary" @click="openCreate">新增用户</a-button>
      <a-button @click="exportUsers">导出</a-button>
      <a-button @click="loadUsers">刷新</a-button>
    </div>

    <a-table
      :columns="columns"
      :data-source="users"
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
        <template v-if="column.dataIndex === 'is_active'">
          <a-tag :color="record.is_active ? 'green' : 'red'">
            {{ record.is_active ? '启用' : '禁用' }}
          </a-tag>
        </template>
        <template v-else-if="column.dataIndex === 'department_id'">
          {{ getDepartmentName(record.department_id) }}
        </template>
        <template v-else-if="column.dataIndex === 'is_superuser'">
          <a-tag :color="record.is_superuser ? 'blue' : 'default'">
            {{ record.is_superuser ? '超级管理员' : '普通用户' }}
          </a-tag>
        </template>
        <template v-else-if="column.dataIndex === 'updated_at'">
          {{ record.updated_at || '-' }}
        </template>
        <template v-else-if="column.dataIndex === 'actions'">
          <a-space>
            <a-button size="small" type="link" @click="openEdit(asUserRecord(record))">
              编辑
            </a-button>
            <a-button
              danger
              size="small"
              type="link"
              @click="confirmDelete(asUserRecord(record))"
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
      :title="editingUser ? '编辑用户' : '新增用户'"
      @ok="saveUser"
    >
      <a-form :label-col="{ span: 6 }" :model="formState">
        <a-form-item label="邮箱" required>
          <a-input v-model:value="formState.email" />
        </a-form-item>
        <a-form-item label="姓名">
          <a-input v-model:value="formState.full_name" />
        </a-form-item>
        <a-form-item label="部门">
          <a-select
            v-model:value="formState.department_id"
            allow-clear
            :options="departments.map((department) => ({
              label: department.name,
              value: department.id,
            }))"
          />
        </a-form-item>
        <a-form-item label="角色">
          <a-select
            v-model:value="formState.role_ids"
            mode="multiple"
            :options="roles.map((role) => ({
              label: role.name,
              value: role.id,
            }))"
          />
        </a-form-item>
        <a-form-item :label="editingUser ? '新密码' : '初始密码'" :required="!editingUser">
          <a-input-password v-model:value="formState.password" />
        </a-form-item>
        <a-form-item label="启用">
          <a-switch v-model:checked="formState.is_active" />
        </a-form-item>
        <a-form-item label="超级管理员">
          <a-switch v-model:checked="formState.is_superuser" />
        </a-form-item>
      </a-form>
    </a-modal>
  </div>
</template>
