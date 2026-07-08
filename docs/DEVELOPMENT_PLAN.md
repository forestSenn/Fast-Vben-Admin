# Fast Vben Admin 开箱即用版开发计划

## 1. 计划目标

本文档基于 [PRD](./PRD.md) 拆解，用于指导 Fast Vben Admin 从“基础全栈模板”升级为“开箱即用后台系统基座”。

目标不是堆功能，而是优先补齐多数中后台项目都会重复建设的通用能力：

- RBAC 角色权限。
- 动态菜单。
- 部门组织。
- 字典管理。
- 系统参数。
- 登录日志和操作日志。
- 文件上传和附件管理。
- 通知公告和站内消息。
- 数据导入导出。
- 完整开发、部署和扩展文档。

## 2. 当前状态

更新时间：2026-07-07

已具备：

- 后端 FastAPI、SQLModel、PostgreSQL、Alembic 基础结构。
- JWT 登录、当前用户、修改密码、忘记密码和重置密码。
- 用户管理基础 CRUD。
- Item 示例 CRUD。
- 仪表盘基础真实数据。
- OpenAPI 类型生成。
- 前端 Vben `web-antd` 应用接入真实 API。
- Docker Compose 和初始化脚本基础。
- 后端测试、前端构建、E2E 基础流程。

主要缺口：

- 用户仍只有 `is_superuser`，缺少通用 RBAC。
- 前端菜单仍未完整后端动态化。
- 缺少部门、字典、系统参数。
- 缺少登录日志、操作日志。
- 缺少文件上传和文件管理。
- 缺少通知公告、站内消息。
- 缺少导入导出。
- 文档仍需按开箱即用版本补齐。

## 3. 开发原则

### 3.1 先系统基建，再高级能力

v1.0 只做通用后台基建，不做低代码、工作流、多租户、OAuth2、多数据库适配。

### 3.2 前端必须沿用 Vben 风格

所有新增页面必须参考 `参考项目/vue-vben-admin` 的样式风格、页面结构、组件用法和代码组织方式。

要求：

- 默认应用仍以 `frontend/apps/web-antd` 为主。
- 页面布局沿用 Vben 主布局、菜单、顶部栏、标签页、主题和暗色模式。
- 列表页沿用 Vben 风格的查询区、工具栏、表格、分页和操作列。
- 新增 / 编辑优先使用 Vben 体系已有 Modal、Drawer、Form、Table、Descriptions、Tag、Switch、Dropdown 等组件组合。
- 路由、store、api、views、locales 的组织方式参考 Vben 现有结构。
- 不新增一套割裂的 UI 组件风格。
- 可以参考 Vben 页面写法，但页面数据必须来自真实 API，不保留无关 Mock。

### 3.3 后端权限是最终边界

前端菜单和按钮隐藏只做体验优化。所有管理接口必须在后端校验权限。

### 3.4 每个模块必须闭环

一个模块完成需要同时具备：

- 数据模型和迁移。
- CRUD / Service。
- API 路由。
- 权限码。
- 前端 API 类型。
- 前端页面。
- 菜单配置。
- 测试。
- 文档。

### 3.5 小步交付

每个里程碑都应保持系统可启动、可登录、核心测试可跑。不要一次性改完所有模型再补页面。

## 4. 目标版本拆分

| 里程碑 | 目标 | 建议版本 | 优先级 |
| --- | --- | --- | --- |
| M0 | 基线稳定和技术准备 | v0.5.0 | P0 |
| M1 | RBAC、菜单、部门 | v0.6.0 | P0 |
| M2 | 字典和系统参数 | v0.7.0 | P1 |
| M3 | 日志审计 | v0.8.0 | P1 |
| M4 | 文件上传和附件管理 | v0.9.0 | P1 |
| M5 | 通知、导入导出、Items 增强 | v0.10.0 | P1 |
| M6 | 文档、CI、发布打磨 | v1.0.0 | P0 |

## 5. M0 基线稳定和技术准备

### 5.1 目标

在新增复杂系统模块前，先确保当前基础闭环稳定，避免后续排查问题时混在一起。

### 5.2 后端任务

| 编号 | 任务 | 涉及文件 / 模块 | 验收标准 |
| --- | --- | --- | --- |
| M0-BE-01 | 跑通现有后端测试 | `backend/tests` | `uv run pytest` 通过 |
| M0-BE-02 | 确认统一错误响应 | `backend/app/main.py`、异常处理 | 401/403/422/500 返回 `code/message/details` |
| M0-BE-03 | 确认统一分页响应 | `UserPublic`、`ItemsPublic` 等 | 列表接口返回 `items/total/page/page_size` |
| M0-BE-04 | 梳理 CRUD 模块化策略 | `backend/app/crud.py` | 明确后续是否拆为 `crud/*.py` 或 `services/*.py` |
| M0-BE-05 | 确认 OpenAPI schema | `/api/v1/openapi.json` | schema 可访问，前端可生成类型 |

### 5.3 前端任务

| 编号 | 任务 | 涉及文件 / 模块 | 验收标准 |
| --- | --- | --- | --- |
| M0-FE-01 | 跑通现有 typecheck/build | `frontend/apps/web-antd` | typecheck 和 build 通过 |
| M0-FE-02 | 确认请求封装 | `src/api` | token、401、403、错误提示统一 |
| M0-FE-03 | 确认路由和菜单结构 | `src/router/routes` | 当前菜单清晰，无无关演示入口 |
| M0-FE-04 | 建立新增页面范式 | 用户管理、Items 页面 | 选定列表页、表单页、详情页写法作为参考 |

### 5.4 工程任务

| 编号 | 任务 | 验收标准 |
| --- | --- |
| M0-ENG-01 | 验证 Docker Compose | `docker compose up --build` 可启动 |
| M0-ENG-02 | 验证 `pnpm generate:api` | 生成代码无类型错误 |
| M0-ENG-03 | 更新 README 当前状态 | README 与实际命令一致 |

## 6. M1 RBAC、菜单、部门

### 6.1 目标

把当前 `is_superuser` 权限模型升级为通用 RBAC，并提供动态菜单和部门组织能力。

### 6.2 数据模型

新增模型：

- `Role`
- `Menu`
- `Department`
- `UserRole`
- `RoleMenu`

建议字段：

```text
Role
  id
  code
  name
  description
  sort
  is_active
  is_system
  created_at
  updated_at

Menu
  id
  parent_id
  type              # directory/menu/button
  title
  route_path
  route_name
  component
  icon
  permission_code
  sort
  is_visible
  is_keep_alive
  is_active
  created_at
  updated_at

Department
  id
  parent_id
  name
  code
  leader_user_id
  sort
  is_active
  created_at
  updated_at

UserRole
  user_id
  role_id

RoleMenu
  role_id
  menu_id
```

修改模型：

- `User` 增加 `department_id`。
- 保留 `is_superuser` 作为超级管理员快速判断和兼容字段。

### 6.3 后端 API

#### 角色 API

| 方法 | 路径 | 权限 | 说明 |
| --- | --- | --- | --- |
| GET | `/api/v1/roles` | `system:role:list` | 角色列表 |
| POST | `/api/v1/roles` | `system:role:create` | 创建角色 |
| GET | `/api/v1/roles/{role_id}` | `system:role:list` | 角色详情 |
| PATCH | `/api/v1/roles/{role_id}` | `system:role:update` | 更新角色 |
| DELETE | `/api/v1/roles/{role_id}` | `system:role:delete` | 删除角色 |
| GET | `/api/v1/roles/{role_id}/menus` | `system:role:list` | 获取角色菜单 |
| PUT | `/api/v1/roles/{role_id}/menus` | `system:role:update` | 分配角色菜单 |

#### 菜单 API

| 方法 | 路径 | 权限 | 说明 |
| --- | --- | --- | --- |
| GET | `/api/v1/menus` | `system:menu:list` | 菜单树 |
| POST | `/api/v1/menus` | `system:menu:create` | 创建菜单 |
| PATCH | `/api/v1/menus/{menu_id}` | `system:menu:update` | 更新菜单 |
| DELETE | `/api/v1/menus/{menu_id}` | `system:menu:delete` | 删除菜单 |
| GET | `/api/v1/menus/me` | 登录用户 | 当前用户菜单树 |
| GET | `/api/v1/permissions/me` | 登录用户 | 当前用户权限码 |

#### 部门 API

| 方法 | 路径 | 权限 | 说明 |
| --- | --- | --- | --- |
| GET | `/api/v1/departments` | `system:department:list` | 部门树 |
| POST | `/api/v1/departments` | `system:department:create` | 创建部门 |
| PATCH | `/api/v1/departments/{department_id}` | `system:department:update` | 更新部门 |
| DELETE | `/api/v1/departments/{department_id}` | `system:department:delete` | 删除部门 |

#### 用户 API 调整

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| PATCH | `/api/v1/users/{user_id}` | 支持 `department_id` |
| PUT | `/api/v1/users/{user_id}/roles` | 分配用户角色 |
| GET | `/api/v1/users/{user_id}/roles` | 获取用户角色 |

### 6.4 后端任务

| 编号 | 任务 | 依赖 | 验收标准 |
| --- | --- | --- | --- |
| M1-BE-01 | 新增 RBAC 数据模型 | M0 | Alembic 迁移可从空库执行 |
| M1-BE-02 | 初始化内置菜单和角色 | M1-BE-01 | 默认管理员拥有全部权限 |
| M1-BE-03 | 增加权限依赖 `require_permission` | M1-BE-02 | 无权限返回 403 |
| M1-BE-04 | 实现角色 CRUD | M1-BE-03 | API 和测试通过 |
| M1-BE-05 | 实现菜单 CRUD 和 `/menus/me` | M1-BE-03 | 前端可获取菜单树 |
| M1-BE-06 | 实现部门 CRUD | M1-BE-01 | 支持树结构和删除校验 |
| M1-BE-07 | 用户绑定部门和角色 | M1-BE-04 | 用户详情返回角色和部门信息 |
| M1-BE-08 | 改造用户管理权限 | M1-BE-03 | 普通用户无法访问管理接口 |
| M1-BE-09 | 补后端测试 | M1-BE-04 至 08 | RBAC、菜单、部门、用户角色测试通过 |

### 6.5 前端页面

新增页面：

- `/system/roles`
- `/system/menus`
- `/system/departments`

改造页面：

- `/system/users`
- 主菜单渲染。
- 路由守卫和权限 store。

### 6.6 前端任务

| 编号 | 任务 | 依赖 | 验收标准 |
| --- | --- | --- | --- |
| M1-FE-01 | 生成最新 API 类型 | M1-BE API | `pnpm generate:api` 通过 |
| M1-FE-02 | 新增权限 store | M1-BE-05 | 保存菜单树和权限码 |
| M1-FE-03 | 改造菜单加载 | M1-FE-02 | 登录后菜单来自 `/menus/me` |
| M1-FE-04 | 改造按钮权限指令或工具 | M1-FE-02 | 操作按钮可按权限隐藏 |
| M1-FE-05 | 角色管理页 | M1-BE-04 | 列表、新增、编辑、删除、分配菜单 |
| M1-FE-06 | 菜单管理页 | M1-BE-05 | 菜单树、新增、编辑、删除 |
| M1-FE-07 | 部门管理页 | M1-BE-06 | 部门树、新增、编辑、删除 |
| M1-FE-08 | 用户管理页增强 | M1-BE-07 | 可分配部门和角色 |
| M1-FE-09 | 普通用户权限验证 | M1-FE-03 | 普通用户看不到系统管理 |

### 6.7 测试

后端：

- 创建角色。
- 删除系统角色被拒绝。
- 给角色分配菜单。
- 普通用户访问无权限接口返回 403。
- 部门树创建、更新、删除。
- 删除存在子部门或用户的部门被拒绝。

前端 / E2E：

- 管理员创建角色。
- 管理员给角色分配菜单。
- 创建普通用户并分配角色。
- 普通用户登录后只看到授权菜单。

### 6.8 M1 验收

- RBAC 表结构和迁移完成。
- 默认管理员拥有全部权限。
- 角色、菜单、部门页面可用。
- 用户可绑定部门和角色。
- 菜单和按钮按权限展示。
- 后端接口权限校验生效。

## 7. M2 字典和系统参数

### 7.1 目标

减少业务页面硬编码，让状态、类型、开关、系统名称等可配置。

### 7.2 数据模型

```text
DictionaryType
  id
  code
  name
  description
  is_active
  created_at
  updated_at

DictionaryItem
  id
  type_id
  label
  value
  color
  sort
  is_active
  extra
  created_at
  updated_at

SystemSetting
  id
  key
  name
  value
  value_type        # string/number/boolean/json
  group
  description
  is_public
  is_system
  created_at
  updated_at
```

### 7.3 API

| 方法 | 路径 | 权限 | 说明 |
| --- | --- | --- | --- |
| GET | `/api/v1/dictionary-types` | `system:dict:list` | 字典类型列表 |
| POST | `/api/v1/dictionary-types` | `system:dict:create` | 创建字典类型 |
| PATCH | `/api/v1/dictionary-types/{id}` | `system:dict:update` | 更新字典类型 |
| DELETE | `/api/v1/dictionary-types/{id}` | `system:dict:delete` | 删除字典类型 |
| GET | `/api/v1/dictionaries/{code}/items` | 登录用户 | 获取字典项 |
| POST | `/api/v1/dictionary-items` | `system:dict:create` | 创建字典项 |
| PATCH | `/api/v1/dictionary-items/{id}` | `system:dict:update` | 更新字典项 |
| DELETE | `/api/v1/dictionary-items/{id}` | `system:dict:delete` | 删除字典项 |
| GET | `/api/v1/settings` | `system:setting:list` | 参数列表 |
| PATCH | `/api/v1/settings/{key}` | `system:setting:update` | 更新参数 |
| GET | `/api/v1/settings/public` | 公开或登录用户 | 公共参数 |

### 7.4 后端任务

| 编号 | 任务 | 验收标准 |
| --- | --- |
| M2-BE-01 | 新增字典模型和迁移 | 空库迁移通过 |
| M2-BE-02 | 新增系统参数模型和迁移 | 空库迁移通过 |
| M2-BE-03 | 初始化内置字典 | 用户状态、是否、业务状态可用 |
| M2-BE-04 | 初始化内置参数 | 系统名称、分页大小、上传大小等可用 |
| M2-BE-05 | 实现字典 API | CRUD 和按 code 获取通过 |
| M2-BE-06 | 实现参数 API | 管理端和公共读取通过 |
| M2-BE-07 | 加缓存和刷新策略 | 修改后可刷新缓存 |
| M2-BE-08 | 补测试 | 字典、参数测试通过 |

### 7.5 前端任务

| 编号 | 任务 | 验收标准 |
| --- | --- |
| M2-FE-01 | 新增字典管理页 | 类型和字典项可维护 |
| M2-FE-02 | 新增参数配置页 | 参数可查看和编辑 |
| M2-FE-03 | 新增字典读取工具 | 表单下拉和 Tag 可复用 |
| M2-FE-04 | 用户状态改用字典 | 不再硬编码状态文案 |
| M2-FE-05 | Items 状态字段可选增强 | 示例业务体现字典用法 |

### 7.6 M2 验收

- 字典和参数页面符合 Vben 风格。
- 系统内置字典和参数初始化成功。
- 页面可以从字典读取选项。
- 参数修改后能被后端或前端读取。

## 8. M3 日志审计

### 8.1 目标

满足生产后台最基础的安全审计需求。

### 8.2 数据模型

```text
LoginLog
  id
  user_id
  email
  ip
  user_agent
  status          # success/fail
  failure_reason
  created_at

OperationLog
  id
  user_id
  module
  action
  method
  path
  status_code
  duration_ms
  ip
  user_agent
  request_summary
  response_summary
  created_at
```

### 8.3 API

| 方法 | 路径 | 权限 | 说明 |
| --- | --- | --- | --- |
| GET | `/api/v1/logs/login` | `system:login-log:list` | 登录日志列表 |
| GET | `/api/v1/logs/login/{id}` | `system:login-log:list` | 登录日志详情 |
| DELETE | `/api/v1/logs/login` | `system:login-log:delete` 可后续 | 清理日志 |
| GET | `/api/v1/logs/operation` | `system:operation-log:list` | 操作日志列表 |
| GET | `/api/v1/logs/operation/{id}` | `system:operation-log:list` | 操作日志详情 |

### 8.4 后端任务

| 编号 | 任务 | 验收标准 |
| --- | --- |
| M3-BE-01 | 新增日志模型和迁移 | 迁移通过 |
| M3-BE-02 | 登录成功/失败写登录日志 | 登录流程有记录 |
| M3-BE-03 | 新增操作日志中间件或装饰器 | 关键接口有记录 |
| M3-BE-04 | 敏感字段脱敏 | 密码、token 不入库 |
| M3-BE-05 | 日志查询 API | 支持分页、搜索、筛选 |
| M3-BE-06 | 补日志测试 | 登录日志和操作日志测试通过 |

### 8.5 前端任务

| 编号 | 任务 | 验收标准 |
| --- | --- |
| M3-FE-01 | 登录日志页面 | 分页、筛选、详情 |
| M3-FE-02 | 操作日志页面 | 分页、筛选、详情 |
| M3-FE-03 | 日志详情弹窗或抽屉 | 展示请求摘要和上下文 |
| M3-FE-04 | 菜单和权限接入 | 只有授权用户可见 |

### 8.6 M3 验收

- 登录成功和失败都有记录。
- 用户、角色、菜单等关键操作有操作日志。
- 日志页面可筛选和查看详情。
- 敏感信息不入库、不展示。

## 9. M4 文件上传和附件管理

### 9.1 目标

提供头像、附件、图片等高频文件能力，并为后续对象存储预留扩展。

### 9.2 数据模型

```text
FileAsset
  id
  original_name
  stored_name
  content_type
  extension
  size
  sha256
  storage_provider   # local/s3/minio/oss
  storage_path
  public_url
  uploader_id
  is_public
  created_at
```

### 9.3 API

| 方法 | 路径 | 权限 | 说明 |
| --- | --- | --- | --- |
| POST | `/api/v1/files/upload` | `system:file:upload` 或登录用户 | 上传文件 |
| GET | `/api/v1/files` | `system:file:list` | 文件列表 |
| GET | `/api/v1/files/{file_id}` | 登录用户 | 文件详情 |
| GET | `/api/v1/files/{file_id}/download` | 登录用户 | 下载文件 |
| DELETE | `/api/v1/files/{file_id}` | `system:file:delete` | 删除文件 |
| POST | `/api/v1/users/me/avatar` | 登录用户 | 上传头像 |

### 9.4 后端任务

| 编号 | 任务 | 验收标准 |
| --- | --- |
| M4-BE-01 | 新增 FileAsset 模型和迁移 | 迁移通过 |
| M4-BE-02 | 实现 storage provider 抽象 | 默认 local，可扩展 S3/MinIO |
| M4-BE-03 | 实现上传 API | 支持大小、后缀、MIME 校验 |
| M4-BE-04 | 实现下载和访问 API | 权限校验清晰 |
| M4-BE-05 | 实现文件管理 API | 列表、详情、删除 |
| M4-BE-06 | 实现头像上传 | 当前用户头像可更新 |
| M4-BE-07 | 补测试 | 上传、非法类型、删除测试通过 |

### 9.5 前端任务

| 编号 | 任务 | 验收标准 |
| --- | --- |
| M4-FE-01 | 封装文件上传 API | 页面可复用 |
| M4-FE-02 | 文件管理页 | 列表、预览、下载、删除 |
| M4-FE-03 | 个人中心头像上传 | 上传后头像刷新 |
| M4-FE-04 | Items 附件增强 | 示例业务可关联附件 |

### 9.6 M4 验收

- 文件上传可用。
- 非法文件被拒绝。
- 文件管理页面可查看和删除文件。
- 用户头像可上传。
- 本地存储路径和生产配置有文档说明。

## 10. M5 通知、导入导出、Items 增强

### 10.1 目标

补齐后台常见运营能力，并让 Items 成为完整业务模块范例。

### 10.2 通知公告模型

```text
Notice
  id
  title
  content
  type
  priority
  status          # draft/published/withdrawn
  published_at
  created_by
  created_at
  updated_at

Message
  id
  user_id
  title
  content
  type
  is_read
  read_at
  created_at
```

### 10.3 通知公告 API

| 方法 | 路径 | 权限 | 说明 |
| --- | --- | --- | --- |
| GET | `/api/v1/notices` | `system:notice:list` | 公告管理列表 |
| POST | `/api/v1/notices` | `system:notice:create` | 创建公告 |
| PATCH | `/api/v1/notices/{id}` | `system:notice:update` | 更新公告 |
| POST | `/api/v1/notices/{id}/publish` | `system:notice:update` | 发布公告 |
| POST | `/api/v1/notices/{id}/withdraw` | `system:notice:update` | 撤回公告 |
| DELETE | `/api/v1/notices/{id}` | `system:notice:delete` | 删除公告 |
| GET | `/api/v1/notices/current` | 登录用户 | 当前有效公告 |
| GET | `/api/v1/messages/me` | 登录用户 | 我的消息 |
| POST | `/api/v1/messages/{id}/read` | 登录用户 | 标记已读 |

### 10.4 导入导出 API

| 方法 | 路径 | 权限 | 说明 |
| --- | --- | --- | --- |
| GET | `/api/v1/users/export` | `system:user:list` | 导出用户 |
| GET | `/api/v1/items/export` | `business:item:list` | 导出 Items |
| GET | `/api/v1/items/import-template` | `business:item:create` | 下载导入模板 |
| POST | `/api/v1/items/import` | `business:item:create` | 导入 Items |

### 10.5 后端任务

| 编号 | 任务 | 验收标准 |
| --- | --- |
| M5-BE-01 | 新增 Notice 和 Message 模型 | 迁移通过 |
| M5-BE-02 | 实现公告 CRUD、发布、撤回 | API 测试通过 |
| M5-BE-03 | 实现我的消息 | 可读、可标记已读 |
| M5-BE-04 | 实现 CSV/XLSX 导出基础工具 | 用户和 Items 可导出 |
| M5-BE-05 | 实现 Items 导入模板和导入 | 失败行有错误原因 |
| M5-BE-06 | 增强 Items 模型 | 可选增加状态、附件 |
| M5-BE-07 | 补测试 | 通知、导入导出测试通过 |

### 10.6 前端任务

| 编号 | 任务 | 验收标准 |
| --- | --- |
| M5-FE-01 | 通知公告管理页 | 列表、新增、编辑、发布、撤回 |
| M5-FE-02 | 用户端公告展示 | 登录后可查看有效公告 |
| M5-FE-03 | 站内消息入口 | 未读数、列表、标记已读 |
| M5-FE-04 | 用户导出按钮 | 下载文件成功 |
| M5-FE-05 | Items 导入导出 | 模板下载、上传、结果反馈 |
| M5-FE-06 | Items 完整示例增强 | 权限、字典、附件、日志、导入导出均体现 |

### 10.7 M5 验收

- 公告可发布并展示。
- 消息可查看和标记已读。
- 用户和 Items 可导出。
- Items 可按模板导入。
- Items 成为新增业务模块的完整参考。

## 11. M6 文档、CI、发布打磨

### 11.1 目标

达到公开发布质量，让陌生用户可以启动、理解、部署和二次开发。

### 11.2 文档任务

| 编号 | 文档 | 内容 | 验收标准 |
| --- | --- | --- | --- |
| M6-DOC-01 | README | 项目介绍、截图、快速开始、默认账号、命令、功能清单 | 新用户可按 README 启动 |
| M6-DOC-02 | `docs/development.md` | 本地开发、目录说明、新增模块、迁移、测试 | 开发者可新增模块 |
| M6-DOC-03 | `docs/deployment.md` | Docker Compose、环境变量、HTTPS、生产安全 | 可按文档部署 |
| M6-DOC-04 | `docs/api-contract.md` | 响应、错误、分页、权限码 | 前后端协作清晰 |
| M6-DOC-05 | `docs/rbac.md` | 角色、菜单、权限码设计 | 权限模型可理解 |
| M6-DOC-06 | `docs/module-guide.md` | 按 Items 新增业务模块 | 能复制范式 |
| M6-DOC-07 | `docs/faq.md` | Docker、端口、数据库、邮件、登录问题 | 常见问题可自查 |

### 11.3 CI 任务

| 编号 | 任务 | 验收标准 |
| --- | --- |
| M6-CI-01 | 后端 workflow | lint、测试通过 |
| M6-CI-02 | 前端 workflow | typecheck、lint、build 通过 |
| M6-CI-03 | Docker Compose workflow | 服务启动和健康检查通过 |
| M6-CI-04 | E2E workflow | 登录、RBAC、Items 核心流程通过 |
| M6-CI-05 | OpenAPI 生成检查 | schema 变化不会破坏前端类型 |

### 11.4 开源配置

| 编号 | 任务 | 验收标准 |
| --- | --- |
| M6-OSS-01 | Issue 模板 | Bug、Feature、Question |
| M6-OSS-02 | PR 模板 | 包含测试、文档、截图检查 |
| M6-OSS-03 | CHANGELOG | v1.0.0 内容完整 |
| M6-OSS-04 | SECURITY.md | 安全报告方式 |
| M6-OSS-05 | License 和致谢 | 说明参考项目和许可证 |

### 11.5 M6 验收

- 新用户按 README 可启动完整系统。
- Docker Compose 可启动。
- 后端测试通过。
- 前端构建通过。
- E2E 核心流程通过。
- 文档完整。
- 发布清单通过。

## 12. 推荐实际开发顺序

实际编码建议按这个顺序推进：

1. M0 基线检查和 Docker 验证。
2. 新增 Role / Menu / Department 模型和迁移。
3. 初始化内置角色、菜单、权限码。
4. 实现 `require_permission` 后端依赖。
5. 实现角色、菜单、部门 API。
6. 生成前端 API 类型。
7. 实现权限 store 和 `/menus/me` 菜单加载。
8. 实现角色、菜单、部门页面。
9. 增强用户管理，支持部门和角色。
10. 补 RBAC E2E。
11. 做字典和参数。
12. 做登录日志和操作日志。
13. 做文件上传。
14. 做通知公告。
15. 做导入导出和 Items 增强。
16. 补文档和 CI。
17. 发布 v1.0.0。

## 13. Issue 拆分建议

### Epic 1: Baseline

- 验证 Docker Compose。
- 跑通后端测试。
- 跑通前端构建。
- 整理现有 API 契约。

### Epic 2: RBAC

- 新增角色模型。
- 新增菜单模型。
- 新增部门模型。
- 初始化内置权限。
- 后端权限依赖。
- 角色管理页面。
- 菜单管理页面。
- 部门管理页面。
- 用户角色分配。

### Epic 3: System Config

- 字典类型和字典项。
- 字典管理页面。
- 系统参数模型。
- 参数配置页面。
- 前端字典工具。

### Epic 4: Audit

- 登录日志模型和写入。
- 操作日志模型和写入。
- 日志查询 API。
- 登录日志页面。
- 操作日志页面。

### Epic 5: Files

- FileAsset 模型。
- Local storage provider。
- 上传、下载、删除 API。
- 文件管理页面。
- 头像上传。
- Items 附件。

### Epic 6: Notice And Import Export

- 通知公告模型。
- 公告管理页面。
- 站内消息。
- CSV/XLSX 导出。
- Items 导入。
- Items 完整范例。

### Epic 7: Release

- README。
- 开发文档。
- 部署文档。
- API 契约文档。
- RBAC 文档。
- CI。
- 发布清单。

## 14. Definition of Done

单个功能完成必须满足：

- 后端模型、迁移、API 完成。
- 后端权限校验完成。
- 前端页面符合 Vben 风格。
- 前端页面具备 loading、empty、error 状态。
- 前端使用真实 API，不使用无关 Mock。
- API 类型已重新生成。
- 后端测试已覆盖关键逻辑。
- 需要 E2E 的流程已覆盖或记录原因。
- 文档同步更新。

单个里程碑完成必须满足：

- 系统可启动。
- 默认管理员可登录。
- 本里程碑页面可用。
- 普通用户无权限访问被拦截。
- 后端测试通过。
- 前端构建通过。
- 关键 E2E 通过。
- README 或 docs 说明新增能力。

## 15. 发布前总检查清单

### 功能

- 登录、退出、当前用户可用。
- 用户管理可用。
- 角色管理可用。
- 菜单管理可用。
- 部门管理可用。
- 字典管理可用。
- 参数配置可用。
- 登录日志可用。
- 操作日志可用。
- 文件上传可用。
- 通知公告可用。
- 导入导出可用。
- Items 示例完整。

### 权限

- 超级管理员拥有全部权限。
- 普通用户只能访问授权菜单。
- 普通用户直接请求无权限接口返回 403。
- 按钮权限生效。
- 系统内置角色和菜单有保护。

### 工程

- `docker compose up --build` 可启动。
- `uv run pytest` 通过。
- 前端 typecheck 通过。
- 前端 build 通过。
- E2E 通过。
- `pnpm generate:api` 通过。
- `.env.example` 完整。
- 真实 `.env` 未提交。
- 默认密钥生产保护生效。

### 文档

- README 可指导新用户启动。
- 开发文档可指导新增业务模块。
- 部署文档覆盖生产安全变量。
- API 契约文档和实现一致。
- RBAC 文档解释权限模型。
- CHANGELOG 完整。

## 16. 总结

这份计划的主线是：先把当前基础闭环稳住，再补齐后台系统最常见的通用基建。实现时要坚持两件事：

- 后端能力必须真实、可测试、可部署。
- 前端页面必须像 Vben Admin 原生页面一样自然。

最终 v1.0 的交付物应该是一套用户能直接二次开发的 FastAPI + Vue Vben Admin 全栈后台基座，而不是一个只能演示登录和 CRUD 的简单模板。
