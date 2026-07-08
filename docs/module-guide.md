# 新增业务模块指南

以 Items 为范例，一个完整模块应包含：

- SQLModel 数据模型。
- Alembic 迁移。
- CRUD/API 路由。
- 权限码和初始化菜单。
- 前端 API 封装。
- 前端列表、查询、新增、编辑、删除页面。
- 测试和文档。

## 后端

1. 在 `models.py` 定义 `XxxBase`、`XxxCreate`、`XxxUpdate`、`Xxx`、`XxxPublic`、`XxxsPublic`。
2. 新建 `api/routes/xxx.py`。
3. 在 `api/main.py` include router。
4. 在 `core/db.py` seed 菜单和按钮权限。
5. 增加测试。

## 前端

1. 在 `src/api/core/xxx.ts` 封装接口。
2. 在 `src/views/xxx/index.vue` 实现页面。
3. 如果使用前端静态路由，在 `src/router/routes/modules` 增加路由；后端菜单模式下，确保后端菜单 `component` 指向页面。
4. 运行 `pnpm generate:api`、`typecheck`、`build`。
