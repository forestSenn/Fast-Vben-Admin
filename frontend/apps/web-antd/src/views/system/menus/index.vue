<script setup lang="ts">
import type { TableColumnsType } from 'ant-design-vue';

import type { MenuRecord } from '#/api';

import { computed, onMounted, reactive, ref } from 'vue';

import { createMenuApi, deleteMenuApi, listMenusApi, updateMenuApi } from '#/api';

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
  Switch as ASwitch,
  Table as ATable,
  Tag as ATag,
  message,
} from 'ant-design-vue';

const loading = ref(false);
const modalOpen = ref(false);
const saving = ref(false);
const editingMenu = ref<null | MenuRecord>(null);
const menus = ref<MenuRecord[]>([]);

const query = reactive({
  keyword: '',
  page: 1,
  pageSize: 200,
  total: 0,
});

interface MenuFormState {
  component?: string;
  icon?: string;
  is_active: boolean;
  is_keep_alive: boolean;
  is_visible: boolean;
  parent_id?: string;
  permission_code?: string;
  route_name?: string;
  route_path?: string;
  sort: number;
  title: string;
  type: string;
}

const formState = reactive<MenuFormState>({
  component: '',
  icon: '',
  is_active: true,
  is_keep_alive: false,
  is_visible: true,
  parent_id: undefined,
  permission_code: '',
  route_name: '',
  route_path: '',
  sort: 0,
  title: '',
  type: 'menu',
});

const columns: TableColumnsType<MenuRecord> = [
  { dataIndex: 'title', title: '菜单名称' },
  { dataIndex: 'type', title: '类型', width: 100 },
  { dataIndex: 'route_path', title: '路由' },
  { dataIndex: 'permission_code', title: '权限码' },
  { dataIndex: 'is_visible', title: '显示', width: 100 },
  { dataIndex: 'is_active', title: '状态', width: 100 },
  { dataIndex: 'sort', title: '排序', width: 90 },
  { dataIndex: 'actions', fixed: 'right', title: '操作', width: 160 },
];

const parentOptions = computed(() =>
  menus.value
    .filter((menu) => menu.id !== editingMenu.value?.id && menu.type !== 'button')
    .map((menu) => ({
      label: `${menu.title}${menu.route_path ? ` (${menu.route_path})` : ''}`,
      value: menu.id,
    })),
);

function resetForm() {
  formState.component = '';
  formState.icon = '';
  formState.is_active = true;
  formState.is_keep_alive = false;
  formState.is_visible = true;
  formState.parent_id = undefined;
  formState.permission_code = '';
  formState.route_name = '';
  formState.route_path = '';
  formState.sort = 0;
  formState.title = '';
  formState.type = 'menu';
}

async function loadMenus() {
  loading.value = true;
  try {
    const result = await listMenusApi({
      keyword: query.keyword || undefined,
      page: query.page,
      page_size: query.pageSize,
    });
    menus.value = result.items;
    query.total = result.total;
  } finally {
    loading.value = false;
  }
}

function openCreate() {
  editingMenu.value = null;
  resetForm();
  modalOpen.value = true;
}

function openEdit(menu: MenuRecord) {
  editingMenu.value = menu;
  formState.component = menu.component || '';
  formState.icon = menu.icon || '';
  formState.is_active = !!menu.is_active;
  formState.is_keep_alive = !!menu.is_keep_alive;
  formState.is_visible = !!menu.is_visible;
  formState.parent_id = menu.parent_id || undefined;
  formState.permission_code = menu.permission_code || '';
  formState.route_name = menu.route_name || '';
  formState.route_path = menu.route_path || '';
  formState.sort = menu.sort ?? 0;
  formState.title = menu.title;
  formState.type = menu.type || 'menu';
  modalOpen.value = true;
}

async function saveMenu() {
  if (!formState.title || !formState.type) {
    message.warning('请输入菜单名称和类型');
    return;
  }

  saving.value = true;
  try {
    const payload = {
      ...formState,
      component: formState.component || undefined,
      icon: formState.icon || undefined,
      parent_id: formState.parent_id || undefined,
      permission_code: formState.permission_code || undefined,
      route_name: formState.route_name || undefined,
      route_path: formState.route_path || undefined,
    };
    if (editingMenu.value) {
      await updateMenuApi(editingMenu.value.id, payload);
      message.success('菜单已更新');
    } else {
      await createMenuApi(payload);
      message.success('菜单已创建');
    }
    modalOpen.value = false;
    await loadMenus();
  } finally {
    saving.value = false;
  }
}

function confirmDelete(menu: MenuRecord) {
  AModal.confirm({
    content: `确认删除菜单 ${menu.title}？`,
    okText: '删除',
    okType: 'danger',
    title: '删除菜单',
    async onOk() {
      await deleteMenuApi(menu.id);
      message.success('菜单已删除');
      await loadMenus();
    },
  });
}

function asMenuRecord(record: Record<string, any>) {
  return record as MenuRecord;
}

function handleTableChange(pagination: { current?: number; pageSize?: number }) {
  query.page = pagination.current || 1;
  query.pageSize = pagination.pageSize || 200;
  void loadMenus();
}

function search() {
  query.page = 1;
  void loadMenus();
}

onMounted(loadMenus);
</script>

<template>
  <div class="p-4">
    <div class="mb-4 flex flex-wrap items-center gap-3">
      <a-input-search
        v-model:value="query.keyword"
        allow-clear
        class="max-w-80"
        placeholder="搜索菜单、路由或权限码"
        @search="search"
      />
      <a-button type="primary" @click="openCreate">新增菜单</a-button>
      <a-button @click="loadMenus">刷新</a-button>
    </div>

    <a-table
      :columns="columns"
      :data-source="menus"
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
        <template v-if="column.dataIndex === 'type'">
          <a-tag :color="record.type === 'button' ? 'purple' : record.type === 'directory' ? 'blue' : 'green'">
            {{ record.type === 'directory' ? '目录' : record.type === 'button' ? '按钮' : '菜单' }}
          </a-tag>
        </template>
        <template v-else-if="column.dataIndex === 'is_visible'">
          <a-tag :color="record.is_visible ? 'green' : 'default'">
            {{ record.is_visible ? '显示' : '隐藏' }}
          </a-tag>
        </template>
        <template v-else-if="column.dataIndex === 'is_active'">
          <a-tag :color="record.is_active ? 'green' : 'red'">
            {{ record.is_active ? '启用' : '禁用' }}
          </a-tag>
        </template>
        <template v-else-if="column.dataIndex === 'route_path'">
          {{ record.route_path || '-' }}
        </template>
        <template v-else-if="column.dataIndex === 'permission_code'">
          {{ record.permission_code || '-' }}
        </template>
        <template v-else-if="column.dataIndex === 'actions'">
          <a-space>
            <a-button size="small" type="link" @click="openEdit(asMenuRecord(record))">
              编辑
            </a-button>
            <a-button
              danger
              size="small"
              type="link"
              @click="confirmDelete(asMenuRecord(record))"
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
      :title="editingMenu ? '编辑菜单' : '新增菜单'"
      width="720px"
      @ok="saveMenu"
    >
      <a-form :label-col="{ span: 6 }" :model="formState">
        <a-form-item label="菜单名称" required>
          <a-input v-model:value="formState.title" />
        </a-form-item>
        <a-form-item label="类型" required>
          <a-select v-model:value="formState.type">
            <a-select-option value="directory">目录</a-select-option>
            <a-select-option value="menu">菜单</a-select-option>
            <a-select-option value="button">按钮</a-select-option>
          </a-select>
        </a-form-item>
        <a-form-item label="父级菜单">
          <a-select
            v-model:value="formState.parent_id"
            allow-clear
            :options="parentOptions"
            placeholder="不选择则为顶级"
          />
        </a-form-item>
        <a-form-item label="路由路径">
          <a-input v-model:value="formState.route_path" />
        </a-form-item>
        <a-form-item label="路由名称">
          <a-input v-model:value="formState.route_name" />
        </a-form-item>
        <a-form-item label="组件路径">
          <a-input v-model:value="formState.component" />
        </a-form-item>
        <a-form-item label="图标">
          <a-input v-model:value="formState.icon" />
        </a-form-item>
        <a-form-item label="权限码">
          <a-input v-model:value="formState.permission_code" />
        </a-form-item>
        <a-form-item label="排序">
          <a-input-number v-model:value="formState.sort" class="w-full" />
        </a-form-item>
        <a-form-item label="显示">
          <a-switch v-model:checked="formState.is_visible" />
        </a-form-item>
        <a-form-item label="启用">
          <a-switch v-model:checked="formState.is_active" />
        </a-form-item>
        <a-form-item label="缓存">
          <a-switch v-model:checked="formState.is_keep_alive" />
        </a-form-item>
      </a-form>
    </a-modal>
  </div>
</template>
