# 架构决策记录

本目录记录 Fast Vben Admin 模块化产品架构中的关键决策。ADR 一经接受原则上不直接改写历史结论；需要改变决策时，应新增 ADR 并标记其替代关系。

| ADR | 标题 | 状态 |
| --- | --- | --- |
| [ADR-0001](./0001-oauth2-authorization-server.md) | OAuth2 授权服务器角色与首期范围 | Accepted |
| [ADR-0002](./0002-multi-tenancy-shared-schema.md) | 多租户隔离与请求上下文 | Accepted |
| [ADR-0003](./0003-edition-module-source-of-truth.md) | Edition 与模块状态的唯一事实源 | Proposed |
| [ADR-0004](./0004-module-access-control.md) | 模块开通与后端访问控制 | Proposed |
| [ADR-0005](./0005-module-migration-orchestration.md) | 多模块数据库迁移编排 | Proposed |
| [ADR-0006](./0006-module-lifecycle-and-events.md) | 模块生命周期与跨模块事件可靠性 | Proposed |
| [ADR-0007](./0007-platform-master-data-lifecycle.md) | 平台主数据生命周期与跨模块引用 | Proposed |
| [ADR-0008](./0008-module-openapi-client-generation.md) | 模块级 OpenAPI 与前端客户端生成 | Proposed |
| [ADR-0009](./0009-module-public-contracts-and-dependency-boundaries.md) | 模块公开契约与依赖边界 | Proposed |

状态含义：

- `Proposed`：已形成建议，尚未通过实现验证。
- `Accepted`：已经评审确认，实施必须遵循。
- `Superseded`：已被后续 ADR 替代。
- `Rejected`：评审后不采用。
