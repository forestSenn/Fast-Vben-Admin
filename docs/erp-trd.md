# Fast Vben Admin 轻量进销存 ERP 技术需求文档

## 1. 文档信息

| 项目 | 内容 |
| --- | --- |
| 文档名称 | Fast Vben Admin 轻量进销存 ERP TRD |
| 文档状态 | Draft，目标态设计，不代表 ERP 已实现 |
| 文档版本 | v0.1 |
| 更新日期 | 2026-07-20 |
| 目标版本 | ERP v1.0 |
| 关联 PRD | [轻量进销存 ERP PRD](./erp-prd.md) |
| 架构基线 | [模块化架构实施基线](./modular-architecture-implementation.md)、[模块开发指南](./module-guide.md) |
| 适用读者 | Backend、Frontend、QA、DBA、DevOps、Security Reviewer、Architecture Owner |

### 1.1 事实基线

本文以当前仓库提交 `2da3c929883b35cd296b49da970072c3cb6fdfa7` 为实现基线，沿用现有 FastAPI、SQLModel、PostgreSQL、Alembic、Vue 3、Vben Admin、ModuleDefinition、Build Manifest v2、TenantUnitOfWork、RLS、RBAC 和事务 Outbox。

文中路径、表、接口和命令均为目标态。只有代码、迁移和测试合入并通过后，才能更新为当前事实。

## 2. 技术目标

本 TRD 将 ERP PRD 转换为以下可实现、可验证的技术边界：

1. ERP 作为单一独立业务模块接入，不把商品、库存、单据或财务模型放入 Platform。
2. 采购、销售、库存和核销在一个模块数据库事务内保持强一致。
3. 所有 ERP 表由独立 `erp` schema、Alembic namespace 和强制 RLS 管理。
4. 所有写命令具备租户校验、后端金额重算、幂等和并发冲突保护。
5. 库存余额只能由不可变库存流水驱动，反审核使用冲销记录。
6. 前端只使用 ERP 模块生成客户端，通过 Edition Manifest 装配页面。
7. 实现按库存底座、进销闭环、财务统计三个阶段交付，每阶段都有可执行门禁。

## 3. 固定约束与保守默认

### 3.1 不可变架构约束

- 架构保持模块化单体，不拆 ERP 微服务，不引入运行时微前端。
- ERP 只依赖 `platform`，不依赖 `items`、CRM、BPM 或其他可选业务模块。
- ERP 只导入 `app.platform.public_api`、`app.platform.web_api` 和模块共享契约，不导入 Platform ORM、`app.models`、旧 Router 或其他模块实现。
- 业务入口统一使用 `require_module_access("erp", permission)`。
- HTTP body、query 和普通 header 中不接受 `tenant_id`；租户只来自 `CurrentTenant`。
- 共享数据库测试串行执行。

### 3.2 PRD 待确认项的技术默认

| PRD 待确认项 | v1.0 技术默认 | 可变更点 |
| --- | --- | --- |
| 商品重名 | 名称可重复，非空条码租户内唯一 | 产品确认后增加名称唯一约束需新迁移 |
| 分类挂载 | 商品只能挂启用的末级分类 | 可在 ERP 设置中增加开关 |
| 最低售价 | 低于最低售价直接返回 409 | 越权销售需单独权限与审计设计 |
| 订金 | 仅记录，不自动核销 | 后续通过显式订金核销命令演进 |
| 销售其他金额 | 命名为“其他扣减”，非负且从结算金额扣除 | 产品确认前不允许负数反转语义 |
| 采购退货来源 | 关联采购订单行，最大可退量按已审核入库量计算 | 后续可增加直接关联入库行 |
| 历史业务日期 | 允许历史日期，不允许晚于租户当前自然日 | 结账期能力另行设计 |
| 导出格式 | CSV UTF-8 BOM | Excel 需确认并评估依赖 |
| Edition | 独立 `erp` 组合，并由 `suite` 同时装配 Items 与 ERP | Edition YAML 是唯一事实源 |
| 主数据导入 | Phase C P1，业务单据不导入 | 不阻塞 P0 闭环 |
| 现金退款 | v1.0 只支持退货信用额净额冲减 | 独立退款单另行设计 |

### 3.3 数值与时间默认

- ID：UUID v4。
- 时间：数据库 `timestamptz`，应用使用 `app.core.clock.get_datetime_utc()`。
- 租户时区：ERP 设置默认 `Asia/Shanghai`，使用标准库 `zoneinfo.ZoneInfo` 校验。
- 数量：`numeric(20, 6)`。
- 单价与金额：`numeric(20, 4)`，页面默认显示 2 位。
- 百分比：`numeric(7, 4)`，范围 0 至 100。
- 后端计算：Python `Decimal`，统一 `ROUND_HALF_UP`。
- API 数量、单价、金额和百分比使用十进制字符串，避免 JavaScript IEEE-754 精度损失。

## 4. 总体架构

```text
Vue ERP pages
    │ generated ERP OpenAPI client
    ▼
FastAPI ERP routers
    │ require_module_access + CurrentTenant + data scope
    ▼
ERP application services
    ├── master data services
    ├── document services
    ├── inventory posting service
    ├── settlement service
    └── reconciliation service
    │
    ├── ERP repositories ── ERP TenantUnitOfWork ── PostgreSQL erp schema/RLS
    ├── Platform public ports ── users/files/secrets
    └── Platform Outbox API ── versioned ERP events
```

### 4.1 后端目标目录

```text
backend/app/modules/erp/
  __init__.py
  module.py
  public_api/
    __init__.py
    dto.py
    events.py
    ports.py
  domain/
    enums.py
    errors.py
    values.py
    calculations.py
    invariants.py
  application/
    master_data.py
    purchasing.py
    sales.py
    inventory.py
    settlement.py
    statistics.py
    reconciliation.py
    idempotency.py
  infrastructure/
    models/
      base.py
      control.py
      master_data.py
      stock.py
      purchase.py
      sale.py
      finance.py
    repositories/
      control.py
      master_data.py
      stock.py
      purchase.py
      sale.py
      finance.py
    numbering.py
    sensitive_fields.py
    tenant_uow.py
  routes/
    settings.py
    product.py
    purchase.py
    sale.py
    stock.py
    finance.py
    statistics.py
    reconciliation.py
  migrations/
    env.py
    script.py.mako
    versions/
```

简单校验和值对象放在 `domain`；事务编排放在 `application`；ORM、SQLAlchemy 查询和 PostgreSQL 专用能力放在 `infrastructure`；Router 只处理 HTTP 契约、依赖注入、权限和事务提交。

### 4.2 前端目标目录

```text
frontend/apps/web-antd/src/modules/erp/
  api/
    generated/
    erp.ts
  components/
    document-lines-grid.vue
    document-status-tag.vue
    money-text.vue
    product-select.vue
    warehouse-select.vue
    source-document-select.vue
  composables/
    use-document-command.ts
    use-decimal.ts
    use-erp-dictionaries.ts
  locales/
    zh-CN.json
    en-US.json
  views/
    home/
    product/{product,category,unit}/
    purchase/{supplier,order,in,return}/
    sale/{customer,order,out,return}/
    stock/{warehouse,balance,ledger,in,out,move,check}/
    finance/{account,payment,receipt}/
```

不得在全局 `views`、全局业务 API 或第二套路由注册器中增加 ERP 页面。

## 5. 模块契约与 Edition

### 5.1 ModuleDefinition 目标

```python
definition = ModuleDefinition(
    code="erp",
    version="1.0.0",
    dependencies=("platform",),
    routers=(
        settings_router,
        product_router,
        purchase_router,
        sale_router,
        stock_router,
        finance_router,
        statistics_router,
        reconciliation_router,
    ),
    api_prefix="/api/v1/erp",
    permission_prefix="erp",
    migration=MigrationSpec(
        namespace="erp",
        schema="erp",
        owned_tables=ERP_OWNED_TABLES,
    ),
    reference_guards=(
        ReferenceGuardSpec("user", count_user_references),
        ReferenceGuardSpec("file", count_file_references),
    ),
    event_publishers=ERP_EVENT_CONTRACTS,
    menus=ERP_PERMISSION_CODES,
)
```

该片段是目标契约，不要求在 TRD 阶段修改注册表。实现时必须将 `erp_definition` 显式加入 `app.modules.registry`，不得运行时扫描目录。

### 5.2 Edition 目标

- 新增 `editions/erp.yaml`，内容为 `platform`、`erp`。
- `base` 与 `items` 保持不包含 ERP。
- `editions/suite.yaml` 同时包含 Platform、Items 与 ERP。
- `pnpm build:edition -- --edition erp` 必须生成只包含 Platform 与 ERP 的 Manifest 和前端入口。
- Base/Items 的 OpenAPI、Router、前端 dist、Worker、Schedule 和迁移不得包含 ERP。

### 5.3 Platform 公开端口前置项

当前 `UserDirectory` 协议已经存在，但 ERP 不能导入 Platform 的 `SqlUserDirectory` 实现。Phase A 必须补齐以下稳定端口和 Web DI：

| 端口 | 位置 | 最小职责 |
| --- | --- | --- |
| `UserDirectoryDep` | `app.platform.web_api` | 注入 `app.platform.public_api.users.UserDirectory`，批量查询和校验启用用户 |
| `FileAssetDirectory` | `app.platform.public_api.files` | 校验文件 ID 属于当前租户且调用人可访问，返回不可变文件摘要 |
| `FileAssetDirectoryDep` | `app.platform.web_api` | 注入文件公开端口实现，不返回 FileAsset ORM |
| `SensitiveValueProtector` | `app.platform.public_api.secrets` | 使用现有 `cryptography` 能力加密、解密敏感值，返回稳定错误 |
| `SensitiveValueProtectorDep` | `app.platform.web_api` | 注入加密端口实现，ERP 不直接导入 `app.core.mfa` |
| `has_all_data_scope` | `app.platform.web_api` | 判断当前 Principal 在当前租户是否具有 all data scope，ERP 不查询 Role ORM |
| `EnabledModuleTenantDirectory` | `app.platform.public_api.modules` | 供受控 Schedule 枚举已启用 ERP 的 tenant ID，不接受请求参数伪造租户 |

这些端口只能暴露 DTO/Protocol，不暴露 Session、Request、ORM 或存储 SDK。文件删除前由 ERP `ReferenceGuardSpec` 阻止仍被单据引用的资产被物理删除。

## 6. 领域模型

### 6.1 通用枚举

| 枚举 | 值 |
| --- | --- |
| `MasterDataStatus` | `enabled`、`disabled` |
| `DocumentStatus` | `draft`、`approved` |
| `IntegrityStatus` | `ready`、`degraded` |
| `CommandReceiptStatus` | `processing`、`completed` |
| `DocumentAction` | `created`、`updated`、`deleted`、`approved`、`reversed`、`exported`、`sensitive_viewed` |
| `StockLedgerType` | `other_in`、`other_in_reversal`、`other_out`、`other_out_reversal`、`move_in`、`move_in_reversal`、`move_out`、`move_out_reversal`、`check_gain`、`check_gain_reversal`、`check_loss`、`check_loss_reversal`、`purchase_in`、`purchase_in_reversal`、`purchase_return`、`purchase_return_reversal`、`sale_out`、`sale_out_reversal`、`sale_return`、`sale_return_reversal` |
| `SettlementSourceType` | `purchase_in`、`purchase_return`、`sale_out`、`sale_return` |
| `ReconciliationStatus` | `running`、`passed`、`failed` |

数据库不创建 PostgreSQL native enum，使用 `varchar(32)` 加 CHECK constraint，避免枚举扩展阻塞滚动部署；Python 使用 `StrEnum`。

### 6.2 聚合边界

| 聚合 | 根 | 子实体 | 事务不变量 |
| --- | --- | --- | --- |
| 商品分类 | `ProductCategory` | 无 | 无环、编码唯一、父节点同租户 |
| 商品 | `Product` | 无 | 分类/单位启用、条码唯一、价格范围合法 |
| 仓库 | `Warehouse` | `WarehouseUserGrant` | 默认仓库唯一、授权用户有效 |
| 采购订单 | `PurchaseOrder` | `PurchaseOrderItem` | 至少一行、汇总后端重算、累计量不超限 |
| 采购入库/退货 | 对应单据头 | 对应单据行 | 来源已审核、行数量不超可用量、库存与来源累计原子更新 |
| 销售订单 | `SaleOrder` | `SaleOrderItem` | 至少一行、最低售价、累计量不超限 |
| 销售出库/退货 | 对应单据头 | 对应单据行 | 来源已审核、库存充足、来源累计原子更新 |
| 库存单据 | `StockIn/Out/Move/Check` | 对应行 | 审核状态、余额、流水同事务 |
| 付款/收款 | 对应单据头 | 对应核销行 | 同一往来单位、源单已审核、核销不超额、净额非负 |

跨聚合写入只能由 application service 编排；Repository 不提交事务。

### 6.3 单据状态机

```text
create/update                approve(expected_version)
    ┌─────────┐             ┌──────────┐
    │  draft  │────────────▶│ approved │
    └─────────┘             └──────────┘
         ▲                        │
         └────────────────────────┘
            reverse(expected_version)
```

- 创建状态固定为 `draft`，客户端不能传状态、单号、租户或汇总字段。
- `draft` 可修改或删除；每次修改 `version += 1`。
- 审核执行 `WHERE id=:id AND status='draft' AND version=:expected_version` 条件更新。
- 反审核执行对称条件更新，并先检查下游依赖和可逆库存/核销。
- 审核、反审核成功均增加版本；重复命令不得产生第二次副作用。
- 反审核只恢复为 draft，不删除原库存流水、核销记录或动作日志。

## 7. 数据库设计

### 7.1 表级通用规范

- Schema：`erp`。
- 主键：`id uuid primary key`，映射表可使用复合主键。
- 每张租户表都包含非空 `tenant_id uuid`。
- 被其他 ERP 表引用的实体增加 `UNIQUE (id, tenant_id)`。
- ERP 内部关联使用复合外键 `(foreign_id, tenant_id) -> (id, tenant_id)`，防止同库跨租户关联。
- 所有业务时间使用 `timestamptz`；所有字符串给出显式最大长度。
- 单据、余额、配置使用 `version integer not null default 1 check (version > 0)`。
- 不使用软删除字段掩盖业务状态。未引用主数据和 draft 单据可以物理删除；已审核单据禁止删除。
- 所有表启用并强制 RLS，包括控制表、映射表、流水和审计表。

### 7.2 通用审计列

除只增不改的流水/日志外，可变实体包含：

| 列 | 类型 | 说明 |
| --- | --- | --- |
| `created_at` | `timestamptz` | 服务端 UTC 创建时间 |
| `updated_at` | `timestamptz` | 服务端 UTC 更新时间 |
| `created_by` | `uuid` | Platform 用户稳定 ID，不建跨模块 FK |
| `updated_by` | `uuid` | Platform 用户稳定 ID，不建跨模块 FK |

单据额外包含 `owner_id`、`approved_by/approved_at`、`reversed_by/reversed_at`。`owner_id` 是当前数据权限过滤字段；库存类单据默认等于创建人。

### 7.3 控制与审计表

| 表 | 关键列 | 关键约束 |
| --- | --- | --- |
| `erp_setting` | `tenant_id`、`timezone`、`integrity_status`、`last_reconciled_at`、`version`、审计列 | `tenant_id` 主键；时区由 ZoneInfo 校验；完整性字段由系统维护 |
| `document_sequence` | `tenant_id`、`prefix`、`sequence_date`、`next_value` | 复合主键；`next_value > 0` |
| `command_receipt` | `id`、`tenant_id`、`command_name`、`idempotency_key`、`request_sha256`、`resource_type`、`resource_id`、`resource_version`、`status`、`expires_at` | `UNIQUE (tenant_id, command_name, idempotency_key)` |
| `document_action_log` | `id`、`tenant_id`、`resource_type`、`resource_id`、`resource_no`、`action`、原/新状态、原/新版本、`actor_id`、`reason`、`metadata jsonb`、`occurred_at` | 仅 INSERT/SELECT，不允许 UPDATE/DELETE |
| `document_attachment` | `id`、`tenant_id`、`document_type`、`document_id`、`file_id`、`sort`、`created_by/at` | `UNIQUE (tenant_id, document_type, document_id, file_id)` |
| `reconciliation_run` | `id`、`tenant_id`、`status`、`stock_difference_count`、`settlement_difference_count`、摘要、开始/完成时间、触发人 | 运行中允许更新结果；完成后应用层只读；摘要不得包含敏感数据 |

`document_attachment` 和 `document_action_log` 使用逻辑资源引用，不建立指向多种单据表的多态外键；application service 必须验证资源存在和同租户。

### 7.4 主数据表

| 表 | 业务列 | 约束/索引 |
| --- | --- | --- |
| `product_unit` | `name`、`normalized_name`、`status` | `UNIQUE (tenant_id, normalized_name)` |
| `product_category` | `parent_id`、`name`、`code`、`sort`、`status` | 编码唯一；复合自引用 FK；`parent_id <> id` |
| `product` | `name`、`normalized_name`、`barcode`、`category_id`、`unit_id`、`status`、`standard`、`expiry_days`、`weight`、采购/销售/最低价、`remark` | 非空条码部分唯一；分类/单位复合 FK；非负 CHECK |
| `supplier` | 名称、联系人、手机、电话、邮箱、传真、税号、税率、开户行、`bank_account_encrypted`、`bank_account_last4`、开户地址、排序、状态、备注 | 规范化名称唯一；税率 0..100；银行账号不存明文 |
| `customer` | 与 supplier 对称 | 规范化名称唯一；敏感字段相同保护 |
| `warehouse` | 名称、地址、负责人、仓储费、运输费、排序、状态、`is_default`、备注 | 规范化名称唯一；默认项部分唯一 |
| `warehouse_user_grant` | `tenant_id`、`warehouse_id`、`user_id`、授权人/时间 | 复合主键；仓库复合 FK；用户经 UserDirectory 校验 |
| `settlement_account` | 名称、内部编号、`account_no_encrypted`、`account_no_last4`、排序、状态、`is_default`、备注 | 名称/非空编号唯一；默认项部分唯一 |

部分唯一索引示例：

```sql
CREATE UNIQUE INDEX uq_warehouse_default_per_tenant
ON erp.warehouse (tenant_id)
WHERE is_default IS TRUE;
```

银行账号与结算账号复用 Platform `SensitiveValueProtector`，数据库只保存密文和末四位。列表仅返回脱敏值；具备 `erp:finance-sensitive:read` 时由详情服务按需解密并写 `sensitive_viewed` 审计。

密文带算法版本前缀，例如 `v1:<ciphertext>`；读取端支持当前与上一版本，轮换使用前向数据迁移，downgrade 不解密回明文。

### 7.5 库存余额与流水

#### `stock_balance`

| 列 | 类型 | 说明 |
| --- | --- | --- |
| `id` | uuid | 主键 |
| `tenant_id` | uuid | 租户 |
| `product_id` | uuid | 商品复合 FK |
| `warehouse_id` | uuid | 仓库复合 FK |
| `quantity` | numeric(20,6) | 当前库存，默认不小于 0 |
| `version` | integer | 原子更新版本 |
| `updated_at` | timestamptz | 最近记账时间 |

约束：`UNIQUE (tenant_id, product_id, warehouse_id)`、`CHECK (quantity >= 0)`。不提供通用 Repository update 方法，只暴露 InventoryPostingService 使用的原子增量方法。

#### `stock_ledger`

| 列 | 类型 | 说明 |
| --- | --- | --- |
| `id` | uuid | 流水 ID |
| `tenant_id` | uuid | 租户 |
| `product_id`、`warehouse_id` | uuid | 商品与仓库 |
| `delta_quantity` | numeric(20,6) | 本次变化，非 0 |
| `balance_after` | numeric(20,6) | 变化后余额，不小于 0 |
| `ledger_type` | varchar(32) | 业务类型/冲销类型 |
| `source_document_type` | varchar(32) | 来源单据类型 |
| `source_document_id` | uuid | 来源头 ID |
| `source_item_id` | uuid | 来源行 ID |
| `source_document_no` | varchar(32) | 单号快照 |
| `source_version` | integer | 产生副作用的单据版本 |
| `reversal_of_id` | uuid nullable | 指向被冲销流水 |
| `operator_id`、`occurred_at` | uuid/timestamptz | 操作审计 |

关键约束：

- `UNIQUE (tenant_id, source_document_type, source_document_id, source_item_id, source_version, ledger_type)` 防重复记账。
- `UNIQUE (tenant_id, reversal_of_id) WHERE reversal_of_id IS NOT NULL` 防重复冲销。
- 原流水不可更新；冲销行保存相反 `delta_quantity`。
- `app_runtime` 对该表只授予 SELECT、INSERT。

### 7.6 业务单据公共列

单据头按需要组合以下列，不使用一个巨型多态单据表：

| 列组 | 列 |
| --- | --- |
| 身份/状态 | `id`、`tenant_id`、`no`、`status`、`version` |
| 业务归属 | `business_at`、`owner_id`、`created_by`、`updated_by` |
| 审核 | `approved_by`、`approved_at`、`reversed_by`、`reversed_at` |
| 汇总 | `total_quantity`、`product_amount`、`tax_amount`、`discount_rate`、`discount_amount`、`other_amount`、`total_amount` |
| 其他 | `remark`、`created_at`、`updated_at` |

每个单据表都有 `UNIQUE (tenant_id, no)`，常用索引 `(tenant_id, business_at DESC)`、`(tenant_id, status, business_at DESC)`、`(tenant_id, owner_id, business_at DESC)`。

所有单据行包含 `id`、`tenant_id`、头 ID、`line_no`、商品/单位 ID、商品名/条码/单位名快照、数量、单价、商品金额、税率、税额、价税合计、备注。库存相关行增加仓库 ID；来源单据行增加 `source_item_id`。

### 7.7 采购表

| 表 | 头/行特有列 | 关键不变量 |
| --- | --- | --- |
| `purchase_order` | supplier、account、供应商快照、`deposit_amount`、累计入库/退货总量 | 供应商启用；汇总后端计算 |
| `purchase_order_item` | `received_quantity`、`returned_quantity` | `0 <= returned <= received <= ordered` |
| `purchase_in` | `purchase_order_id`、供应商快照、`settled_amount` | 来源订单 approved；`settled_amount <= total_amount` |
| `purchase_in_item` | `source_item_id`、warehouse | 所有行属于同一来源订单；数量不超剩余入库量 |
| `purchase_return` | `purchase_order_id`、供应商快照、`offset_amount` | `offset_amount <= total_amount` |
| `purchase_return_item` | `source_item_id`、warehouse | 数量不超已入库减已退量；库存充足 |

`purchase_in` 和 `purchase_return` 头保存供应商名称/税号等必要快照，历史展示不依赖供应商当前状态。

### 7.8 销售表

| 表 | 头/行特有列 | 关键不变量 |
| --- | --- | --- |
| `sale_order` | customer、account、`sales_user_id`、客户快照、`deposit_amount`、累计出库/退货总量 | 客户/销售员有效；不得低于最低价 |
| `sale_order_item` | `shipped_quantity`、`returned_quantity` | `0 <= returned <= shipped <= ordered` |
| `sale_out` | `sale_order_id`、客户快照、`sales_user_id`、`settled_amount` | 来源订单 approved；库存充足 |
| `sale_out_item` | `source_item_id`、warehouse | 数量不超剩余出库量 |
| `sale_return` | `sale_order_id`、客户快照、`sales_user_id`、`offset_amount` | 只能退已出库未退数量 |
| `sale_return_item` | `source_item_id`、warehouse | 审核增加库存，反审核需可扣回 |

### 7.9 独立库存单据表

| 表 | 特有列 | 审核副作用 |
| --- | --- | --- |
| `stock_in` / `stock_in_item` | 可选 supplier、warehouse、product、quantity、reference price | 增加库存，写 other_in 流水 |
| `stock_out` / `stock_out_item` | 可选 customer、warehouse、product、quantity、reference price | 扣减库存，写 other_out 流水 |
| `stock_move` / `stock_move_item` | from_warehouse、to_warehouse、product、quantity | 同事务写 move_out 与 move_in |
| `stock_check` / `stock_check_item` | warehouse、product、`snapshot_quantity`、`actual_quantity`、`difference_quantity` | 快照未变化时写 gain/loss |

`stock_check_item` 增加 `CHECK (actual_quantity >= 0)` 和 `CHECK (difference_quantity = actual_quantity - snapshot_quantity)`。调拨行增加 `CHECK (from_warehouse_id <> to_warehouse_id)`。

### 7.10 财务核销表

#### 付款单

`finance_payment` 头包含 supplier、account、财务人员、源单有符号总额、优惠额、实付净额、状态和审计列。

`finance_payment_item` 包含：

- `source_type`：只允许 `purchase_in`、`purchase_return`。
- `source_document_id/no`。
- `source_total_signed`：入库为正，退货为负。
- `settled_before_signed`：创建时的核销快照。
- `settlement_signed`：本次入库付款为正，退货冲减为负。
- `discount_allocated`：只分配给正向来源行，非负。
- `remark`。

#### 收款单

`finance_receipt` 与 `finance_receipt_item` 对称，只允许 `sale_out`、`sale_return`。

约束：

- 同一头下来源 `(source_type, source_document_id)` 唯一。
- 正向核销不超过剩余应付/应收；负向冲减绝对值不超过剩余信用额。
- 头净额 = `sum(settlement_signed) - discount_amount`，必须大于等于 0。
- `sum(item.discount_allocated) = header.discount_amount`；优惠只在正向行间按本次 settlement 比例分摊，按 source ID 排序后的末行吸收 4 位舍入差。
- 来源单据只保存正数累计已核销量；正向来源累计额增加 `settlement_signed`，负向来源累计额增加其绝对值，行表负责表达有符号方向。
- 审核才占用核销额度；draft 不改变来源累计金额。

来源头的 `settled_amount` 表示已结算总额，包含现金、折扣和同往来单位退货信用抵扣，不等同于纯现金流。实际现金只以 approved 付款/收款头的 `payment_amount`/`receipt_amount` 统计；API 和页面使用“已结算/未结算”避免误导。

### 7.11 ERP_OWNED_TABLES 完整清单

`ModuleDefinition.migration.owned_tables` 必须显式包含以下 40 张表，并由测试与 ERP metadata 双向比对：

```text
erp_setting
document_sequence
command_receipt
document_action_log
document_attachment
reconciliation_run
product_unit
product_category
product
supplier
customer
warehouse
warehouse_user_grant
settlement_account
stock_balance
stock_ledger
stock_in
stock_in_item
stock_out
stock_out_item
stock_move
stock_move_item
stock_check
stock_check_item
purchase_order
purchase_order_item
purchase_in
purchase_in_item
purchase_return
purchase_return_item
sale_order
sale_order_item
sale_out
sale_out_item
sale_return
sale_return_item
finance_payment
finance_payment_item
finance_receipt
finance_receipt_item
```

## 8. 迁移与 RLS

### 8.1 迁移链

ERP 使用独立 Alembic 配置和版本表，例如 `erp.alembic_version`。建议按阶段增加 revision：

1. `erp_control_and_master_baseline`：schema、设置、序号、幂等、日志、附件、主数据。
2. `erp_stock_baseline`：仓库授权、余额、流水、其他出入库、调拨、盘点。
3. `erp_purchase_and_sale_baseline`：采购与销售单据。
4. `erp_finance_baseline`：账户、付款、收款。
5. `erp_enable_forced_rls`：全表 policy、runtime 授权和不可变表权限收紧。

实现可以在未共享前合并 revision，但一旦进入共享历史不得改写。每个 upgrade 必须显式创建 schema、表、约束、索引、policy 和 grant；downgrade 至少能安全移除当前增量，baseline 不得在生产自动降级。

### 8.2 RLS policy

所有 ERP tenant-owned 表执行：

```sql
ALTER TABLE erp.<table> ENABLE ROW LEVEL SECURITY;
ALTER TABLE erp.<table> FORCE ROW LEVEL SECURITY;

CREATE POLICY <table>_tenant_isolation ON erp.<table>
USING (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid)
WITH CHECK (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid);
```

- `app_runtime` 获得 schema USAGE 和所需表权限，无表 owner、超级用户或 `BYPASSRLS`。
- `stock_ledger`、`document_action_log` 不授予 UPDATE/DELETE；`reconciliation_run` 只授予完成运行所需列的 UPDATE，不授予 DELETE。
- 无 `app.tenant_id` 时 SELECT 返回空、写入失败。
- migration/admin 连接验证 DDL；runtime 连接验证真实 RLS。

### 8.3 ERP TenantUnitOfWork

`ErpTenantUnitOfWork` 沿用 Items 模式并扩展到 `ERP_TENANT_SCOPED_MODELS`：

- `after_begin` 参数化设置事务级 `app.tenant_id`。
- `do_orm_execute` 对所有 ERP 模型应用 `with_loader_criteria`。
- 禁止 ORM bulk update/delete 和未封装 raw SQL。
- `before_flush` 校验新增/修改实体 tenant 与 UoW 一致，并禁止变更 tenant_id。
- UoW 退出恢复父 scope；最外层退出清理 Session info。
- API、事件消费者、Schedule 和 CLI 使用同一 UoW。

由于模型数量较多，监听器通过显式模型 tuple 管理，不扫描 SQLModel metadata；新增 ERP 模型未加入 tuple 时架构测试失败。

## 9. 计算与领域服务

### 9.1 DecimalValue

`domain.values` 提供受限值对象/函数：

- `parse_quantity(text) -> Decimal`
- `parse_money(text) -> Decimal`
- `parse_percent(text) -> Decimal`
- `quantize_quantity`、`quantize_money`
- `DecimalText` Pydantic alias，OpenAPI schema 为 string 且带 pattern。

禁止在业务逻辑使用 float。数据库返回 Decimal 后保持 Decimal，直到 API 序列化为规范字符串。

### 9.2 单据金额计算

每行：

```text
product_amount = round(quantity * unit_price, 4)
tax_amount     = round(product_amount * tax_rate / 100, 4)
line_total     = product_amount + tax_amount
```

表头：

```text
product_amount = sum(line.product_amount)
tax_amount     = sum(line.tax_amount)
gross_amount   = product_amount + tax_amount
discount       = round(gross_amount * discount_rate / 100, 4)
```

- 采购/销售订单：`total = gross - discount`。
- 采购入库/采购退货：`total = gross - discount + other_amount`。
- 销售出库/销售退货：`total = gross - discount - other_amount`。
- 后端忽略客户端汇总，只接受明细、折扣率和其他金额并重算。
- 任何结果小于 0 时返回验证错误。

### 9.3 单号服务

`DocumentNumberService` 使用 SQLAlchemy PostgreSQL `insert().on_conflict_do_update().returning()` 原子取得日序号：

1. 从 ERP setting 取得租户时区。
2. 使用服务端当前时间得到租户自然日，不使用客户端业务日期。
3. 对 `(tenant, prefix, date)` 插入 1 或原子加 1。
4. 格式化 6 位序号；超过 999999 时返回 `ERP_DOCUMENT_SEQUENCE_EXHAUSTED`。
5. 单据表唯一约束是最终边界，碰撞最多重试 3 次。

不新增 Redis 依赖；Redis 故障不影响单号正确性。

### 9.4 库存记账服务

`InventoryPostingService.post(effects, source, expected_version)` 是唯一库存写入口：

1. 提取并去重所有 `(product, warehouse)` 余额 key，按 `(warehouse_id, product_id)` 排序，避免并发死锁顺序漂移。
2. `SELECT ... FOR UPDATE` 锁定已有余额；正向首次入库可插入 0 余额并处理唯一冲突。
3. effect 按余额 key、来源行和类型稳定排序，逐行原子更新 `quantity = quantity + delta`，条件保证结果不小于 0。
4. 每个来源行 effect 写独立不可变流水及当时的 `balance_after`，不因同商品同仓库而合并来源。
5. 对 Outbox `erp.stock.changed` 事件按余额 key 合并本事务净变化，事件不替代逐行流水。
6. 调用方在同一事务更新来源累计量、单据状态、动作日志和 Outbox。

库存不足时整个事务回滚，不允许部分行成功。

### 9.5 核销服务

`SettlementService` 在审核付款/收款时：

1. 按 `(source_type, source_document_id)` 排序并 `FOR UPDATE` 锁定来源头。
2. 再次确认来源 approved、往来单位相同、仍有可核销余额。
3. 根据来源类型由服务端赋予符号，拒绝客户端符号反转。
4. 校验每行绝对值与头净额，按正向核销比例计算 `discount_allocated`，末行吸收舍入差。
5. 原子更新来源 `settled/offset_amount`；优惠视为正向来源已结清的一部分，不改变现金净额公式。
6. 更新核销单状态、动作日志和 Outbox。

反审核执行相反增量。任一来源已被后续数据改变导致无法完全撤回时返回 409。

## 10. 事务与并发

### 10.1 创建单据

1. Router 校验模块、权限、Tenant 和 DTO。
2. Application service 校验/占用 `Idempotency-Key`。
3. 校验主数据状态、用户、文件和数据范围。
4. 分配单号，重算明细与汇总。
5. 写头、行、附件和 `created` 动作日志。
6. 标记 command receipt completed，提交一次事务。

同一幂等键和同一 request hash 重试返回原资源；同键不同请求返回 409。

### 10.2 更新/删除 draft

- DTO 必带 `expected_version`。
- 加载头和行并应用数据范围过滤。
- 条件更新状态与版本；未命中时区分不存在/无权与版本冲突时不得泄露其他租户存在性。
- 更新采用替换行集合策略：校验完整新集合后计算 insert/update/delete diff；不得先删旧行再校验。
- 删除头和行前写动作日志快照；已审核返回 409。

### 10.3 审核库存单据

锁顺序固定：单据头 -> 来源订单头/行 -> 库存余额 -> 来源累计字段。

审核事务包含：

- CAS 状态校验。
- 来源可用数量校验。
- 库存 effect 记账。
- 来源订单累计量更新。
- 单据状态、审核人和版本更新。
- 动作日志与 Outbox 写入。

任何步骤失败全部回滚。禁止在提交后再补库存流水或累计量。

### 10.4 反审核

- 查找该单据最近一次审核版本产生的有效 effect，而不是根据当前余额猜测。
- 订单存在已审核下游入库/出库/退货时禁止反审核。
- 库存单据存在有效核销时禁止反审核。
- 冲销库存不足时禁止反审核。
- 写一一对应的 reversal ledger，恢复来源累计量，状态回 draft，记录反审核原因。
- `reason` 必填，长度 1..500。

### 10.5 死锁与重试

- 所有多资源锁使用稳定 UUID 排序。
- 仅对 PostgreSQL serialization failure/deadlock 做最多 3 次带抖动重试。
- 业务冲突、库存不足、版本冲突和验证错误不重试。
- 重试包围完整 application transaction，幂等 receipt 保证不会重复副作用。

## 11. HTTP API 契约

### 11.1 通用约定

- 根路径：`/api/v1/erp`。
- 列表响应：`{items, total, page, page_size}`。
- 详情响应不返回 `tenant_id`；租户上下文对客户端隐式。
- POST 创建返回 201；PATCH/命令返回最新详情；DELETE 返回 204。
- create、approve、reverse 必须携带 `Idempotency-Key` header。
- PATCH、approve、reverse body 必带 `expected_version`。
- 日期时间必须包含 offset；服务端转换 UTC。
- CSV 导出使用当前筛选、UTF-8 BOM 和安全文件名。

### 11.2 设置与主数据 API

| 方法与路径 | 权限 | 说明 |
| --- | --- | --- |
| `GET/PATCH /settings` | `erp:settings:read/update` | 缺少设置行时 GET 返回代码默认，不产生写副作用 |
| `GET/POST /product-units` | `erp:product-unit:list/create` | 分页/创建 |
| `GET/PATCH/DELETE /product-units/{id}` | list/update/delete | 详情、更新、删除 |
| `GET /product-units/export` | `erp:product-unit:export` | 当前筛选导出 |
| `GET /product-categories/tree` | `erp:product-category:list` | 分类树 |
| `POST/PATCH/DELETE /product-categories...` | create/update/delete | 分类维护 |
| `GET/POST/PATCH/DELETE /products...` | 对应 product 权限 | 商品 CRUD |
| `GET /products/export` | `erp:product:export` | 商品导出 |
| `GET/POST/PATCH/DELETE /suppliers...` | 对应 supplier 权限 | 供应商 CRUD |
| `GET/POST/PATCH/DELETE /customers...` | 对应 customer 权限 | 客户 CRUD |
| `GET/POST/PATCH/DELETE /warehouses...` | 对应 warehouse 权限 | 仓库 CRUD |
| `GET/PUT /warehouses/{id}/users` | `erp:warehouse:assign` | 用户仓库授权，PUT 替换集合 |
| `GET/POST/PATCH/DELETE /settlement-accounts...` | 对应 account 权限 | 结算账户 CRUD |

敏感账号详情另用 `GET /suppliers/{id}/sensitive`、`customers/{id}/sensitive`、`settlement-accounts/{id}/sensitive`，统一要求 `erp:finance-sensitive:read` 并记录审计；普通详情只返回掩码。

### 11.3 单据 API 模式

以下每种资源均提供统一接口：

```text
GET    /<resource>
POST   /<resource>
GET    /<resource>/export
GET    /<resource>/{id}
PATCH  /<resource>/{id}
DELETE /<resource>/{id}
POST   /<resource>/{id}/approve
POST   /<resource>/{id}/reverse
```

资源名：

- `purchase-orders`、`purchase-ins`、`purchase-returns`
- `sale-orders`、`sale-outs`、`sale-returns`
- `stock-ins`、`stock-outs`、`stock-moves`、`stock-checks`
- `finance-payments`、`finance-receipts`

每类动作使用对应 `erp:<resource>:list/create/update/delete/export/approve/reverse` 权限。详情复用 list 权限；审核与反审核不复用 update。

### 11.4 选单 API

| 路径 | 权限组合 | 返回 |
| --- | --- | --- |
| `GET /purchase-orders/selectable-for-in` | purchase-in:create + purchase-order:list | 已审核且存在剩余入库量的订单摘要 |
| `GET /purchase-orders/{id}/available-in-items` | 同上 | 每行剩余可入库量 |
| `GET /purchase-orders/selectable-for-return` | purchase-return:create + purchase-order:list | 存在可退量订单 |
| `GET /sale-orders/selectable-for-out` | sale-out:create + sale-order:list | 存在剩余出库量订单 |
| `GET /sale-orders/selectable-for-return` | sale-return:create + sale-order:list | 存在可退量订单 |
| `GET /finance-payment-sources` | finance-payment:create + 来源 list | 同供应商未结采购入库/退货 |
| `GET /finance-receipt-sources` | finance-receipt:create + 来源 list | 同客户未结销售出库/退货 |

选单接口执行与源列表相同的数据权限，不因“只用于选择器”放宽。

### 11.5 库存、统计与对账 API

| 方法与路径 | 权限 | 说明 |
| --- | --- | --- |
| `GET /stock-balances` | `erp:stock:list` | 商品/分类/仓库筛选 |
| `GET /stock-balances/export` | `erp:stock:export` | 当前范围导出 |
| `GET /stock-records` | `erp:stock-record:list` | 库存流水类型/单号/时间筛选 |
| `GET /stock-records/export` | `erp:stock-record:export` | 当前范围导出 |
| `GET /statistics/summary` | `erp:statistics:query` | 今日/昨日/月/年采购销售净额 |
| `GET /statistics/time-series` | `erp:statistics:query` | type 为 `sale` 或 `purchase`，并传范围与粒度 |
| `POST /reconciliation-runs` | `erp:reconciliation:execute` | 启动当前租户同步对账，幂等 |
| `GET /reconciliation-runs/latest` | `erp:reconciliation:read` | 最近结果 |

对账 API 不自动修复。差异修复必须通过受审计的业务冲销或单独批准的数据修复迁移。

## 12. 错误契约

| code | HTTP | 场景 |
| --- | --- | --- |
| `ERP_NOT_FOUND` | 404 | 当前租户和数据范围内不存在 |
| `ERP_MASTER_DATA_DISABLED` | 409 | 使用已停用主数据 |
| `ERP_DUPLICATE_VALUE` | 409 | 编码、条码、名称或默认项冲突 |
| `ERP_DOCUMENT_STATE_CONFLICT` | 409 | 状态不允许当前操作 |
| `ERP_VERSION_CONFLICT` | 409 | expected_version 过期 |
| `ERP_DOCUMENT_HAS_DOWNSTREAM` | 409 | 存在已审核下游单据，不能反审核 |
| `ERP_DOCUMENT_HAS_SETTLEMENT` | 409 | 已核销，不能反审核 |
| `ERP_SOURCE_NOT_APPROVED` | 409 | 来源单未审核 |
| `ERP_SOURCE_QUANTITY_EXCEEDED` | 409 | 入库/出库/退货超量 |
| `ERP_STOCK_INSUFFICIENT` | 409 | 库存不足 |
| `ERP_STOCK_SNAPSHOT_STALE` | 409 | 盘点快照过期 |
| `ERP_MINIMUM_SALE_PRICE_VIOLATION` | 409 | 售价低于最低价 |
| `ERP_SETTLEMENT_EXCEEDED` | 409 | 核销超过剩余金额 |
| `ERP_SETTLEMENT_SIGN_INVALID` | 422 | 核销方向或净额非法 |
| `ERP_IDEMPOTENCY_KEY_REUSED` | 409 | 相同 key 对应不同请求 |
| `ERP_DOCUMENT_SEQUENCE_EXHAUSTED` | 503 | 当日序号耗尽 |
| `ERP_FILE_NOT_ACCESSIBLE` | 404 | 文件不属于当前租户或无权访问 |
| `ERP_RECONCILIATION_FAILED` | 409 | 发现余额差异 |
| `ERP_TENANT_DATA_DEGRADED` | 503 | 当前租户 ERP 对账失败，写入失败关闭 |

错误 message 可国际化，但 code 稳定。无权访问其他租户资源时统一返回 404 或既有安全策略，不泄露资源存在性。

## 13. 权限与数据范围

### 13.1 权限集合

- 主数据：`list/create/update/delete/export`。
- 仓库额外：`assign`。
- 单据：`list/create/update/delete/export/approve/reverse`。
- 只读能力：`stock:list/export`、`stock-record:list/export`、`statistics:query`。
- 敏感信息：`finance-sensitive:read`。
- 对账：`reconciliation:read/execute`。

ModuleDefinition、Platform 菜单播种、后端 dependencies、前端 `v-access:code` 和测试必须使用同一完整字符串。

### 13.2 数据范围算法

- 主数据默认租户级共享；拥有 list 权限即可查看当前租户主数据。
- 所有业务单据以 `owner_id` 调用 `build_owner_data_scope_filter`，详情、更新、删除、审核、反审核、导出一致。
- 库存余额/流水先应用 RLS，再应用仓库范围：超级管理员或 DataScope=all 可查看全部；其他用户只能查看 `warehouse_user_grant` 明确授权仓库。
- 创建或审核库存相关单据时，所有仓库都必须在有效仓库范围内。
- 财务选单同时应用财务单据权限、来源 list 权限和来源 owner 数据范围。
- 统计查询直接在同一 owner/warehouse scope 下聚合，不先查询全量再在 Python 过滤。

为避免 ERP 导入授权 ORM，owner scope 继续通过 `platform.web_api.build_owner_data_scope_filter` 获得 SQL predicate；仓库授权由 ERP 自己的表管理。

## 14. 幂等与安全重试

### 14.1 Idempotency-Key

- 格式：1..128 个可打印 ASCII 字符；日志只保存 hash 或截断安全值。
- 唯一域：tenant + command_name + key。
- `request_sha256` 对 canonical JSON、路径资源 ID 和当前用户命令语义计算，不包含 token。
- receipt 与业务资源在同一事务提交；事务失败时 receipt 回滚。
- completed receipt 保留 7 天；清理任务只删除过期 completed 记录。
- 同 key 同 hash 返回原资源最新可见表示；同 key 不同 hash 返回 409。

### 14.2 审核副作用唯一性

即使调用方未正确重试，以下数据库边界仍防重复：

- 单据 status/version CAS。
- stock ledger source/version/type 唯一约束。
- reversal_of_id 部分唯一约束。
- finance item source 在单据内唯一。
- source 累计字段在锁内校验和更新。

## 15. 公开契约与事件

### 15.1 public_api

`public_api` 只包含冻结 Pydantic DTO、Protocol、稳定错误码和事件，不导入 FastAPI、SQLAlchemy、SQLModel 或 ERP 内部实现。

首版不提供通用跨模块 CRUD。必要查询按用例提供，例如：

```python
class StockAvailabilityQuery(Protocol):
    def get_available(
        self, tenant_id: UUID, requests: tuple[StockRequest, ...]
    ) -> tuple[StockAvailability, ...]: ...
```

只有出现真实消费者并声明模块依赖后才实现该端口，避免提前暴露内部表。

### 15.2 事件契约

| 事件 | aggregate_id | aggregate_sequence | 说明 |
| --- | --- | --- | --- |
| `erp.purchase_order.approved`，version 1 | order UUID | document version | 采购订单审核通知 |
| `erp.purchase_order.reversed`，version 1 | order UUID | document version | 采购订单反审核通知 |
| `erp.purchase_in.approved`，version 1 | document UUID | document version | 采购入库审核通知 |
| `erp.sale_order.approved`，version 1 | order UUID | document version | 销售订单审核通知 |
| `erp.sale_out.approved`，version 1 | document UUID | document version | 销售出库审核通知 |
| `erp.stock.changed`，version 1 | `product:warehouse` | stock balance version | 合并后的库存余额变化 |
| `erp.payment.approved`，version 1 | payment UUID | document version | 付款审核通知 |
| `erp.receipt.approved`，version 1 | receipt UUID | document version | 收款审核通知 |
| 对应 `.reversed`，version 1 | 同上 | 新版本 | 明确反审核语义 |

单据事件基名固定为：

```text
erp.purchase_order
erp.purchase_in
erp.purchase_return
erp.sale_order
erp.sale_out
erp.sale_return
erp.stock_in
erp.stock_out
erp.stock_move
erp.stock_check
erp.payment
erp.receipt
```

每个基名发布 `.approved` 和 `.reversed` 两个 EventContract，version 均为 1；另有 `erp.stock.changed` 和 `erp.reconciliation.failed` version 1。创建、普通更新和删除 draft 不发布跨模块事件，只写业务动作日志。

事件 payload 包含 `tenant_id`、资源 ID、单号、动作、发生时间和必要金额/库存 effect，不包含 ORM、Session、银行账号、附件 URL 或自由格式内部对象。

同一事务内写业务数据、OutboxEvent 和初始 Delivery。单据与库存事件首版仅为集成通知、没有必选消费者时可以声明 `allow_zero_subscribers=True`；`erp.reconciliation.failed` 必须配置 Platform required consumer，不能零订阅。一旦其他事件的业务正确性要求消费者改变下游状态，也必须配置 required target。

## 16. 附件与审计

### 16.1 附件流程

1. 前端先调用 Platform 文件上传接口。
2. ERP create/update DTO 只提交 `file_ids: UUID[]`。
3. `FileAssetDirectory` 批量校验当前租户、访问权和文件存在性。
4. ERP 写 `document_attachment`，不保存临时签名 URL。
5. 下载仍走 Platform 授权接口；ERP 详情只返回 file ID 和安全摘要。

已审核单据不允许修改附件。若后续支持补充附件，必须新增独立命令、权限和动作日志。

### 16.2 审计分层

- Platform OperationLog 记录 HTTP 方法、路径、状态和耗时。
- `document_action_log` 记录业务状态变化、版本、原因和安全差异摘要。
- `stock_ledger` 记录库存财务事实。
- Outbox 记录跨模块通知交付。

`metadata` 只保存字段名和前后值的安全摘要；银行账号密文、token、签名 URL、完整请求体不进入日志。

## 17. 前端实现

### 17.1 生成客户端

- 后端 OpenAPI 是 ERP 类型唯一事实源。
- 运行 `pnpm generate:api -- --edition erp` 生成 `src/modules/erp/api/generated`。
- 手写 `api/erp.ts` 只封装参数整形、下载和易用调用，不复制生成 DTO。
- generated 文件不得手工修改；CI 重生成并检查 drift。

### 17.2 精确小数

浏览器原生 Number 不满足 ERP 十进制预览。实现前将锁文件中已有的 `bignumber.js` 提升为 `web-antd` 显式依赖，所有表单预览、汇总和比较使用 BigNumber；不得用 `toFixed` 结果参与后续计算。

后端始终重新计算，前端汇总只用于即时反馈。前后端使用相同 4 位金额和 HALF_UP 规则，并以契约测试样例校验。

### 17.3 页面状态

- draft：可编辑、删除、审核；表单携带 expected_version。
- approved：只读，可反审核；存在下游阻断时后端返回稳定 409。
- 所有命令按钮有 loading、disabled 和重复点击保护。
- 删除/审核/反审核用确认弹窗，反审核必须填写原因。
- 409 版本冲突提示刷新，不自动覆盖用户输入。
- 选择器服务端分页和搜索，不一次拉取全部商品或单据。

### 17.4 组件装配

菜单 component 使用 `#/modules/erp/views/.../index.vue`。生成脚本将 ERP 页面写入 `generated-module-pages.ts`；不存在 ERP 的 Edition 不产生对应 glob。

ERP locale 位于模块内，键前缀 `erp.*`。公共枚举文案集中定义，不在页面重复硬编码。

## 18. 统计与查询性能

### 18.1 统计口径

- 销售净额：approved sale_out.total_amount - approved sale_return.total_amount。
- 采购净额：approved purchase_in.total_amount - approved purchase_return.total_amount。
- 使用业务时间 `business_at`，按 ERP setting 的租户时区计算 UTC 边界。
- 反审核单据因状态回 draft 自动排除，不按冲销流水重复扣减。
- owner 数据范围直接进入 SQL WHERE。

### 18.2 索引

除通用单据索引外至少包含：

- 商品：`(tenant_id, status, normalized_name)`、条码部分唯一。
- 分类：`(tenant_id, parent_id, sort)`。
- 往来单位：`(tenant_id, status, normalized_name)`。
- 库存余额：唯一 product/warehouse；`(tenant_id, warehouse_id, product_id)`。
- 库存流水：`(tenant_id, warehouse_id, occurred_at DESC)`、`(tenant_id, product_id, occurred_at DESC)`、`(tenant_id, source_document_no)`。
- 来源选单：单据 `(tenant_id, status, party_id, business_at DESC)`。
- 财务来源：`(tenant_id, status, settled_amount, business_at DESC)` 的适用组合索引。
- 动作日志：`(tenant_id, resource_type, resource_id, occurred_at DESC)`。

不得为低选择性布尔列单独建索引；使用租户前缀复合或部分索引。

### 18.3 性能门槛

- 10 万单据、100 万单据行和 100 万库存流水的基准数据下，常用分页 P95 小于 2 秒。
- 默认 page_size 20，最大 100。
- 导出默认上限 100,000 行；超过上限返回 422 并要求缩小筛选。后台导出任务不在 v1.0 P0。
- 所有跨主数据名称解析批量查询，禁止逐行 N+1 调用 UserDirectory。

## 19. 对账、健康与可观测性

### 19.1 对账检查

库存对账：按 `(product, warehouse)` 聚合全部 ledger delta，与 stock_balance.quantity 比较。

核销对账：按来源单聚合 approved finance item 的有符号 settlement，与来源头累计字段比较。

订单累计对账：按 approved 入库/出库/退货行聚合，与订单行累计量比较。

对账只写 `reconciliation_run` 和指标，不直接改数据。

### 19.2 Schedule 与健康状态

- `ModuleDefinition.schedules` 目标声明 `erp.reconciliation.daily` 和 `erp.command_receipt.cleanup`。
- Schedule 由受控 Platform tenant enumerator 获取启用 ERP 的租户，逐租户进入 ERP UoW；不使用裸跨租户 Session。
- 发现差异时把当前租户 `erp_setting.integrity_status` 更新为 degraded，并发布 `erp.reconciliation.failed` version 1 供 Platform 告警消费者处理。
- ERP 每个业务写 Router 通过公共依赖检查当前租户完整性；degraded 租户写入返回 `ERP_TENANT_DATA_DEGRADED`，其他租户和 Platform 不受影响。对账执行/查询、审计和故障诊断接口明确豁免该写保护，以便完成恢复。
- 修复并连续一次完整对账通过后，由对账服务恢复该租户 integrity_status；普通业务请求不得修改。
- 只有 ERP migration、共享依赖或模块实现本身发生全局故障时，才通过 ModuleRegistry 将整个 ERP 模块标为 degraded，并统一返回 `MODULE_UNAVAILABLE`。

若 Platform Schedule runner/tenant enumerator 尚未具备，该前置能力必须在 Phase A 完成；不得用 API 请求副作用代替。

### 19.3 指标

- `erp_document_commands_total{type,action,result}`
- `erp_document_command_duration_seconds{type,action}`
- `erp_stock_conflicts_total{reason}`
- `erp_settlement_conflicts_total{reason}`
- `erp_reconciliation_differences{kind}`
- `erp_outbox_pending_total`

标签不得包含 tenant_id、document_no、user_id 等高基数或敏感值。日志包含 trace ID 和内部资源 ID，单号按现有日志策略处理。

## 20. 安全要求

- 所有路由默认登录、模块访问和精确权限检查。
- 所有 Repository 只能接受 ErpTenantUnitOfWork，不接受裸 Session。
- tenant_id、owner_id、created_by、审核人、汇总、状态和版本均由服务端控制。
- 银行账号/结算账号使用现有 cryptography 能力加密，密钥不进入数据库或日志。
- CSV 防公式注入：以 `=`, `+`, `-`, `@` 开头的文本字段导出时按统一策略转义。
- 上传附件沿用 Platform 大小、扩展名、私有访问和存储渠道策略。
- HTTP 详情、导出、选单、统计、敏感字段和对账均有负向权限测试。
- 不使用 `privileged=True` 实现普通 ERP 请求。Schedule 的租户枚举是 Platform 受控入口，进入单租户后使用普通 ERP UoW。

## 21. 测试设计

### 21.1 单元测试

目录建议 `backend/tests/modules/erp/unit`：

- Decimal parse、舍入、折扣和税额样例。
- 单号格式、时区日界线和序号耗尽。
- 状态机合法/非法迁移。
- 库存 effect 合并与冲销映射。
- 采购/销售剩余数量计算。
- 正负核销与净额计算。
- 敏感字段掩码。

### 21.2 Repository 与事务测试

目录建议 `backend/tests/modules/erp`：

- 复合租户 FK 拒绝跨租户引用。
- UoW 自动读过滤、写校验、tenant 不可变、bulk DML 禁止。
- app_runtime 无 scope、跨租户、raw SQL 和 RLS policy 测试。
- 两线程/连接并发审核只产生一次 effect。
- 并发扣同库存不产生负数。
- 调拨任一端失败整单回滚。
- 盘点快照过期冲突。
- 并发核销不超额。
- 反审核写冲销而非删除原流水。
- Outbox 与业务事务共同提交/回滚。

### 21.3 API 测试

每个资源覆盖：

- list/detail/create/update/delete。
- DTO 422、not found、disabled、重复值、状态冲突。
- 权限缺失 403、数据范围 404/403 既有策略。
- Idempotency-Key 同请求重放和不同请求冲突。
- expected_version 冲突。
- 导出筛选、脱敏、CSV 注入保护。
- 选单不返回无权、未审核或无剩余额度资源。

### 21.4 迁移与模块测试

- ERP migration upgrade 到 head、空库创建、重复检查和 downgrade 边界。
- `uv run alembic check`。
- owned_tables 与 ERP metadata 一致且唯一。
- registry、Manifest、OpenAPI digest 和模块边界测试。
- Base/Items 不暴露 ERP；ERP Edition 只装配 Platform+ERP。
- 新增非法 Platform ORM import 时架构测试失败。

### 21.5 前端与 E2E

关键 Playwright 流程：

1. 商品/仓库主数据创建。
2. 采购订单 -> 分批入库 -> 退货 -> 付款净额核销。
3. 销售订单 -> 分批出库 -> 退货 -> 收款净额核销。
4. 其他出入库、调拨、盘点和库存流水追踪。
5. 重复审核、版本冲突、库存不足和下游阻断。
6. 权限按钮、直接 URL、跨部门和仓库授权负向场景。
7. 桌面与移动查询/详情，复杂单据在小屏无操作遮挡。

检查控制台错误、网络失败、loading、重复点击和响应式布局。

## 22. 实施阶段与任务包

### 22.1 Phase A：基础与库存底座

| 任务包 | 输出 | 退出证据 |
| --- | --- | --- |
| A1 模块骨架 | module/public_api/domain/application/infrastructure/routes | 边界测试、registry/manifest 测试 |
| A2 Platform 端口 | User/File/Sensitive web deps | 契约与适配器测试，无 ORM 泄漏 |
| A3 迁移基线 | control/master/stock tables、RLS、grant | upgrade、alembic check、runtime RLS |
| A4 主数据 | 商品、分类、单位、仓库、授权 | API/RBAC/数据验证测试 |
| A5 库存记账 | balance/ledger、其他出入库、调拨、盘点 | 并发、负库存、冲销、对账测试 |
| A6 前端底座 | 生成客户端、主数据和库存页面 | typecheck、build、库存 E2E |

### 22.2 Phase B：采购与销售

| 任务包 | 输出 | 退出证据 |
| --- | --- | --- |
| B1 采购 | 供应商、订单、入库、退货、选单 | 分批/超量/反审核阻断测试 |
| B2 销售 | 客户、订单、出库、退货、选单 | 最低价/库存/分批/超量测试 |
| B3 事件 | 审核、反审核、stock changed Outbox | 事务、重复投递和 schema 测试 |
| B4 前端闭环 | 采购销售页面和行编辑器 | 主流程与权限 E2E |

### 22.3 Phase C：财务、统计与发布

| 任务包 | 输出 | 退出证据 |
| --- | --- | --- |
| C1 财务 | 账户、付款、收款、正负核销 | 部分/全部/超额/并发/反审核测试 |
| C2 统计 | 汇总、时间序列、数据范围 | 口径对账与性能测试 |
| C3 对账与健康 | reconciliation、schedule、metrics | 差异触发 degraded 与恢复演练 |
| C4 导出/附件/敏感信息 | CSV、文件引用、加密与审计 | 安全和负向测试 |
| C5 Edition 发布 | erp Edition、文档、Compose | build、migration、startup、N-1 门禁 |

任务包可以分 PR 合并，但 ERP 权益默认关闭。Phase A-C 的 P0 验收完成前不得把 ERP 标为可交付。

## 23. PRD 追踪矩阵

| PRD 能力 | TRD 实现章节 | 核心验证 |
| --- | --- | --- |
| 商品与往来单位 | 7.4、11.2 | CRUD、唯一性、停用、引用保护 |
| 采购闭环 | 7.7、9、10、11.3/11.4 | 分批、超量、库存、付款 |
| 销售闭环 | 7.8、9、10、11.3/11.4 | 最低价、库存、收款 |
| 库存可信 | 7.5、9.4、10.3/10.4 | 原子增量、不可变流水、冲销、对账 |
| 财务核销 | 7.10、9.5、11.3 | 正负方向、超额、并发、反审核 |
| 首页统计 | 11.5、18 | 时间区间、数据范围、净额口径 |
| 租户与安全 | 8、13、20 | UoW、RLS、权限、负向测试 |
| Edition | 5 | Manifest、Base/Items/ERP 构建 |
| 审计与事件 | 15、16 | Outbox、动作日志、敏感操作 |
| 可运维性 | 19、21 | 对账、健康、指标、恢复演练 |

## 24. 已知风险与技术边界

| 风险 | 技术处理 |
| --- | --- |
| 约 40 张表一次建模错误率高 | 分 migration/Phase，先固化共享列和聚合不变量 |
| Items UoW 监听器模式在多模块扩展时重复 | ERP 先显式实现；若抽共享 helper，必须由独立架构变更和全模块回归支撑 |
| Platform 文件公开端口当前缺失 | A2 是阻塞前置项，禁止 ERP 直接导入 file ORM |
| 租户时区当前不在 TenantContext | ERP setting 提供模块内时区，缺省不写库 |
| 银行账号明文风险 | 复用 cryptography，通过公开 protector 保存密文和末四位 |
| 反审核链复杂 | 以原 effect/settlement 记录反向恢复，不从当前汇总猜测 |
| 统计与大导出拖慢 API | 强制筛选、索引、导出上限；异步报表后续立项 |
| Schedule 平台执行器可能未完备 | Phase A 补齐受控 tenant enumerator/runner，不在请求中偷偷执行 |
| 参考系统核销负数语义不清 | TRD 固定有符号来源与非负净额，现金退款排除 |

## 25. 完成定义

只有满足以下全部条件，ERP TRD 才算实现完成：

- `erp` ModuleDefinition、独立 Edition、schema、migration namespace 和生成注册表完整。
- 目标表、约束、索引、复合租户外键、RLS policy 和 runtime grant 均由迁移表达。
- 所有 ERP Repository 受 TenantUnitOfWork 约束，tenant ID 不可从请求覆盖。
- 所有单据支持版本 CAS、幂等创建/审核/反审核和稳定错误码。
- 库存、来源累计量、核销、动作日志和 Outbox 在正确事务内提交。
- 库存与核销对账为零差异，差异场景能失败关闭并进入 degraded。
- 后端 OpenAPI 重新生成 ERP 客户端，仓库无 generated drift。
- 后端 lint、ERP 测试、迁移测试、RLS runtime 测试、前端 typecheck、ERP build/E2E 和 Edition 构建实际通过。
- Base/Items 未注册或预加载 ERP，前后端 Manifest 一致。
- 部署、监控、迁移、兼容、回退和安全说明更新为当前事实。
- 远端 CI、镜像扫描、签名、SBOM、N-1 演练和团队签署以真实证据验收；未执行项明确列出。
