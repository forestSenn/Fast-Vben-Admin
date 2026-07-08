<script setup lang="ts">
import type { TableColumnsType } from 'ant-design-vue';

import type { MenuRecord, RoleRecord } from '#/api';

import { computed, onMounted, reactive, ref } from 'vue';

import {
  createRoleApi,
  deleteRoleApi,
  getRoleMenusApi,
  listMenusApi,
  listRolesApi,
  updateRoleApi,
  updateRoleMenusApi,
} from '#/api';

import {
  Button as AButton,
  Form as AForm,
  FormItem as AFormItem,
  Input as AInput,
  InputSearch as AInputSearch,
  InputNumber as AInputNumber,
  Modal as AModal,
  Space as ASpace,
  Switch as ASwitch,
  Table as ATable,
  Tag as ATag,
  Tree as ATree,
  message,
} from 'ant-design-vue';

const loading = ref(false);
const saving = ref(false);
const modalOpen = ref(false);
const permissionModalOpen = ref(false);
const permissionSaving = ref(false);
const editingRole = ref<null | RoleRecord>(null);
const permissionRole = ref<null | RoleRecord>(null);
const checkedMenuIds = ref<string[]>([]);
const roles = ref<RoleRecord[]>([]);
const menus = ref<MenuRecord[]>([]);

const query = reactive({
  keyword: '',
  page: 1,
  pageSize: 20,
  total: 0,
});

interface RoleFormState {
  code: string;
  description: string;
  is_active: boolean;
  is_system: boolean;
  name: string;
  sort: number;
}

interface MenuTreeNode {
  children: MenuTreeNode[];
  key: string;
  title: string;
}

const formState = reactive<RoleFormState>({
  code: '',
  description: '',
  is_active: true,
  is_system: false,
  name: '',
  sort: 0,
});

const columns: TableColumnsType<RoleRecord> = [
  { dataIndex: 'name', title: '角色名称' },
  { dataIndex: 'code', title: '角色编码' },
  { dataIndex: 'is_active', title: '状态', width: 100 },
  { dataIndex: 'is_system', title: '内置', width: 100 },
  { dataIndex: 'sort', title: '排序', width: 100 },
  { dataIndex: 'updated_at', title: '更新时间' },
  { dataIndex: 'actions', fixed: 'right', title: '操作', width: 220 },
];

const menuTreeData = computed(() => {
  const childrenMap = new Map<null | string, MenuRecord[]>();
  for (const menu of menus.value) {
    const parentId = menu.parent_id ?? null;
    const children = childrenMap.get(parentId) ?? [];
    children.push(menu);
    childrenMap.set(parentId, children);
  }

  function build(parentId: null | string): MenuTreeNode[] {
    return (childrenMap.get(parentId) ?? [])
      .sort((a, b) => (a.sort ?? 0) - (b.sort ?? 0))
      .map((menu) => ({
        children: build(menu.id),
        key: menu.id,
        title: `${menu.title}${menu.permission_code ? ` (${menu.permission_code})` : ''}`,
      }));
  }

  return build(null);
});

function resetForm() {
  formState.code = '';
  formState.description = '';
  formState.is_active = true;
  formState.is_system = false;
  formState.name = '';
  formState.sort = 0;
}

async function loadRoles() {
  loading.value = true;
  try {
    const result = await listRolesApi({
      keyword: query.keyword || undefined,
      page: query.page,
      page_size: query.pageSize,
    });
    roles.value = result.items;
    query.total = result.total;
  } finally {
    loading.value = false;
  }
}

async function loadMenus() {
  const result = await listMenusApi({ page: 1, page_size: 500 });
  menus.value = result.items;
}

function openCreate() {
  editingRole.value = null;
  resetForm();
  modalOpen.value = true;
}

function openEdit(role: RoleRecord) {
  editingRole.value = role;
  formState.code = role.code;
  formState.description = role.description || '';
  formState.is_active = !!role.is_active;
  formState.is_system = !!role.is_system;
  formState.name = role.name;
  formState.sort = role.sort ?? 0;
  modalOpen.value = true;
}

async function saveRole() {
  if (!formState.code || !formState.name) {
    message.warning('请输入角色名称和编码');
    return;
  }

  saving.value = true;
  try {
    if (editingRole.value) {
      await updateRoleApi(editingRole.value.id, { ...formState });
      message.success('角色已更新');
    } else {
      await createRoleApi({ ...formState });
      message.success('角色已创建');
    }
    modalOpen.value = false;
    await loadRoles();
  } finally {
    saving.value = false;
  }
}

async function openPermission(role: RoleRecord) {
  permissionRole.value = role;
  permissionModalOpen.value = true;
  await loadMenus();
  checkedMenuIds.value = await getRoleMenusApi(role.id);
}

async function savePermissions() {
  if (!permissionRole.value) return;

  permissionSaving.value = true;
  try {
    await updateRoleMenusApi(permissionRole.value.id, {
      menu_ids: checkedMenuIds.value,
    });
    message.success('角色权限已保存');
    permissionModalOpen.value = false;
  } finally {
    permissionSaving.value = false;
  }
}

function confirmDelete(role: RoleRecord) {
  AModal.confirm({
    content: `确认删除角色 ${role.name}？`,
    okText: '删除',
    okType: 'danger',
    title: '删除角色',
    async onOk() {
      await deleteRoleApi(role.id);
      message.success('角色已删除');
      await loadRoles();
    },
  });
}

function asRoleRecord(record: Record<string, any>) {
  return record as RoleRecord;
}

function handleTableChange(pagination: { current?: number; pageSize?: number }) {
  query.page = pagination.current || 1;
  query.pageSize = pagination.pageSize || 20;
  void loadRoles();
}

function search() {
  query.page = 1;
  void loadRoles();
}

onMounted(loadRoles);
</script>

<template>
  <div class="p-4">
    <div class="mb-4 flex flex-wrap items-center gap-3">
      <a-input-search
        v-model:value="query.keyword"
        allow-clear
        class="max-w-80"
        placeholder="搜索角色名称或编码"
        @search="search"
      />
      <a-button type="primary" @click="openCreate">新增角色</a-button>
      <a-button @click="loadRoles">刷新</a-button>
    </div>

    <a-table
      :columns="columns"
      :data-source="roles"
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
            <a-button size="small" type="link" @click="openPermission(asRoleRecord(record))">
              权限
            </a-button>
            <a-button size="small" type="link" @click="openEdit(asRoleRecord(record))">
              编辑
            </a-button>
            <a-button
              danger
              :disabled="record.is_system"
              size="small"
              type="link"
              @click="confirmDelete(asRoleRecord(record))"
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
      :title="editingRole ? '编辑角色' : '新增角色'"
      @ok="saveRole"
    >
      <a-form :label-col="{ span: 6 }" :model="formState">
        <a-form-item label="角色名称" required>
          <a-input v-model:value="formState.name" />
        </a-form-item>
        <a-form-item label="角色编码" required>
          <a-input v-model:value="formState.code" :disabled="editingRole?.is_system" />
        </a-form-item>
        <a-form-item label="描述">
          <a-input v-model:value="formState.description" />
        </a-form-item>
        <a-form-item label="排序">
          <a-input-number v-model:value="formState.sort" class="w-full" />
        </a-form-item>
        <a-form-item label="启用">
          <a-switch v-model:checked="formState.is_active" />
        </a-form-item>
        <a-form-item label="内置角色">
          <a-switch v-model:checked="formState.is_system" :disabled="editingRole?.is_system" />
        </a-form-item>
      </a-form>
    </a-modal>

    <a-modal
      v-model:open="permissionModalOpen"
      :confirm-loading="permissionSaving"
      :title="`分配权限${permissionRole ? ` - ${permissionRole.name}` : ''}`"
      width="640px"
      @ok="savePermissions"
    >
      <a-tree
        v-model:checked-keys="checkedMenuIds"
        checkable
        :default-expand-all="true"
        :tree-data="menuTreeData"
      />
    </a-modal>
  </div>
</template>
