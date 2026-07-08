import type { RouteRecordRaw } from 'vue-router';

const routes: RouteRecordRaw[] = [
  {
    component: () => import('#/views/files/index.vue'),
    meta: {
      authority: ['system:file:list'],
      icon: 'lucide:folder',
      order: 25,
      title: '文件管理',
    },
    name: 'Files',
    path: '/files',
  },
];

export default routes;
