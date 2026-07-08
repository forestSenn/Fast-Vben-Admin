<script lang="ts" setup>
import type {
  OnActionClickParams,
  VxeTableGridOptions,
} from '#/adapter/vxe-table';
import type {
  DictionaryItemRecord,
  DictionaryTypeRecord,
} from '#/api';

import { computed, onMounted, ref, watch } from 'vue';

import { Page, useVbenDrawer } from '@vben/common-ui';
import { IconifyIcon, Plus } from '@vben/icons';

import {
  Button,
  Card,
  Dropdown,
  Empty,
  InputSearch,
  Menu,
  message,
  Spin,
  Tag,
} from 'ant-design-vue';

import { useVbenVxeGrid } from '#/adapter/vxe-table';
import {
  deleteDictionaryItemApi,
  deleteDictionaryTypeApi,
  listDictionaryItemsApi,
  listDictionaryTypesApi,
  updateDictionaryItemApi,
} from '#/api';

import { buildKeyword, confirmAction } from '../shared/utils';
import { useItemColumns, useItemGridFormSchema } from './data';
import ItemForm from './modules/item-form.vue';
import TypeForm from './modules/type-form.vue';

const allTypes = ref<DictionaryTypeRecord[]>([]);
const typeSearchValue = ref('');
const typeLoading = ref(false);
const selectedType = ref<DictionaryTypeRecord>();

const filteredTypes = computed(() => {
  const keyword = typeSearchValue.value.trim().toLowerCase();
  if (!keyword) {
    return allTypes.value;
  }
  return allTypes.value.filter(
    (type) =>
      type.name.toLowerCase().includes(keyword) ||
      type.code.toLowerCase().includes(keyword),
  );
});

const itemTableTitle = computed(() => {
  if (!selectedType.value) {
    return '字典项';
  }
  return `字典项 · ${selectedType.value.name}`;
});

const [TypeFormDrawer, typeFormDrawerApi] = useVbenDrawer({
  connectedComponent: TypeForm,
  destroyOnClose: true,
});

const [ItemFormDrawer, itemFormDrawerApi] = useVbenDrawer({
  connectedComponent: ItemForm,
  destroyOnClose: true,
});

async function onItemStatusChange(
  newStatus: boolean,
  row: DictionaryItemRecord,
) {
  try {
    await confirmAction(
      `确认将字典项 ${row.label} 的状态切换为【${newStatus ? '启用' : '禁用'}】吗？`,
      '切换状态',
    );
    await updateDictionaryItemApi(row.id, { is_active: newStatus });
    return true;
  } catch {
    return false;
  }
}

function onItemActionClick({
  code,
  row,
}: OnActionClickParams<DictionaryItemRecord>) {
  switch (code) {
    case 'delete': {
      void onDeleteItem(row);
      break;
    }
    case 'edit': {
      if (!selectedType.value) return;
      itemFormDrawerApi
        .setData({ record: row, typeId: selectedType.value.id })
        .open();
      break;
    }
  }
}

async function onDeleteType(row: DictionaryTypeRecord) {
  try {
    await confirmAction(`确认删除字典类型 ${row.name} 吗？`, '删除字典类型');
  } catch {
    return;
  }

  const hideLoading = message.loading({
    content: `正在删除 ${row.name}`,
    duration: 0,
    key: 'dict_type_delete',
  });
  try {
    await deleteDictionaryTypeApi(row.id);
    if (selectedType.value?.id === row.id) {
      selectedType.value = undefined;
    }
    message.success({
      content: `${row.name} 已删除`,
      key: 'dict_type_delete',
    });
    await loadTypes();
    itemGridApi.query();
  } catch {
    hideLoading();
  }
}

async function onDeleteItem(row: DictionaryItemRecord) {
  const hideLoading = message.loading({
    content: `正在删除 ${row.label}`,
    duration: 0,
    key: 'dict_item_delete',
  });
  try {
    await deleteDictionaryItemApi(row.id);
    message.success({
      content: `${row.label} 已删除`,
      key: 'dict_item_delete',
    });
    onRefreshItems();
  } catch {
    hideLoading();
  }
}

const [ItemGrid, itemGridApi] = useVbenVxeGrid({
  formOptions: {
    schema: useItemGridFormSchema(),
    submitOnChange: true,
  },
  gridOptions: {
    columns: useItemColumns(onItemActionClick, onItemStatusChange),
    height: 'auto',
    keepSource: true,
    proxyConfig: {
      ajax: {
        query: async ({ page }, formValues) => {
          if (!selectedType.value) {
            return { items: [], total: 0 };
          }
          return await listDictionaryItemsApi({
            keyword: buildKeyword(formValues.keyword) || undefined,
            page: page.currentPage,
            page_size: page.pageSize,
            type_id: selectedType.value.id,
          });
        },
      },
    },
    rowConfig: {
      keyField: 'id',
    },
    toolbarConfig: {
      custom: true,
      export: false,
      refresh: true,
      search: true,
      zoom: true,
    },
  } as VxeTableGridOptions<DictionaryItemRecord>,
});

watch(selectedType, () => {
  itemGridApi.query();
});

async function loadTypes() {
  typeLoading.value = true;
  try {
    const result = await listDictionaryTypesApi({
      page: 1,
      page_size: 500,
    });
    allTypes.value = result.items;

    if (selectedType.value) {
      selectedType.value = result.items.find(
        (type) => type.id === selectedType.value?.id,
      );
    }
    if (!selectedType.value && result.items.length > 0) {
      selectedType.value = result.items[0];
    }
  } finally {
    typeLoading.value = false;
  }
}

function selectType(type: DictionaryTypeRecord) {
  selectedType.value = type;
}

function onTypeMenuClick(
  type: DictionaryTypeRecord,
  info: { key: number | string | symbol },
) {
  switch (info.key) {
    case 'delete': {
      void onDeleteType(type);
      break;
    }
    case 'edit': {
      typeFormDrawerApi.setData(type).open();
      break;
    }
  }
}

function onRefreshTypes() {
  void loadTypes();
}

function onRefreshItems() {
  itemGridApi.query();
}

function onCreateType() {
  typeFormDrawerApi.setData(undefined).open();
}

function onCreateItem() {
  if (!selectedType.value) {
    message.warning('请先选择字典类型');
    return;
  }
  itemFormDrawerApi.setData({ typeId: selectedType.value.id }).open();
}

onMounted(loadTypes);
</script>

<template>
  <Page auto-content-height>
    <TypeFormDrawer @success="onRefreshTypes" />
    <ItemFormDrawer @success="onRefreshItems" />
    <div class="flex size-full">
      <Card class="flex w-1/6 min-w-[260px] flex-col">
        <div class="mb-3 flex items-center justify-between">
          <span class="font-medium">字典类型</span>
          <Button size="small" type="primary" @click="onCreateType">
            <Plus class="size-4" />
          </Button>
        </div>
        <InputSearch
          v-model:value="typeSearchValue"
          allow-clear
          class="mb-3"
          placeholder="搜索字典类型"
        />
        <Spin :spinning="typeLoading">
          <div class="max-h-[calc(100vh-280px)] overflow-y-auto">
            <Empty
              v-if="!filteredTypes.length"
              :image="Empty.PRESENTED_IMAGE_SIMPLE"
              description="暂无字典类型"
            />
            <div
              v-for="type in filteredTypes"
              :key="type.id"
              class="group mb-1 flex items-center justify-between rounded-md px-2 py-2 text-sm transition-colors"
              :class="
                selectedType?.id === type.id
                  ? 'bg-accent'
                  : 'hover:bg-accent/50'
              "
            >
              <div
                class="min-w-0 flex-1 cursor-pointer"
                @click="selectType(type)"
              >
                <div class="flex items-center gap-2">
                  <span class="truncate font-medium">{{ type.name }}</span>
                  <Tag v-if="!type.is_active" color="default">禁用</Tag>
                </div>
                <div class="truncate text-xs text-muted-foreground">
                  {{ type.code }}
                </div>
              </div>
              <Dropdown placement="bottomRight" :trigger="['click']">
                <Button
                  class="shrink-0"
                  :class="
                    selectedType?.id === type.id
                      ? 'opacity-100'
                      : 'opacity-0 group-hover:opacity-100'
                  "
                  size="small"
                  type="text"
                >
                  <IconifyIcon
                    class="size-4"
                    icon="lucide:ellipsis-vertical"
                  />
                </Button>
                <template #overlay>
                  <Menu @click="(info) => onTypeMenuClick(type, info)">
                    <Menu.Item key="edit">编辑</Menu.Item>
                    <Menu.Item key="delete" danger>删除</Menu.Item>
                  </Menu>
                </template>
              </Dropdown>
            </div>
          </div>
        </Spin>
      </Card>

      <div class="ml-4 w-5/6 min-w-0">
        <ItemGrid :table-title="itemTableTitle">
          <template #toolbar-tools>
            <Button
              :disabled="!selectedType"
              type="primary"
              @click="onCreateItem"
            >
              <Plus class="size-5" />
              新增字典项
            </Button>
          </template>
          <template #color="{ row }">
            <div v-if="row.color" class="flex items-center justify-center gap-2">
              <span
                class="inline-block size-4 shrink-0 rounded-full border"
                :style="{ backgroundColor: row.color }"
              />
              <span class="truncate">{{ row.color }}</span>
            </div>
            <span v-else class="text-muted-foreground">-</span>
          </template>
        </ItemGrid>
      </div>
    </div>
  </Page>
</template>
