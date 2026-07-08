import type { RouteRecordRaw } from 'vue-router';

const routes: RouteRecordRaw[] = [
  {
    meta: {
      icon: 'lucide:clipboard-list',
      order: 15,
      title: '日志审计',
    },
    name: 'Logs',
    path: '/logs',
    children: [
      {
        component: () => import('#/views/logs/login/index.vue'),
        meta: {
          authority: ['system:login-log:list'],
          icon: 'lucide:log-in',
          title: '登录日志',
        },
        name: 'LoginLogs',
        path: 'login',
      },
      {
        component: () => import('#/views/logs/operation/index.vue'),
        meta: {
          authority: ['system:operation-log:list'],
          icon: 'lucide:history',
          title: '操作日志',
        },
        name: 'OperationLogs',
        path: 'operation',
      },
    ],
  },
];

export default routes;
