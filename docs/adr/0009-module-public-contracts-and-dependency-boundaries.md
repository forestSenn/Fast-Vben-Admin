# ADR-0009：模块公开契约与依赖边界

- 状态：Proposed
- 日期：2026-07-20
- 关联文档：[模块化产品架构规划](../modular-product-architecture.md)
- 补充关系：细化 [ADR-0006](./0006-module-lifecycle-and-events.md) 的能力适配器和事件契约，并约束 [ADR-0007](./0007-platform-master-data-lifecycle.md) 的平台主数据访问方式

## 背景

edition、Manifest、独立路由和独立数据库 Schema 可以控制模块是否被装配，但不能自动形成代码边界。如果业务模块仍然导入其他模块的 ORM 模型、Service、Repository 或路由，目录虽然分开，修改仍会沿内部实现传播，也无法在缺少可选模块时独立运行。

参考项目 LZ-litchi 使用 `module.xxx.api.*` 接口和 DTO 隔离大部分跨模块调用，这种显式 API 包值得采用。但其业务模块仍依赖提供方的完整 Maven 模块，部分业务模块直接依赖 BPM，接口与实现在同一制品中，无法单独约束公开面，也不能自然表达“能力不存在时降级”。

本项目需要在模块化单体阶段形成可检查的接口边界，并保证这些边界未来可以替换为进程内适配器、HTTP 客户端或消息消费者，而不要求业务核心代码随部署形态改变。

## 决策

### 1. 公开面与内部实现分离

每个模块只通过 `public_api` 暴露跨模块可用内容：

```text
backend/app/modules/erp/
  module.py
  public_api/
    commands.py
    queries.py
    dto.py
    events.py
  domain/
  application/
    ports.py
    services/
  infrastructure/
  routes/
  migrations/
```

`public_api` 只允许包含：

- 稳定的同步查询或命令接口。
- 输入、输出 DTO 和错误语义。
- 版本化事件 Schema。
- 供组合根校验实现的 `Protocol` 或抽象接口。

业务模块的 `public_api` 禁止导出或传递：

- SQLModel/ORM 实体、Mapper、Repository 或数据库查询对象。
- `Session`、数据库连接和可由调用方继续修改的持久化对象。
- FastAPI Router、请求对象或模块内部 Web 依赖函数。
- 模块内部 Service、配置对象及第三方 SDK 类型。

公开 DTO 使用 Pydantic 模型、不可变 dataclass 或 Python 标准类型。模块内部实现可以依赖自己的 `public_api`，但 `public_api` 不能反向导入 `domain`、`application`、`infrastructure` 或 `routes`。

### 2. 依赖方向

允许的依赖方向固定为：

```text
composition root / generated registry
  → module implementation
  → declared dependency.public_api
  → platform.public_api and stable shared contracts
```

具体规则：

1. 业务模块可以依赖平台公开接口和 Manifest 中声明的必选依赖模块 `public_api`。
2. 业务模块禁止导入其他业务模块的 `domain`、`application`、`infrastructure`、`routes`、`migrations` 和 ORM 模型。
3. 平台核心不能导入具体业务模块；只有组合根、生成注册表和 edition 构建工具可以装配业务模块。
4. 禁止为规避边界把业务模型、Repository 或混合领域逻辑移动到全局 `common`。共享包只保存无业务归属的技术基础设施和稳定契约。
5. Manifest 中的依赖声明必须与静态导入检查结果一致。未声明依赖或循环依赖使 CI 失败。

### 3. 平台能力通过公开端口提供

身份、租户、组织、权限、文件、消息等平台能力必须提供窄接口，例如：

```python
class UserDirectory(Protocol):
    def get_users(self, user_ids: Collection[UUID]) -> list[UserSummary]: ...
    def validate_active_users(self, user_ids: Collection[UUID]) -> None: ...
```

业务模块只能依赖 `UserDirectory` 和 `UserSummary`，不能直接查询平台用户、部门、岗位表。调用方只传稳定标识和请求上下文；租户隔离、数据权限及数据读取由接口实现方负责。

公开接口按业务用途设计，不暴露通用 ORM CRUD。一个调用需要过多平台数据时，应增加面向用例的批量查询，避免调用方拼接平台内部关系。

FastAPI Router 所需的认证、租户上下文和 `require_module_access` 由平台提供单独的稳定 Web 集成面，例如 `platform.web_api`。这是框架适配接口，不属于领域公开 DTO；它可以使用 FastAPI 的依赖注入机制，但返回不可变的 Principal、TenantContext 等公开上下文，不能返回平台 ORM 实体或暴露内部 Service。

### 4. 可选能力不形成模块硬依赖

审批、电子签章、外部支付等可选能力使用稳定的能力契约和 Provider 注册机制。契约至少包含：

- 唯一能力编码，例如 `workflow.approval`。
- 主版本和兼容范围。
- 请求、响应、错误及超时语义。
- Provider 健康状态和生命周期。
- 缺少 Provider 时的明确行为。

ERP 等消费者依赖能力契约，不直接导入 IOA：

```text
ERP → ApprovalCapabilityV1 ← IOA provider
                         ← ERP simple provider
```

具体 Provider 只由组合根根据 Build Manifest 绑定。没有 IOA 时，ERP 必须使用声明过的本地实现，或者明确返回 `CAPABILITY_UNAVAILABLE`；禁止在业务代码中通过动态导入探测 IOA。

创建长生命周期业务实例时，按照 ADR-0006 保存 `provider_code`、`provider_version` 和外部实例标识。Provider 切换不能静默改变进行中实例的处理方。

### 5. 同步接口与事件的选择

- 需要立即返回且不改变其他模块业务状态的读取，使用同步公开查询接口。
- 必须立即得到结果的跨模块命令，使用能力接口，并定义超时、幂等键和失败语义。
- 会改变其他模块业务状态的传播，使用 ADR-0006 规定的事务 Outbox 和版本化事件。
- 指标、日志等不影响业务正确性的通知才允许使用进程内临时事件。

事件 Schema 放在发布方 `public_api.events` 或独立的稳定契约包中。事件消费者只能依赖事件 Schema，不能依赖发布方 Outbox ORM 实体。事件字段只做向后兼容扩展；破坏性修改发布新主版本。

### 6. ModuleDefinition 是装配契约

`ModuleDefinition` 应从当前只声明 Router 的结构扩展为声明式装配契约，至少覆盖：

```text
identity and version
required dependencies and optional capabilities
routers and OpenAPI ownership
permissions and menus
migration specification and owned metadata
lifecycle and health hooks
provided capabilities
event publishers and subscribers
workers and schedules
ReferenceGuard
```

定义中保存结构化声明或类型明确的 Provider，不接受不受控的目录扫描。组合根负责校验依赖、选择 Provider 和调用生命周期钩子；业务模块不得反向操作全局注册表。

### 7. 自动执行边界

CI 必须增加架构边界检查，至少验证：

1. 业务模块没有导入其他模块内部包。
2. `public_api` 没有反向导入模块实现。
3. 平台核心没有导入业务模块。
4. 实际模块导入依赖是 Manifest 声明依赖的子集。
5. 可选模块缺失时消费者仍可导入、启动并执行规定的降级路径。
6. 公开 DTO、事件 Schema 和 OpenAPI 的破坏性变化经过兼容性检查。
7. 每个 edition 的独立启动测试只注册当前 Manifest 包含的实现和 Provider。

第一阶段可以使用基于 Python AST 的仓库测试执行规则，后续再按需要引入 import-linter。仅依靠代码评审不视为满足边界要求。

## 结果

优点：

- 跨模块依赖从目录约定变为可检查的代码契约。
- 平台内部模型变化不会直接传播到所有业务模块。
- IOA 等可选模块不存在时，ERP 仍可构建和运行。
- 同一业务接口可以从进程内实现演进为 HTTP 或消息适配器。
- 契约测试和替身实现可以缩小模块测试范围。

代价：

- 需要为平台能力和业务能力维护 DTO、接口及适配器。
- 进程内调用也需要执行数据转换，不能直接传递 ORM 对象。
- `ModuleDefinition`、组合根和 CI 边界检查需要继续建设。
- 接口粒度需要治理，过宽会泄漏内部模型，过细会产生大量往返调用。

## 验收标准

- Items 模块迁入独立目录后，不再从全局 `app.models` 或 `app.api.routes.items` 导入业务实现。
- Items 只通过平台公开接口取得当前用户、租户和数据权限能力。
- 新增一个违反依赖方向的导入时，CI 能给出源模块、目标模块和违规文件。
- ERP edition 不包含 IOA 时，ERP 能启动，并通过本地审批 Provider 或明确关闭审批功能。
- Suite edition 可以由组合根将 `workflow.approval.v1` 绑定到 IOA，ERP 不导入 IOA 内部包。
- 公开接口测试不需要初始化提供方的 Router 或直接访问提供方数据库表。
- 事件消费者只使用版本化事件 DTO，重复投递保持幂等。
