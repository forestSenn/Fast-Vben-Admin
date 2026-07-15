<script lang="ts" setup>
import type { MenuRecord, RoleRecord } from '#/api';

import { computed, ref } from 'vue';

import { useVbenDrawer } from '@vben/common-ui';

import { Tree as ATree } from 'ant-design-vue';

import { getRoleMenusApi, listMenusApi, updateRoleMenusApi } from '#/api';

interface MenuTreeNode {
  children: MenuTreeNode[];
  key: string;
  title: string;
}

const emits = defineEmits<{ success: [] }>();

const permissionRole = ref<RoleRecord>();
const checkedMenuIds = ref<string[]>([]);
const menus = ref<MenuRecord[]>([]);
const loading = ref(false);

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
      .toSorted((a, b) => (a.sort ?? 0) - (b.sort ?? 0))
      .map((menu) => ({
        children: build(menu.id),
        key: menu.id,
        title: `${menu.title}${menu.permission_code ? ` (${menu.permission_code})` : ''}`,
      }));
  }

  return build(null);
});

const [Drawer, drawerApi] = useVbenDrawer({
  async onConfirm() {
    if (!permissionRole.value) return;

    drawerApi.lock();
    try {
      await updateRoleMenusApi(permissionRole.value.id, {
        menu_ids: checkedMenuIds.value,
      });
      emits('success');
      drawerApi.close();
    } catch {
      drawerApi.unlock();
    }
  },
  async onOpenChange(isOpen) {
    if (!isOpen) return;

    permissionRole.value = drawerApi.getData<RoleRecord>();
    checkedMenuIds.value = [];
    loading.value = true;
    try {
      const [menuResult, roleMenuIds] = await Promise.all([
        listMenusApi({ page: 1, page_size: 500 }),
        permissionRole.value
          ? getRoleMenusApi(permissionRole.value.id)
          : Promise.resolve([]),
      ]);
      menus.value = menuResult.items;
      checkedMenuIds.value = roleMenuIds;
    } finally {
      loading.value = false;
    }
  },
});

const drawerTitle = computed(
  () =>
    `分配权限${permissionRole.value ? ` - ${permissionRole.value.name}` : ''}`,
);
</script>

<template>
  <Drawer :loading="loading" :title="drawerTitle" class="w-[640px]">
    <a-tree
      v-model:checked-keys="checkedMenuIds"
      checkable
      :default-expand-all="true"
      :tree-data="menuTreeData"
    />
  </Drawer>
</template>
