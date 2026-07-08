<script setup lang="ts">
import type { DashboardSummary } from '#/api';

import { computed, onMounted, ref } from 'vue';
import { useRouter } from 'vue-router';

import { getDashboardSummaryApi } from '#/api';

import {
  Button as AButton,
  Card as ACard,
  Descriptions as ADescriptions,
  DescriptionsItem as ADescriptionsItem,
  Space as ASpace,
  Spin as ASpin,
  Tag as ATag,
  message,
} from 'ant-design-vue';

const router = useRouter();
const loading = ref(false);
const summary = ref<DashboardSummary | null>(null);

const stats = computed(() => [
  {
    label: 'API 状态',
    value: summary.value?.apiHealthy ? '正常' : '异常',
  },
  {
    label: '示例资源',
    value: summary.value?.itemTotal ?? '-',
  },
  {
    label: '用户总数',
    value: summary.value?.userTotal ?? (summary.value?.isSuperuser ? '-' : '无权限'),
  },
  {
    label: '当前角色',
    value: summary.value?.isSuperuser ? '超级管理员' : '普通用户',
  },
]);

async function loadSummary() {
  loading.value = true;
  try {
    summary.value = await getDashboardSummaryApi();
  } catch {
    message.error('仪表盘数据加载失败');
  } finally {
    loading.value = false;
  }
}

function go(path: string) {
  void router.push(path);
}

onMounted(loadSummary);
</script>

<template>
  <div class="p-4">
    <div class="mb-4 flex flex-wrap items-center justify-between gap-3">
      <div>
        <h1 class="text-xl font-semibold">仪表盘</h1>
        <p class="text-muted-foreground mt-1 text-sm">
          {{ summary?.currentUserName || '正在加载...' }}
        </p>
      </div>
      <a-space>
        <a-tag :color="summary?.apiHealthy ? 'green' : 'red'">
          {{ summary?.apiHealthy ? '服务正常' : '服务未知' }}
        </a-tag>
        <a-button :loading="loading" @click="loadSummary">刷新</a-button>
      </a-space>
    </div>

    <a-spin :spinning="loading">
      <div class="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <a-card v-for="item in stats" :key="item.label" :bordered="false">
          <div class="text-muted-foreground text-sm">{{ item.label }}</div>
          <div class="mt-3 text-2xl font-semibold">{{ item.value }}</div>
        </a-card>
      </div>

      <div class="mt-4 grid gap-4 lg:grid-cols-3">
        <a-card :bordered="false" title="快捷入口">
          <a-space wrap>
            <a-button type="primary" @click="go('/items')">示例资源</a-button>
            <a-button v-if="summary?.isSuperuser" @click="go('/system/users')">
              用户管理
            </a-button>
            <a-button @click="go('/profile')">个人设置</a-button>
          </a-space>
        </a-card>

        <a-card :bordered="false" title="当前账号">
          <a-descriptions :column="1" size="small">
            <a-descriptions-item label="邮箱">
              {{ summary?.currentUserEmail || '-' }}
            </a-descriptions-item>
            <a-descriptions-item label="权限">
              {{ summary?.isSuperuser ? '可管理用户和资源' : '可管理自己的资源' }}
            </a-descriptions-item>
          </a-descriptions>
        </a-card>

        <a-card :bordered="false" title="接口契约">
          <a-descriptions :column="1" size="small">
            <a-descriptions-item label="API 前缀">/api/v1</a-descriptions-item>
            <a-descriptions-item label="OpenAPI">
              /api/v1/openapi.json
            </a-descriptions-item>
          </a-descriptions>
        </a-card>
      </div>
    </a-spin>
  </div>
</template>
