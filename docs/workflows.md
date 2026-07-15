# 可选 BPM 工作流 POC

项目提供一个独立、默认关闭的 BPM POC。它不参与租户核心初始化，也不是多租户主链路的完成条件。

## 启用

在 `.env` 中设置：

```env
BPM_ENABLED=true
```

然后应用迁移并重新执行初始化，使流程菜单和权限进入当前环境：

```powershell
cd backend
uv run alembic upgrade head
uv run python app/initial_data.py
```

关闭时，`/api/v1/workflows/*` 返回 404；初始化脚本保留 inactive 的权限清单记录，但不会显示流程菜单或授予有效权限。

## POC 范围

- BPMN 定义、草稿版本和单一已发布版本。
- 发起、审批、驳回、撤回、转交和抄送。
- `starter`、`user:<uuid>`、`role:<code>`、`department:<code-or-uuid>`、`post:<code>` 分派表达式。
- 业务类型、业务 ID、JSON 表单数据与流程实例关联。
- 待办截止时间、超时标记、应用内通知记录和完整操作审计。
- 所有定义、版本、实例、待办、抄送、通知和审计数据按 `tenant_id` 隔离。

流程执行与状态序列化由 SpiffWorkflow 负责；转交、抄送、分派解析、通知和审计属于应用层职责。

## 边界

当前只验证顺序用户任务的最小闭环，不包含可视化 BPMN 设计器、定时调度器、会签、条件表达式安全沙箱、外部任务、补偿事务和生产级消息投递。超时由查询标记，尚未配置后台定时升级任务。

SpiffWorkflow 3.x 使用 LGPLv3。正式启用前必须完成许可证、升级策略、持久化兼容性、任务调度、监控告警、备份恢复和容量评审。未完成这些评审前，BPM 保持可选 POC，不作为生产承诺。
