<script lang="ts" setup>
import { computed } from 'vue';

import { AuthPageLayout } from '@vben/layouts';
import { preferences } from '@vben/preferences';

const appName = computed(() => preferences.app.name);
const logo = computed(() => preferences.logo.source);
const logoDark = computed(() => preferences.logo.sourceDark);
const apiDocsUrl = computed(() => {
  const apiUrl = String(import.meta.env.VITE_GLOB_API_URL || '');
  return `${apiUrl.replace(/\/api\/v1\/?$/, '')}/docs`;
});
const sourceUrl = 'https://github.com/forestSenn/Fast-Vben-Admin';
</script>

<template>
  <AuthPageLayout
    :app-name="appName"
    :logo="logo"
    :logo-dark="logoDark"
    :page-description="`${appName} 项目管理系统`"
    page-title="欢迎使用"
  >
    <template #copyright>
      <div class="flex flex-col items-center gap-1">
        <div class="flex items-center justify-center gap-4">
          <a
            class="hover:text-primary"
            :href="apiDocsUrl"
            rel="noopener noreferrer"
            target="_blank"
          >
            接口文档
          </a>
          <a
            class="hover:text-primary"
            :href="sourceUrl"
            rel="noopener noreferrer"
            target="_blank"
          >
            源码
          </a>
        </div>
        <span>Copyright © {{ new Date().getFullYear() }} {{ appName }}</span>
      </div>
    </template>
  </AuthPageLayout>
</template>
