import uuid

from fastapi.testclient import TestClient
from sqlmodel import Session, delete, select

from app.api.routes.workflows import assignment_matches_user
from app.core.config import settings
from app.core.tenancy import DEFAULT_TENANT_ID
from app.models import (
    Department,
    Post,
    Role,
    Tenant,
    TenantMembership,
    User,
    UserPost,
    UserRole,
    UserSession,
    WorkflowAudit,
    WorkflowCc,
    WorkflowDefinition,
    WorkflowDefinitionVersion,
    WorkflowInstance,
    WorkflowNotification,
    WorkflowTask,
)
from tests.utils.utils import get_superuser_token_headers, random_lower_string

BPMN_XML = """<definitions xmlns="http://www.omg.org/spec/BPMN/20100524/MODEL" targetNamespace="https://example.test/bpmn">
  <process id="leave_approval" isExecutable="true">
    <startEvent id="start" name="Submit" />
    <userTask id="manager_approval" name="Manager approval" />
    <endEvent id="end" name="Completed" />
    <sequenceFlow id="flow_1" sourceRef="start" targetRef="manager_approval" />
    <sequenceFlow id="flow_2" sourceRef="manager_approval" targetRef="end" />
  </process>
</definitions>"""


def cleanup_workflows(db: Session, definition_code: str) -> None:
    definition = db.exec(
        select(WorkflowDefinition).where(WorkflowDefinition.code == definition_code)
    ).first()
    if definition is None:
        return
    version_ids = db.exec(
        select(WorkflowDefinitionVersion.id).where(
            WorkflowDefinitionVersion.definition_id == definition.id
        )
    ).all()
    instance_ids = db.exec(
        select(WorkflowInstance.id).where(
            WorkflowInstance.definition_version_id.in_(version_ids)
        )
    ).all()
    task_ids = db.exec(
        select(WorkflowTask.id).where(WorkflowTask.instance_id.in_(instance_ids))
    ).all()
    db.exec(
        delete(WorkflowNotification).where(
            WorkflowNotification.instance_id.in_(instance_ids)
        )
    )
    db.exec(delete(WorkflowCc).where(WorkflowCc.task_id.in_(task_ids)))
    db.exec(delete(WorkflowAudit).where(WorkflowAudit.instance_id.in_(instance_ids)))
    db.exec(delete(WorkflowTask).where(WorkflowTask.instance_id.in_(instance_ids)))
    db.exec(
        delete(WorkflowInstance).where(
            WorkflowInstance.definition_version_id.in_(version_ids)
        )
    )
    db.exec(
        delete(WorkflowDefinitionVersion).where(
            WorkflowDefinitionVersion.definition_id == definition.id
        )
    )
    db.delete(definition)
    db.commit()


def test_bpm_module_is_disabled_by_default(
    client: TestClient, superuser_token_headers: dict[str, str]
) -> None:
    original = settings.BPM_ENABLED
    settings.BPM_ENABLED = False
    try:
        response = client.get(
            f"{settings.API_V1_STR}/workflows/tasks",
            headers=superuser_token_headers,
        )
        assert response.status_code == 404
    finally:
        settings.BPM_ENABLED = original


def test_workflow_definition_lifecycle_and_actions(
    client: TestClient, db: Session
) -> None:
    original = settings.BPM_ENABLED
    settings.BPM_ENABLED = True
    headers = get_superuser_token_headers(client)
    current_user = db.exec(
        select(User).where(User.email == settings.FIRST_SUPERUSER)
    ).one()
    code = f"leave-{random_lower_string()}"
    try:
        invalid_response = client.post(
            f"{settings.API_V1_STR}/workflows/definitions",
            headers=headers,
            json={
                "code": f"invalid-{code}",
                "name": "Invalid",
                "process_id": "missing",
                "bpmn_xml": "<invalid />",
            },
        )
        assert invalid_response.status_code == 422

        create_response = client.post(
            f"{settings.API_V1_STR}/workflows/definitions",
            headers=headers,
            json={
                "code": code,
                "name": "Leave approval",
                "description": "BPM POC",
                "process_id": "leave_approval",
                "bpmn_xml": BPMN_XML,
                "task_assignments": {"manager_approval": "role:super_admin"},
                "timeout_hours": 1,
            },
        )
        assert create_response.status_code == 200, create_response.text
        definition = create_response.json()
        assert definition["versions"][0]["status"] == "draft"

        version_response = client.post(
            f"{settings.API_V1_STR}/workflows/definitions/{definition['id']}/versions",
            headers=headers,
            json={
                "process_id": "leave_approval",
                "bpmn_xml": BPMN_XML,
                "task_assignments": {"manager_approval": "starter"},
                "timeout_hours": 2,
            },
        )
        assert version_response.status_code == 200
        assert version_response.json()["version"] == 2
        version_id = version_response.json()["id"]

        publish_response = client.post(
            f"{settings.API_V1_STR}/workflows/versions/{version_id}/publish",
            headers=headers,
        )
        assert publish_response.status_code == 200
        assert publish_response.json()["status"] == "published"

        start_response = client.post(
            f"{settings.API_V1_STR}/workflows/instances",
            headers=headers,
            json={
                "definition_code": code,
                "title": "Annual leave",
                "business_type": "leave_request",
                "business_id": "LEAVE-001",
                "form_data": {"days": 2, "reason": "Vacation"},
            },
        )
        assert start_response.status_code == 200, start_response.text
        instance = start_response.json()
        assert instance["status"] == "running"
        assert instance["form_data"]["days"] == 2
        assert len(instance["tasks"]) == 1
        assert instance["tasks"][0]["due_at"] is not None
        task_id = instance["tasks"][0]["id"]

        task_list = client.get(
            f"{settings.API_V1_STR}/workflows/tasks", headers=headers
        )
        assert task_list.status_code == 200
        assert task_id in {task["id"] for task in task_list.json()}

        cc_response = client.post(
            f"{settings.API_V1_STR}/workflows/tasks/{task_id}/actions",
            headers=headers,
            json={"action": "cc", "target_user_id": str(current_user.id)},
        )
        assert cc_response.status_code == 200
        transfer_response = client.post(
            f"{settings.API_V1_STR}/workflows/tasks/{task_id}/actions",
            headers=headers,
            json={"action": "transfer", "target_user_id": str(current_user.id)},
        )
        assert transfer_response.status_code == 200
        assert (
            transfer_response.json()["tasks"][0]["assignment_expression"]
            == f"user:{current_user.id}"
        )

        approve_response = client.post(
            f"{settings.API_V1_STR}/workflows/tasks/{task_id}/actions",
            headers=headers,
            json={"action": "approve", "comment": "Approved"},
        )
        assert approve_response.status_code == 200, approve_response.text
        assert approve_response.json()["status"] == "completed"
        assert [item["action"] for item in approve_response.json()["audits"]] == [
            "start",
            "cc",
            "transfer",
            "approve",
        ]
        assert db.exec(
            select(WorkflowNotification).where(
                WorkflowNotification.instance_id == uuid.UUID(instance["id"])
            )
        ).all()

        withdraw_start = client.post(
            f"{settings.API_V1_STR}/workflows/instances",
            headers=headers,
            json={"definition_code": code, "title": "Withdraw me"},
        )
        withdraw_response = client.post(
            f"{settings.API_V1_STR}/workflows/instances/{withdraw_start.json()['id']}/withdraw",
            headers=headers,
        )
        assert withdraw_response.status_code == 200
        assert withdraw_response.json()["status"] == "withdrawn"

        reject_start = client.post(
            f"{settings.API_V1_STR}/workflows/instances",
            headers=headers,
            json={"definition_code": code, "title": "Reject me"},
        )
        reject_task_id = reject_start.json()["tasks"][0]["id"]
        reject_response = client.post(
            f"{settings.API_V1_STR}/workflows/tasks/{reject_task_id}/actions",
            headers=headers,
            json={"action": "reject", "comment": "Rejected"},
        )
        assert reject_response.status_code == 200
        assert reject_response.json()["status"] == "rejected"
    finally:
        cleanup_workflows(db, code)
        settings.BPM_ENABLED = original


def test_assignment_expressions_and_tenant_isolation(
    client: TestClient, db: Session
) -> None:
    original = settings.BPM_ENABLED
    settings.BPM_ENABLED = True
    headers = get_superuser_token_headers(client)
    current_user = db.exec(
        select(User).where(User.email == settings.FIRST_SUPERUSER)
    ).one()
    membership = db.get(TenantMembership, (current_user.id, DEFAULT_TENANT_ID))
    assert membership is not None and membership.department_id is not None
    department = db.get(Department, membership.department_id)
    role = db.exec(
        select(Role)
        .join(UserRole, UserRole.role_id == Role.id)
        .where(
            UserRole.user_id == current_user.id,
            UserRole.tenant_id == DEFAULT_TENANT_ID,
        )
    ).first()
    post = db.exec(
        select(Post).where(Post.tenant_id == DEFAULT_TENANT_ID, Post.is_active)
    ).first()
    assert department is not None and role is not None and post is not None
    user_post = db.get(UserPost, (current_user.id, post.id, DEFAULT_TENANT_ID))
    created_user_post = user_post is None
    if user_post is None:
        db.add(
            UserPost(
                user_id=current_user.id,
                post_id=post.id,
                tenant_id=DEFAULT_TENANT_ID,
            )
        )
        db.commit()

    tenant = Tenant(code=f"workflow-{random_lower_string()}", name="Workflow tenant")
    db.add(tenant)
    db.flush()
    db.add(
        TenantMembership(
            user_id=current_user.id,
            tenant_id=tenant.id,
            is_active=True,
        )
    )
    db.commit()
    code = f"isolated-{random_lower_string()}"
    try:
        for expression in [
            "starter",
            f"user:{current_user.id}",
            f"role:{role.code}",
            f"department:{department.code}",
            f"department:{department.id}",
            f"post:{post.code}",
        ]:
            assert assignment_matches_user(
                session=db,
                tenant_id=DEFAULT_TENANT_ID,
                user_id=current_user.id,
                expression=expression,
                starter_user_id=current_user.id,
            )

        create_response = client.post(
            f"{settings.API_V1_STR}/workflows/definitions",
            headers=headers,
            json={
                "code": code,
                "name": "Tenant isolation",
                "process_id": "leave_approval",
                "bpmn_xml": BPMN_XML,
            },
        )
        version_id = create_response.json()["versions"][0]["id"]
        client.post(
            f"{settings.API_V1_STR}/workflows/versions/{version_id}/publish",
            headers=headers,
        )
        instance_response = client.post(
            f"{settings.API_V1_STR}/workflows/instances",
            headers=headers,
            json={"definition_code": code, "title": "Isolated"},
        )
        instance_id = instance_response.json()["id"]

        switch_response = client.post(
            f"{settings.API_V1_STR}/tenants/switch",
            headers=headers,
            json={"tenant_id": str(tenant.id)},
        )
        assert switch_response.status_code == 200
        tenant_headers = {
            "Authorization": f"Bearer {switch_response.json()['access_token']}"
        }
        definitions_response = client.get(
            f"{settings.API_V1_STR}/workflows/definitions", headers=tenant_headers
        )
        assert definitions_response.status_code == 200
        assert definitions_response.json() == []
        cross_tenant_response = client.get(
            f"{settings.API_V1_STR}/workflows/instances/{instance_id}",
            headers=tenant_headers,
        )
        assert cross_tenant_response.status_code == 404
    finally:
        cleanup_workflows(db, code)
        db.exec(delete(UserSession).where(UserSession.tenant_id == tenant.id))
        db.exec(delete(TenantMembership).where(TenantMembership.tenant_id == tenant.id))
        db.delete(tenant)
        if created_user_post:
            db.exec(
                delete(UserPost).where(
                    UserPost.user_id == current_user.id,
                    UserPost.post_id == post.id,
                    UserPost.tenant_id == DEFAULT_TENANT_ID,
                )
            )
        db.commit()
        settings.BPM_ENABLED = original
