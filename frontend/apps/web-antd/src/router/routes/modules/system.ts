import type { RouteRecordRaw } from 'vue-router';

const routes: RouteRecordRaw[] = [
  {
    meta: {
      icon: 'lucide:settings',
      order: 10,
      title: '系统管理',
    },
    name: 'System',
    path: '/system',
    children: [
      {
        component: () => import('#/views/system/users/index.vue'),
        meta: {
          authority: ['system:user:list'],
          icon: 'lucide:users',
          title: '用户管理',
        },
        name: 'SystemUsers',
        path: 'users',
      },
      {
        component: () => import('#/views/system/roles/index.vue'),
        meta: {
          authority: ['system:role:list'],
          icon: 'lucide:shield-check',
          title: '角色管理',
        },
        name: 'SystemRoles',
        path: 'roles',
      },
      {
        component: () => import('#/views/system/menus/index.vue'),
        meta: {
          authority: ['system:menu:list'],
          icon: 'lucide:menu',
          title: '菜单管理',
        },
        name: 'SystemMenus',
        path: 'menus',
      },
      {
        component: () => import('#/views/system/departments/index.vue'),
        meta: {
          authority: ['system:department:list'],
          icon: 'lucide:building-2',
          title: '部门管理',
        },
        name: 'SystemDepartments',
        path: 'departments',
      },
      {
        component: () => import('#/views/system/dictionaries/index.vue'),
        meta: {
          authority: ['system:dict:list'],
          icon: 'lucide:book-open',
          title: '字典管理',
        },
        name: 'SystemDictionaries',
        path: 'dictionaries',
      },
      {
        component: () => import('#/views/system/settings/index.vue'),
        meta: {
          authority: ['system:setting:list'],
          icon: 'lucide:sliders-horizontal',
          title: '参数配置',
        },
        name: 'SystemSettings',
        path: 'settings',
      },
    ],
  },
];

export default routes;
