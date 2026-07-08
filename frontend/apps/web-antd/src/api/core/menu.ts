import type { RouteRecordStringComponent } from '@vben/types';

import { getMyMenusApi } from './rbac';

interface BackendMenuRoute {
  component?: null | string;
  icon?: null | string;
  id?: string;
  name?: string;
  parent_id?: null | string;
  path?: string;
  permission_code?: null | string;
  route_name?: null | string;
  route_path?: null | string;
  sort?: number;
  title: string;
  type?: string;
}

function normalizeComponent(component?: null | string) {
  return component?.replace(/^#/, '');
}

function toRoute(menu: BackendMenuRoute): RouteRecordStringComponent {
  return {
    children: [],
    component:
      normalizeComponent(menu.component) ||
      (menu.type === 'directory' ? 'BasicLayout' : ''),
    meta: {
      authority: menu.permission_code ? [menu.permission_code] : undefined,
      icon: menu.icon || undefined,
      order: menu.sort,
      title: menu.title,
    },
    name: menu.route_name || menu.name || menu.id,
    path: menu.route_path || menu.path || '/',
  };
}

/**
 * 获取用户所有菜单
 */
export async function getAllMenusApi() {
  const menus = (await getMyMenusApi()) as unknown as BackendMenuRoute[];
  const routeById = new Map<string, RouteRecordStringComponent>();
  const roots: RouteRecordStringComponent[] = [];

  for (const menu of menus.filter((item) => item.type !== 'button')) {
    if (!menu.id) continue;
    routeById.set(menu.id, toRoute(menu));
  }

  for (const menu of menus.filter((item) => item.type !== 'button')) {
    if (!menu.id) continue;
    const route = routeById.get(menu.id);
    if (!route) continue;
    if (menu.parent_id && routeById.has(menu.parent_id)) {
      const parent = routeById.get(menu.parent_id);
      parent?.children?.push(route);
    } else {
      roots.push(route);
    }
  }

  return roots;
}
