# RBAC 权限模型

## 核心表

- `role`：角色。
- `menu`：目录、菜单、按钮和权限码。
- `department`：部门组织。
- `userrole`：用户和角色关系。
- `rolemenu`：角色和菜单/权限关系。

`User.is_superuser` 仍保留，超级管理员绕过权限码校验。

## 菜单类型

- `directory`：目录。
- `menu`：可访问页面。
- `button`：按钮或操作权限，不显示在菜单中。

## 常用权限码

- `system:user:list/create/update/delete`
- `system:role:list/create/update/delete`
- `system:menu:list/create/update/delete`
- `system:department:list/create/update/delete`
- `system:dict:list/create/update/delete`
- `system:setting:list/update`
- `system:login-log:list`
- `system:operation-log:list`
- `system:file:list/upload/delete`
- `system:notice:list/create/update/delete`
- `business:item:list/create/update/delete`
- `personal:message:list`

## 前端菜单

前端默认使用后端菜单模式。登录后请求 `/menus/me`，并把后端菜单转换成 Vben 动态路由。
