<script lang="ts" setup>
import type { TenantMembershipRecord } from '#/api';

import { computed, onBeforeUnmount, onMounted, ref } from 'vue';

import { ChevronDown, IconifyIcon } from '@vben/icons';

import { Button, Dropdown, Menu, Tag, message } from 'ant-design-vue';

import { listMyTenantsApi, TENANT_MEMBERSHIPS_CHANGED_EVENT } from '#/api';
import { $t } from '#/locales';
import { useAuthStore } from '#/store';

const authStore = useAuthStore();
const memberships = ref<TenantMembershipRecord[]>([]);
const switchingTenantId = ref<string>();

const currentMembership = computed(
  () =>
    memberships.value.find((membership) => membership.is_current) ||
    memberships.value.find((membership) => membership.is_default) ||
    memberships.value[0],
);

async function fetchMemberships() {
  try {
    memberships.value = await listMyTenantsApi();
  } catch {
    memberships.value = [];
  }
}

async function handleMenuClick(info: { key: number | string }) {
  const tenantId = String(info.key);
  const membership = memberships.value.find(
    (item) => item.tenant.id === tenantId,
  );
  if (!membership?.is_active || membership.is_current) return;

  switchingTenantId.value = tenantId;
  const hideLoading = message.loading({
    content: `${$t('system.tenant.switch')}...`,
    duration: 0,
    key: 'tenant_switch',
  });
  try {
    await authStore.switchTenant(tenantId);
  } catch {
    hideLoading();
    switchingTenantId.value = undefined;
  }
}

onMounted(() => {
  void fetchMemberships();
  window.addEventListener(TENANT_MEMBERSHIPS_CHANGED_EVENT, fetchMemberships);
});

onBeforeUnmount(() => {
  window.removeEventListener(
    TENANT_MEMBERSHIPS_CHANGED_EVENT,
    fetchMemberships,
  );
});
</script>

<template>
  <Dropdown
    v-if="currentMembership"
    placement="bottomRight"
    :trigger="['click']"
  >
    <Button
      class="tenant-trigger mx-1 flex h-9 max-w-52 items-center gap-2 px-2"
      type="text"
      :aria-label="$t('system.tenant.switch')"
      :title="$t('system.tenant.switch')"
    >
      <IconifyIcon class="size-4 shrink-0" icon="lucide:building-2" />
      <span class="tenant-name min-w-0 truncate text-sm font-medium">
        {{ currentMembership.tenant.name }}
      </span>
      <ChevronDown class="tenant-chevron size-3.5 shrink-0" />
    </Button>
    <template #overlay>
      <Menu
        class="min-w-56"
        :selected-keys="[currentMembership.tenant.id]"
        @click="handleMenuClick"
      >
        <Menu.Item
          v-for="membership in memberships"
          :key="membership.tenant.id"
          :disabled="
            !membership.is_active || membership.tenant.id === switchingTenantId
          "
        >
          <div class="flex min-w-0 items-center justify-between gap-3">
            <div class="min-w-0">
              <div class="truncate">{{ membership.tenant.name }}</div>
              <div class="truncate text-xs text-muted-foreground">
                {{ membership.tenant.code }}
              </div>
            </div>
            <Tag v-if="!membership.is_active" class="mr-0" color="default">
              {{ $t('common.disabled') }}
            </Tag>
          </div>
        </Menu.Item>
      </Menu>
    </template>
  </Dropdown>
</template>

<style scoped>
@media (max-width: 639px) {
  .tenant-name,
  .tenant-chevron {
    display: none;
  }

  .tenant-trigger {
    width: 2.25rem;
    padding-right: 0.5rem;
    padding-left: 0.5rem;
  }
}
</style>
