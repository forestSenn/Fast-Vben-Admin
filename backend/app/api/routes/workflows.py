import uuid
from datetime import timedelta
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import or_
from sqlmodel import col, select

from app.api.deps import (
    CurrentTenant,
    CurrentUser,
    SessionDep,
    require_permission,
    user_has_permission,
)
from app.core.config import settings
from app.models import (
    Department,
    Post,
    Role,
    TenantMembership,
    User,
    UserPost,
    UserRole,
    WorkflowAudit,
    WorkflowAuditPublic,
    WorkflowCc,
    WorkflowDefinition,
    WorkflowDefinitionCreate,
    WorkflowDefinitionPublic,
    WorkflowDefinitionVersion,
    WorkflowInstance,
    WorkflowInstancePublic,
    WorkflowInstanceStatus,
    WorkflowNotification,
    WorkflowStartRequest,
    WorkflowTask,
    WorkflowTaskActionRequest,
    WorkflowTaskPublic,
    WorkflowTaskStatus,
    WorkflowVersionCreate,
    WorkflowVersionPublic,
    WorkflowVersionStatus,
    get_datetime_utc,
)
from app.workflow_engine import (
    ReadyWorkflowTask,
    complete_workflow_task,
    start_workflow,
    validate_workflow_definition,
)


def require_bpm_enabled() -> None:
    if not settings.BPM_ENABLED:
        raise HTTPException(status_code=404, detail="BPM module is disabled")


router = APIRouter(
    prefix="/workflows",
    tags=["workflows"],
    dependencies=[Depends(require_bpm_enabled)],
)

DefinitionManager = Annotated[
    User, Depends(require_permission("workflow:definition:manage"))
]
WorkflowReader = Annotated[User, Depends(require_permission("workflow:task:list"))]
InstanceStarter = Annotated[
    User, Depends(require_permission("workflow:instance:start"))
]


def validate_definition_input(
    *, bpmn_xml: str, process_id: str, task_assignments: dict[str, str]
) -> None:
    try:
        validate_workflow_definition(bpmn_xml=bpmn_xml, process_id=process_id)
    except Exception as exc:
        raise HTTPException(status_code=422, detail=f"Invalid BPMN definition: {exc}")
    for task_key, expression in task_assignments.items():
        if not task_key or not expression:
            raise HTTPException(status_code=422, detail="Invalid task assignment")
        if expression == "starter":
            continue
        kind, separator, value = expression.partition(":")
        if (
            not separator
            or kind not in {"department", "post", "role", "user"}
            or not value
        ):
            raise HTTPException(
                status_code=422,
                detail=f"Unsupported assignment expression: {expression}",
            )


def version_public(version: WorkflowDefinitionVersion) -> WorkflowVersionPublic:
    return WorkflowVersionPublic(
        **version.model_dump(exclude={"status"}),
        status=WorkflowVersionStatus(version.status),
    )


def definition_public(
    *, session: SessionDep, definition: WorkflowDefinition
) -> WorkflowDefinitionPublic:
    versions = session.exec(
        select(WorkflowDefinitionVersion)
        .where(
            WorkflowDefinitionVersion.tenant_id == definition.tenant_id,
            WorkflowDefinitionVersion.definition_id == definition.id,
        )
        .order_by(col(WorkflowDefinitionVersion.version).desc())
    ).all()
    return WorkflowDefinitionPublic(
        **definition.model_dump(),
        versions=[version_public(version) for version in versions],
    )


def get_definition(
    *, session: SessionDep, tenant_id: uuid.UUID, definition_id: uuid.UUID
) -> WorkflowDefinition:
    definition = session.exec(
        select(WorkflowDefinition).where(
            WorkflowDefinition.id == definition_id,
            WorkflowDefinition.tenant_id == tenant_id,
        )
    ).first()
    if definition is None:
        raise HTTPException(status_code=404, detail="Workflow definition not found")
    return definition


def get_version(
    *, session: SessionDep, tenant_id: uuid.UUID, version_id: uuid.UUID
) -> WorkflowDefinitionVersion:
    version = session.exec(
        select(WorkflowDefinitionVersion).where(
            WorkflowDefinitionVersion.id == version_id,
            WorkflowDefinitionVersion.tenant_id == tenant_id,
        )
    ).first()
    if version is None:
        raise HTTPException(status_code=404, detail="Workflow version not found")
    return version


def get_instance(
    *, session: SessionDep, tenant_id: uuid.UUID, instance_id: uuid.UUID
) -> WorkflowInstance:
    instance = session.exec(
        select(WorkflowInstance).where(
            WorkflowInstance.id == instance_id,
            WorkflowInstance.tenant_id == tenant_id,
        )
    ).first()
    if instance is None:
        raise HTTPException(status_code=404, detail="Workflow instance not found")
    return instance


def get_task(
    *, session: SessionDep, tenant_id: uuid.UUID, task_id: uuid.UUID
) -> WorkflowTask:
    task = session.exec(
        select(WorkflowTask).where(
            WorkflowTask.id == task_id,
            WorkflowTask.tenant_id == tenant_id,
        )
    ).first()
    if task is None:
        raise HTTPException(status_code=404, detail="Workflow task not found")
    return task


def assignment_matches_user(
    *,
    session: SessionDep,
    tenant_id: uuid.UUID,
    user_id: uuid.UUID,
    expression: str,
    starter_user_id: uuid.UUID,
) -> bool:
    if expression == "starter":
        return user_id == starter_user_id
    kind, _, value = expression.partition(":")
    if kind == "user":
        return str(user_id) == value
    if kind == "role":
        return (
            session.exec(
                select(UserRole)
                .join(Role, Role.id == UserRole.role_id)
                .where(
                    UserRole.tenant_id == tenant_id,
                    UserRole.user_id == user_id,
                    Role.tenant_id == tenant_id,
                    Role.code == value,
                    Role.is_active,
                )
            ).first()
            is not None
        )
    if kind == "post":
        return (
            session.exec(
                select(UserPost)
                .join(Post, Post.id == UserPost.post_id)
                .where(
                    UserPost.tenant_id == tenant_id,
                    UserPost.user_id == user_id,
                    Post.tenant_id == tenant_id,
                    Post.code == value,
                    Post.is_active,
                )
            ).first()
            is not None
        )
    if kind == "department":
        filters = [Department.code == value]
        try:
            filters.append(Department.id == uuid.UUID(value))
        except ValueError:
            pass
        return (
            session.exec(
                select(TenantMembership)
                .join(
                    Department,
                    Department.id == TenantMembership.department_id,
                )
                .where(
                    TenantMembership.tenant_id == tenant_id,
                    TenantMembership.user_id == user_id,
                    TenantMembership.is_active,
                    Department.tenant_id == tenant_id,
                    Department.is_active,
                    or_(*filters),
                )
            ).first()
            is not None
        )
    return False


def can_manage_all_tasks(
    *, session: SessionDep, current_user: CurrentUser, tenant_id: uuid.UUID
) -> bool:
    return user_has_permission(
        session=session,
        current_user=current_user,
        tenant_id=tenant_id,
        permission_code="workflow:task:manage",
    )


def can_act_on_task(
    *,
    session: SessionDep,
    current_user: CurrentUser,
    tenant_id: uuid.UUID,
    task: WorkflowTask,
    instance: WorkflowInstance,
) -> bool:
    return can_manage_all_tasks(
        session=session, current_user=current_user, tenant_id=tenant_id
    ) or assignment_matches_user(
        session=session,
        tenant_id=tenant_id,
        user_id=current_user.id,
        expression=task.assignment_expression,
        starter_user_id=instance.started_by,
    )


def add_notification(
    *,
    session: SessionDep,
    tenant_id: uuid.UUID,
    instance_id: uuid.UUID,
    task_id: uuid.UUID | None,
    recipient_user_id: uuid.UUID,
    kind: str,
    message: str,
) -> None:
    membership = session.get(TenantMembership, (recipient_user_id, tenant_id))
    if membership is None or not membership.is_active:
        return
    session.add(
        WorkflowNotification(
            tenant_id=tenant_id,
            instance_id=instance_id,
            task_id=task_id,
            recipient_user_id=recipient_user_id,
            kind=kind,
            message=message,
        )
    )


def sync_ready_tasks(
    *,
    session: SessionDep,
    instance: WorkflowInstance,
    version: WorkflowDefinitionVersion,
    ready_tasks: list[ReadyWorkflowTask],
) -> list[WorkflowTask]:
    created: list[WorkflowTask] = []
    for ready in ready_tasks:
        existing = session.exec(
            select(WorkflowTask).where(
                WorkflowTask.tenant_id == instance.tenant_id,
                WorkflowTask.engine_task_id == ready.engine_task_id,
            )
        ).first()
        if existing is not None:
            continue
        assignment = version.task_assignments.get(ready.task_key, "starter")
        due_at = (
            get_datetime_utc() + timedelta(hours=version.timeout_hours)
            if version.timeout_hours
            else None
        )
        task = WorkflowTask(
            tenant_id=instance.tenant_id,
            instance_id=instance.id,
            engine_task_id=ready.engine_task_id,
            task_key=ready.task_key,
            name=ready.name,
            assignment_expression=assignment,
            due_at=due_at,
        )
        session.add(task)
        session.flush()
        created.append(task)
        if assignment.startswith("user:"):
            try:
                recipient_id = uuid.UUID(assignment.removeprefix("user:"))
            except ValueError:
                continue
            add_notification(
                session=session,
                tenant_id=instance.tenant_id,
                instance_id=instance.id,
                task_id=task.id,
                recipient_user_id=recipient_id,
                kind="task_assigned",
                message=f"Workflow task assigned: {task.name}",
            )
    return created


def task_public(task: WorkflowTask) -> WorkflowTaskPublic:
    return WorkflowTaskPublic(
        **task.model_dump(exclude={"status"}),
        status=WorkflowTaskStatus(task.status),
        is_overdue=bool(
            task.status == WorkflowTaskStatus.PENDING
            and task.due_at
            and task.due_at < get_datetime_utc()
        ),
    )


def instance_public(
    *, session: SessionDep, instance: WorkflowInstance
) -> WorkflowInstancePublic:
    tasks = session.exec(
        select(WorkflowTask)
        .where(
            WorkflowTask.tenant_id == instance.tenant_id,
            WorkflowTask.instance_id == instance.id,
        )
        .order_by(WorkflowTask.created_at)
    ).all()
    audits = session.exec(
        select(WorkflowAudit)
        .where(
            WorkflowAudit.tenant_id == instance.tenant_id,
            WorkflowAudit.instance_id == instance.id,
        )
        .order_by(WorkflowAudit.created_at)
    ).all()
    return WorkflowInstancePublic(
        **instance.model_dump(exclude={"engine_state", "status", "tenant_id"}),
        status=WorkflowInstanceStatus(instance.status),
        tasks=[task_public(task) for task in tasks],
        audits=[WorkflowAuditPublic.model_validate(audit) for audit in audits],
    )


@router.get("/definitions", response_model=list[WorkflowDefinitionPublic])
def list_definitions(
    session: SessionDep,
    tenant_context: CurrentTenant,
    _reader: WorkflowReader,
) -> list[WorkflowDefinitionPublic]:
    definitions = session.exec(
        select(WorkflowDefinition)
        .where(WorkflowDefinition.tenant_id == tenant_context.tenant_id)
        .order_by(WorkflowDefinition.created_at)
    ).all()
    return [definition_public(session=session, definition=item) for item in definitions]


@router.post("/definitions", response_model=WorkflowDefinitionPublic)
def create_definition(
    definition_in: WorkflowDefinitionCreate,
    session: SessionDep,
    tenant_context: CurrentTenant,
    manager: DefinitionManager,
) -> WorkflowDefinitionPublic:
    validate_definition_input(
        bpmn_xml=definition_in.bpmn_xml,
        process_id=definition_in.process_id,
        task_assignments=definition_in.task_assignments,
    )
    duplicate = session.exec(
        select(WorkflowDefinition).where(
            WorkflowDefinition.tenant_id == tenant_context.tenant_id,
            WorkflowDefinition.code == definition_in.code,
        )
    ).first()
    if duplicate:
        raise HTTPException(status_code=409, detail="Workflow code already exists")
    definition = WorkflowDefinition(
        tenant_id=tenant_context.tenant_id,
        code=definition_in.code,
        name=definition_in.name,
        description=definition_in.description,
        created_by=manager.id,
    )
    session.add(definition)
    session.flush()
    version = WorkflowDefinitionVersion(
        tenant_id=tenant_context.tenant_id,
        definition_id=definition.id,
        version=1,
        process_id=definition_in.process_id,
        bpmn_xml=definition_in.bpmn_xml,
        task_assignments=definition_in.task_assignments,
        timeout_hours=definition_in.timeout_hours,
        created_by=manager.id,
    )
    session.add(version)
    session.commit()
    session.refresh(definition)
    return definition_public(session=session, definition=definition)


@router.post(
    "/definitions/{definition_id}/versions", response_model=WorkflowVersionPublic
)
def create_version(
    definition_id: uuid.UUID,
    version_in: WorkflowVersionCreate,
    session: SessionDep,
    tenant_context: CurrentTenant,
    manager: DefinitionManager,
) -> WorkflowVersionPublic:
    definition = get_definition(
        session=session,
        tenant_id=tenant_context.tenant_id,
        definition_id=definition_id,
    )
    validate_definition_input(
        bpmn_xml=version_in.bpmn_xml,
        process_id=version_in.process_id,
        task_assignments=version_in.task_assignments,
    )
    latest = session.exec(
        select(WorkflowDefinitionVersion.version)
        .where(
            WorkflowDefinitionVersion.tenant_id == tenant_context.tenant_id,
            WorkflowDefinitionVersion.definition_id == definition.id,
        )
        .order_by(col(WorkflowDefinitionVersion.version).desc())
    ).first()
    version = WorkflowDefinitionVersion(
        tenant_id=tenant_context.tenant_id,
        definition_id=definition.id,
        version=(latest or 0) + 1,
        process_id=version_in.process_id,
        bpmn_xml=version_in.bpmn_xml,
        task_assignments=version_in.task_assignments,
        timeout_hours=version_in.timeout_hours,
        created_by=manager.id,
    )
    session.add(version)
    session.commit()
    session.refresh(version)
    return version_public(version)


@router.post("/versions/{version_id}/publish", response_model=WorkflowVersionPublic)
def publish_version(
    version_id: uuid.UUID,
    session: SessionDep,
    tenant_context: CurrentTenant,
    _manager: DefinitionManager,
) -> WorkflowVersionPublic:
    version = get_version(
        session=session,
        tenant_id=tenant_context.tenant_id,
        version_id=version_id,
    )
    published_versions = session.exec(
        select(WorkflowDefinitionVersion).where(
            WorkflowDefinitionVersion.tenant_id == tenant_context.tenant_id,
            WorkflowDefinitionVersion.definition_id == version.definition_id,
            WorkflowDefinitionVersion.status == WorkflowVersionStatus.PUBLISHED,
        )
    ).all()
    for published in published_versions:
        published.status = WorkflowVersionStatus.RETIRED
        session.add(published)
    version.status = WorkflowVersionStatus.PUBLISHED
    version.published_at = get_datetime_utc()
    session.add(version)
    session.commit()
    session.refresh(version)
    return version_public(version)


@router.post("/instances", response_model=WorkflowInstancePublic)
def start_instance(
    request: WorkflowStartRequest,
    session: SessionDep,
    tenant_context: CurrentTenant,
    starter: InstanceStarter,
) -> WorkflowInstancePublic:
    definition = session.exec(
        select(WorkflowDefinition).where(
            WorkflowDefinition.tenant_id == tenant_context.tenant_id,
            WorkflowDefinition.code == request.definition_code,
        )
    ).first()
    if definition is None:
        raise HTTPException(status_code=404, detail="Workflow definition not found")
    version = session.exec(
        select(WorkflowDefinitionVersion)
        .where(
            WorkflowDefinitionVersion.tenant_id == tenant_context.tenant_id,
            WorkflowDefinitionVersion.definition_id == definition.id,
            WorkflowDefinitionVersion.status == WorkflowVersionStatus.PUBLISHED,
        )
        .order_by(col(WorkflowDefinitionVersion.version).desc())
    ).first()
    if version is None:
        raise HTTPException(status_code=409, detail="Workflow has no published version")
    engine_state, ready_tasks, completed = start_workflow(
        bpmn_xml=version.bpmn_xml, process_id=version.process_id
    )
    now = get_datetime_utc()
    instance = WorkflowInstance(
        tenant_id=tenant_context.tenant_id,
        definition_version_id=version.id,
        title=request.title,
        business_type=request.business_type,
        business_id=request.business_id,
        form_data=request.form_data,
        engine_state=engine_state,
        status=(
            WorkflowInstanceStatus.COMPLETED
            if completed
            else WorkflowInstanceStatus.RUNNING
        ),
        started_by=starter.id,
        completed_at=now if completed else None,
    )
    session.add(instance)
    session.flush()
    sync_ready_tasks(
        session=session,
        instance=instance,
        version=version,
        ready_tasks=ready_tasks,
    )
    session.add(
        WorkflowAudit(
            tenant_id=tenant_context.tenant_id,
            instance_id=instance.id,
            action="start",
            actor_user_id=starter.id,
        )
    )
    session.commit()
    session.refresh(instance)
    return instance_public(session=session, instance=instance)


@router.get("/instances", response_model=list[WorkflowInstancePublic])
def list_instances(
    session: SessionDep,
    tenant_context: CurrentTenant,
    current_user: CurrentUser,
) -> list[WorkflowInstancePublic]:
    statement = select(WorkflowInstance).where(
        WorkflowInstance.tenant_id == tenant_context.tenant_id
    )
    if not can_manage_all_tasks(
        session=session,
        current_user=current_user,
        tenant_id=tenant_context.tenant_id,
    ):
        statement = statement.where(WorkflowInstance.started_by == current_user.id)
    instances = session.exec(
        statement.order_by(col(WorkflowInstance.created_at).desc())
    ).all()
    return [instance_public(session=session, instance=item) for item in instances]


@router.get("/instances/{instance_id}", response_model=WorkflowInstancePublic)
def read_instance(
    instance_id: uuid.UUID,
    session: SessionDep,
    tenant_context: CurrentTenant,
    current_user: CurrentUser,
) -> WorkflowInstancePublic:
    instance = get_instance(
        session=session,
        tenant_id=tenant_context.tenant_id,
        instance_id=instance_id,
    )
    if instance.started_by != current_user.id and not can_manage_all_tasks(
        session=session,
        current_user=current_user,
        tenant_id=tenant_context.tenant_id,
    ):
        task_access = any(
            assignment_matches_user(
                session=session,
                tenant_id=tenant_context.tenant_id,
                user_id=current_user.id,
                expression=task.assignment_expression,
                starter_user_id=instance.started_by,
            )
            for task in session.exec(
                select(WorkflowTask).where(
                    WorkflowTask.tenant_id == tenant_context.tenant_id,
                    WorkflowTask.instance_id == instance.id,
                )
            ).all()
        )
        if not task_access:
            raise HTTPException(status_code=403, detail="Workflow access denied")
    return instance_public(session=session, instance=instance)


@router.post("/instances/{instance_id}/withdraw", response_model=WorkflowInstancePublic)
def withdraw_instance(
    instance_id: uuid.UUID,
    session: SessionDep,
    tenant_context: CurrentTenant,
    current_user: CurrentUser,
) -> WorkflowInstancePublic:
    instance = get_instance(
        session=session,
        tenant_id=tenant_context.tenant_id,
        instance_id=instance_id,
    )
    if instance.started_by != current_user.id:
        raise HTTPException(status_code=403, detail="Only the starter can withdraw")
    if instance.status != WorkflowInstanceStatus.RUNNING:
        raise HTTPException(status_code=409, detail="Workflow is not running")
    now = get_datetime_utc()
    instance.status = WorkflowInstanceStatus.WITHDRAWN
    instance.updated_at = now
    instance.completed_at = now
    for task in session.exec(
        select(WorkflowTask).where(
            WorkflowTask.tenant_id == tenant_context.tenant_id,
            WorkflowTask.instance_id == instance.id,
            WorkflowTask.status == WorkflowTaskStatus.PENDING,
        )
    ).all():
        task.status = WorkflowTaskStatus.CANCELLED
        task.completed_at = now
        session.add(task)
    session.add(instance)
    session.add(
        WorkflowAudit(
            tenant_id=tenant_context.tenant_id,
            instance_id=instance.id,
            action="withdraw",
            actor_user_id=current_user.id,
        )
    )
    session.commit()
    session.refresh(instance)
    return instance_public(session=session, instance=instance)


@router.get("/tasks", response_model=list[WorkflowTaskPublic])
def list_tasks(
    session: SessionDep,
    tenant_context: CurrentTenant,
    current_user: CurrentUser,
    overdue: Annotated[bool | None, Query()] = None,
) -> list[WorkflowTaskPublic]:
    tasks = session.exec(
        select(WorkflowTask)
        .where(
            WorkflowTask.tenant_id == tenant_context.tenant_id,
            WorkflowTask.status == WorkflowTaskStatus.PENDING,
        )
        .order_by(WorkflowTask.created_at)
    ).all()
    manage_all = can_manage_all_tasks(
        session=session,
        current_user=current_user,
        tenant_id=tenant_context.tenant_id,
    )
    visible: list[WorkflowTaskPublic] = []
    for task in tasks:
        instance = get_instance(
            session=session,
            tenant_id=tenant_context.tenant_id,
            instance_id=task.instance_id,
        )
        if manage_all or assignment_matches_user(
            session=session,
            tenant_id=tenant_context.tenant_id,
            user_id=current_user.id,
            expression=task.assignment_expression,
            starter_user_id=instance.started_by,
        ):
            public = task_public(task)
            if overdue is None or public.is_overdue == overdue:
                visible.append(public)
    return visible


@router.post("/tasks/{task_id}/actions", response_model=WorkflowInstancePublic)
def act_on_task(
    task_id: uuid.UUID,
    request: WorkflowTaskActionRequest,
    session: SessionDep,
    tenant_context: CurrentTenant,
    current_user: CurrentUser,
) -> WorkflowInstancePublic:
    task = get_task(
        session=session, tenant_id=tenant_context.tenant_id, task_id=task_id
    )
    instance = get_instance(
        session=session,
        tenant_id=tenant_context.tenant_id,
        instance_id=task.instance_id,
    )
    if task.status != WorkflowTaskStatus.PENDING:
        raise HTTPException(status_code=409, detail="Workflow task is not pending")
    if instance.status != WorkflowInstanceStatus.RUNNING:
        raise HTTPException(status_code=409, detail="Workflow is not running")
    if not can_act_on_task(
        session=session,
        current_user=current_user,
        tenant_id=tenant_context.tenant_id,
        task=task,
        instance=instance,
    ):
        raise HTTPException(status_code=403, detail="Workflow task access denied")

    if request.action in {"transfer", "cc"}:
        if request.target_user_id is None:
            raise HTTPException(status_code=422, detail="target_user_id is required")
        membership = session.get(
            TenantMembership, (request.target_user_id, tenant_context.tenant_id)
        )
        if membership is None or not membership.is_active:
            raise HTTPException(status_code=422, detail="Target user is not in tenant")
        if request.action == "transfer":
            previous = task.assignment_expression
            task.assignment_expression = f"user:{request.target_user_id}"
            session.add(task)
            detail = {"from": previous, "to": task.assignment_expression}
            kind = "task_transferred"
        else:
            existing_cc = session.exec(
                select(WorkflowCc).where(
                    WorkflowCc.task_id == task.id,
                    WorkflowCc.recipient_user_id == request.target_user_id,
                )
            ).first()
            if existing_cc is None:
                session.add(
                    WorkflowCc(
                        tenant_id=tenant_context.tenant_id,
                        task_id=task.id,
                        recipient_user_id=request.target_user_id,
                        created_by=current_user.id,
                    )
                )
            detail = {"recipient_user_id": str(request.target_user_id)}
            kind = "task_cc"
        add_notification(
            session=session,
            tenant_id=tenant_context.tenant_id,
            instance_id=instance.id,
            task_id=task.id,
            recipient_user_id=request.target_user_id,
            kind=kind,
            message=f"Workflow {request.action}: {task.name}",
        )
        session.add(
            WorkflowAudit(
                tenant_id=tenant_context.tenant_id,
                instance_id=instance.id,
                task_id=task.id,
                action=request.action,
                actor_user_id=current_user.id,
                comment=request.comment,
                detail=detail,
            )
        )
        session.commit()
        session.refresh(instance)
        return instance_public(session=session, instance=instance)

    now = get_datetime_utc()
    task.completed_at = now
    task.completed_by = current_user.id
    task.status = (
        WorkflowTaskStatus.APPROVED
        if request.action == "approve"
        else WorkflowTaskStatus.REJECTED
    )
    session.add(task)
    session.add(
        WorkflowAudit(
            tenant_id=tenant_context.tenant_id,
            instance_id=instance.id,
            task_id=task.id,
            action=request.action,
            actor_user_id=current_user.id,
            comment=request.comment,
        )
    )
    if request.action == "reject":
        instance.status = WorkflowInstanceStatus.REJECTED
        instance.completed_at = now
    else:
        try:
            engine_state, ready_tasks, completed = complete_workflow_task(
                engine_state=instance.engine_state,
                engine_task_id=task.engine_task_id,
            )
        except ValueError as exc:
            raise HTTPException(status_code=409, detail=str(exc))
        instance.engine_state = engine_state
        version = get_version(
            session=session,
            tenant_id=tenant_context.tenant_id,
            version_id=instance.definition_version_id,
        )
        sync_ready_tasks(
            session=session,
            instance=instance,
            version=version,
            ready_tasks=ready_tasks,
        )
        if completed:
            instance.status = WorkflowInstanceStatus.COMPLETED
            instance.completed_at = now
    instance.updated_at = now
    session.add(instance)
    session.commit()
    session.refresh(instance)
    return instance_public(session=session, instance=instance)
