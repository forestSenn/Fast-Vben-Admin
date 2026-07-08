import type { RouteRecordRaw } from 'vue-router';

const routes: RouteRecordRaw[] = [
  {
    component: () => import('#/views/items/index.vue'),
    meta: {
      authority: ['business:item:list'],
      icon: 'lucide:package',
      order: 20,
      title: '示例资源',
    },
    name: 'Items',
    path: '/items',
  },
];

export default routes;
