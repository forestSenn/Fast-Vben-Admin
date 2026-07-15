import type {
  DepartmentCreate,
  DepartmentPublic,
  DepartmentsPublic,
  DepartmentUpdate,
  MenuCreate,
  MenuPublic,
  MenusPublic,
  MenuUpdate,
  PostCreate,
  PostPublic,
  PostsPublic,
  PostUpdate,
  RoleCreate,
  RoleMenuUpdate,
  RolePublic,
  RolesPublic,
  RoleUpdate,
  UserPostUpdate,
  UserRoleUpdate,
} from '#/api/generated';

import { requestClient } from '#/api/request';

export type RoleRecord = RolePublic;
export type RoleListResult = RolesPublic;
export type RoleCreatePayload = RoleCreate;
export type RoleUpdatePayload = RoleUpdate;

export type MenuRecord = MenuPublic;
export type MenuListResult = MenusPublic;
export type MenuCreatePayload = MenuCreate;
export type MenuUpdatePayload = MenuUpdate;

export type DepartmentRecord = DepartmentPublic;
export type DepartmentListResult = DepartmentsPublic;
export type DepartmentCreatePayload = DepartmentCreate;
export type DepartmentUpdatePayload = DepartmentUpdate;

export type PostRecord = PostPublic;
export type PostListResult = PostsPublic;
export type PostCreatePayload = PostCreate;
export type PostUpdatePayload = PostUpdate;

export interface ListParams {
  is_active?: boolean;
  keyword?: string;
  page?: number;
  page_size?: number;
}

export function listRolesApi(params: ListParams = {}) {
  return requestClient.get<RoleListResult>('/roles', { params });
}

export function createRoleApi(data: RoleCreatePayload) {
  return requestClient.post<RoleRecord>('/roles', data);
}

export function updateRoleApi(roleId: string, data: RoleUpdatePayload) {
  return requestClient.request<RoleRecord>(`/roles/${roleId}`, {
    data,
    method: 'PATCH',
  });
}

export function deleteRoleApi(roleId: string) {
  return requestClient.delete(`/roles/${roleId}`);
}

export function getRoleMenusApi(roleId: string) {
  return requestClient.get<string[]>(`/roles/${roleId}/menus`);
}

export function updateRoleMenusApi(roleId: string, data: RoleMenuUpdate) {
  return requestClient.request<string[]>(`/roles/${roleId}/menus`, {
    data,
    method: 'PUT',
  });
}

export function listMenusApi(params: ListParams = {}) {
  return requestClient.get<MenuListResult>('/menus', { params });
}

export function getMyMenusApi() {
  return requestClient.get<MenuRecord[]>('/menus/me');
}

export function getMyPermissionsApi() {
  return requestClient.get<string[]>('/permissions/me');
}

export function createMenuApi(data: MenuCreatePayload) {
  return requestClient.post<MenuRecord>('/menus', data);
}

export function updateMenuApi(menuId: string, data: MenuUpdatePayload) {
  return requestClient.request<MenuRecord>(`/menus/${menuId}`, {
    data,
    method: 'PATCH',
  });
}

export function deleteMenuApi(menuId: string) {
  return requestClient.delete(`/menus/${menuId}`);
}

export function listDepartmentsApi(params: ListParams = {}) {
  return requestClient.get<DepartmentListResult>('/departments', { params });
}

export function createDepartmentApi(data: DepartmentCreatePayload) {
  return requestClient.post<DepartmentRecord>('/departments', data);
}

export function updateDepartmentApi(
  departmentId: string,
  data: DepartmentUpdatePayload,
) {
  return requestClient.request<DepartmentRecord>(
    `/departments/${departmentId}`,
    {
      data,
      method: 'PATCH',
    },
  );
}

export function deleteDepartmentApi(departmentId: string) {
  return requestClient.delete(`/departments/${departmentId}`);
}

export function listPostsApi(params: ListParams = {}) {
  return requestClient.get<PostListResult>('/posts', { params });
}

export function createPostApi(data: PostCreatePayload) {
  return requestClient.post<PostRecord>('/posts', data);
}

export function updatePostApi(postId: string, data: PostUpdatePayload) {
  return requestClient.request<PostRecord>(`/posts/${postId}`, {
    data,
    method: 'PATCH',
  });
}

export function deletePostApi(postId: string) {
  return requestClient.delete(`/posts/${postId}`);
}

export function getUserRolesApi(userId: string) {
  return requestClient.get<RoleRecord[]>(`/users/${userId}/roles`);
}

export function updateUserRolesApi(userId: string, data: UserRoleUpdate) {
  return requestClient.request<string[]>(`/users/${userId}/roles`, {
    data,
    method: 'PUT',
  });
}

export function getUserPostsApi(userId: string) {
  return requestClient.get<PostRecord[]>(`/users/${userId}/posts`);
}

export function updateUserPostsApi(userId: string, data: UserPostUpdate) {
  return requestClient.request<string[]>(`/users/${userId}/posts`, {
    data,
    method: 'PUT',
  });
}
