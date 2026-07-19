# 新增业务模块指南

业务模块的边界、模块契约、产品发行版和部署组合见[模块化产品架构规划](./modular-product-architecture.md)，公开接口与依赖规则见 [ADR-0009](./adr/0009-module-public-contracts-and-dependency-boundaries.md)。本指南描述目标模块结构；现有集中式代码可以渐进迁移，但新业务模块不得继续扩大 `app.models`、`app.api.routes` 和集中式菜单种子。

以 Items 为范例，一个完整模块应包含：

- SQLModel 数据模型。
- Alembic 迁移。
- CRUD/API 路由。
- 权限码和初始化菜单。
- 前端 API 封装。
- 前端列表、查询、新增、编辑、删除页面。
- 测试和文档。

## 后端

目标目录如下：

```text
backend/app/modules/<module_code>/
  module.py
  public_api/
    queries.py
    commands.py
    dto.py
    events.py
  domain/
  application/
    ports.py
    services/
  infrastructure/
    models.py
    repositories.py
  routes/
  permissions.py
  menus.py
  migrations/
```

1. 在 `module.py` 声明模块版本、必选依赖、可选能力、Router、权限、菜单、迁移、事件和生命周期组件。
2. ORM 模型、Repository 和外部系统适配器放在模块自己的 `infrastructure`，不能加入全局 `app.models`。
3. FastAPI Router 放在模块自己的 `routes`，并通过平台稳定 Web 集成面使用 `require_module_access("<module>", "<permission>")`。
4. 跨模块需要调用的查询、命令、DTO 和事件放入 `public_api`；纯模块内部接口不要放入公开目录。
5. 对平台用户、租户、组织和权限的读取依赖平台公开端口，不直接查询平台表。
6. 对其他业务模块的必选依赖只能导入其 `public_api`，并在模块声明中登记。
7. 对审批等可选能力只依赖稳定能力契约，由组合根选择 Provider；禁止直接导入可选模块实现。
8. 增加单元测试、公开契约测试、接口测试和 edition 独立启动测试。

在模块注册器和菜单声明完全落地前，允许在组合根增加一次显式注册，但业务实现不能放回中央文件。该兼容步骤必须带有迁移 TODO，不能成为长期接入方式。

## 公开接口设计

公开接口应围绕调用方用例设计，例如批量解析用户摘要、发起审批或检查业务引用，不提供跨模块通用 ORM CRUD。

- 输入输出只使用 Pydantic DTO、不可变 dataclass、枚举和标准类型。
- 不公开 ORM 实体、数据库 Session、FastAPI 请求对象、内部异常和第三方 SDK 对象。
- 查询接口不得允许调用方拼接提供方数据库过滤条件。
- 命令接口定义幂等键、超时和稳定错误码。
- 破坏性契约变更创建新主版本；旧版本按发布策略保留迁移周期。
- 公开接口测试使用替身实现时，不应要求初始化提供方 Router 或数据库表。

## 跨模块事件

改变其他模块业务状态的事件必须通过事务 Outbox 发布，事件 Schema 放在发布方 `public_api.events`。事件至少包含 `event_id`、`event_type`、`event_version`、`tenant_id`、`aggregate_id`、`occurred_at` 和追踪标识。

消费者必须：

- 只依赖事件 DTO，不依赖发布方 Outbox ORM 模型。
- 按 `event_id` 幂等处理。
- 接受同一主版本内新增可选字段。
- 对失败执行重试、死信和可观测处理。

## 前端

目标目录如下：

```text
frontend/apps/web-antd/src/modules/<module_code>/
  module.ts
  api/
    generated/
    index.ts
  views/
  components/
  locales/
```

1. 在 `module.ts` 注册组件映射、国际化资源、初始化逻辑和可选工作台部件。
2. 页面、模块私有组件和 API 包装保存在模块目录内，不加入平台 `views` 或 `api/core`。
3. 只导入本模块生成客户端和平台公开客户端，禁止导入其他可选业务模块客户端。
4. 后端菜单的 `component` 必须指向当前 edition 注册的组件；构建时校验映射存在。
5. 给新增、编辑、删除、导入导出等操作加 `v-access:code` 或表格 `auth`，但仍以后端访问检查为安全边界。
6. 按 ADR-0008 生成模块子契约和组合契约，再运行类型检查及生产构建。

现有集中式页面可以渐进迁移；新模块不得继续写入全局业务页面和全局生成客户端目录。

## 代码生成器

系统管理中的代码生成器可根据现有 PostgreSQL 表下载起始代码。当前 ZIP 包含：

- `backend/schemas.py`：Schema 起始定义。
- `backend/routes.py`：带权限码的 CRUD 路由骨架。
- `frontend/api/*.ts`：前端 API 封装。
- `frontend/views/*/index.vue`：Vben 列表页。

这些是兼容旧结构的起始文件，不是模块目标目录。生成器不会直接注册模型或路由；合并前必须把后端代码迁入模块的 `domain/application/infrastructure/routes`，把前端代码迁入 `src/modules/<module_code>`，并复核字段类型、主键策略、关联关系、数据权限和业务校验。后续代码生成器应直接输出目标模块结构。

## 发布前检查

新增模块进入发布前，至少确认：

- 后端路由使用 `require_module_access("<module>", "<permission>")`。
- 模块通过自己的定义注册 Router、菜单、权限、迁移和生命周期组件。
- 模块没有导入其他模块的内部包、ORM 模型、Service 或 Repository。
- `public_api` 没有反向导入 `domain`、`application`、`infrastructure` 或 `routes`。
- Manifest 依赖声明与静态导入结果一致。
- 可选 Provider 缺失时，模块独立启动和降级测试通过。
- 跨模块事件具有版本化 Schema、幂等消费和重试测试。
- 前端页面没有绕过权限展示危险操作入口。
- 对应模块 OpenAPI 客户端已生成，组合契约没有命名冲突。
- `uv run pytest` 和 `pnpm frontend:build` 通过。
