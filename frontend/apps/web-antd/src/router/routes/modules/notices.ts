import type { RouteRecordRaw } from 'vue-router';

const routes: RouteRecordRaw[] = [
  {
    component: () => import('#/views/notices/index.vue'),
    meta: {
      authority: ['system:notice:list'],
      icon: 'lucide:megaphone',
      order: 26,
      title: '通知公告',
    },
    name: 'Notices',
    path: '/notices',
  },
  {
    component: () => import('#/views/messages/index.vue'),
    meta: {
      authority: ['personal:message:list'],
      icon: 'lucide:mail',
      order: 27,
      title: '我的消息',
    },
    name: 'Messages',
    path: '/messages',
  },
];

export default routes;
