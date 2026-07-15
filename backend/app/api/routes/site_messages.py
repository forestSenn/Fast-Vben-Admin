import json
import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlmodel import col, func, or_, select

from app.api.deps import (
    CurrentTenant,
    SessionDep,
    normalize_pagination,
    require_permission,
)
from app.mail import get_template_params, render_template
from app.models import (
    SiteMessagePublic,
    SiteMessageSendRequest,
    SiteMessagesPublic,
    SiteMessageTemplate,
    SiteMessageTemplateCreate,
    SiteMessageTemplatePublic,
    SiteMessageTemplatesPublic,
    SiteMessageTemplateUpdate,
    TenantMembership,
    User,
    UserMessage,
    get_datetime_utc,
)

router = APIRouter(prefix="/site-messages", tags=["site-messages"])


def ensure_template_code_unique(
    *,
    session: SessionDep,
    tenant_id: uuid.UUID,
    code: str,
    exclude_id: uuid.UUID | None = None,
) -> None:
    statement = select(SiteMessageTemplate).where(
        SiteMessageTemplate.tenant_id == tenant_id,
        SiteMessageTemplate.code == code,
    )
    if exclude_id:
        statement = statement.where(SiteMessageTemplate.id != exclude_id)
    if session.exec(statement).first():
        raise HTTPException(
            status_code=409,
            detail="Site message template code already exists",
        )


def get_template_or_404(
    *,
    session: SessionDep,
    tenant_id: uuid.UUID,
    template_id: uuid.UUID,
) -> SiteMessageTemplate:
    template = session.exec(
        select(SiteMessageTemplate).where(
            SiteMessageTemplate.id == template_id,
            SiteMessageTemplate.tenant_id == tenant_id,
        )
    ).first()
    if template is None:
        raise HTTPException(status_code=404, detail="Site message template not found")
    return template


def validate_template_params(
    *, template: SiteMessageTemplate, template_params: dict[str, str]
) -> None:
    required = [param for param in template.params.split(",") if param]
    missing = [param for param in required if not template_params.get(param)]
    if missing:
        raise HTTPException(
            status_code=400,
            detail=f"Missing template parameters: {', '.join(missing)}",
        )


def to_site_message_public(
    *, message: UserMessage, user: User | None = None
) -> SiteMessagePublic:
    data = SiteMessagePublic.model_validate(message)
    if user:
        data.user_email = str(user.email)
        data.user_full_name = user.full_name
    return data


@router.get(
    "/templates",
    dependencies=[Depends(require_permission("system:site-message-template:list"))],
    response_model=SiteMessageTemplatesPublic,
)
def read_site_message_templates(
    session: SessionDep,
    tenant_context: CurrentTenant,
    page: int = 1,
    page_size: int = 20,
    keyword: str | None = None,
    type: str | None = None,
    is_active: bool | None = None,
) -> Any:
    page, page_size = normalize_pagination(page=page, page_size=page_size)
    filters = [SiteMessageTemplate.tenant_id == tenant_context.tenant_id]
    if keyword:
        pattern = f"%{keyword}%"
        filters.append(
            or_(
                col(SiteMessageTemplate.name).ilike(pattern),
                col(SiteMessageTemplate.code).ilike(pattern),
                col(SiteMessageTemplate.sender_name).ilike(pattern),
                col(SiteMessageTemplate.content).ilike(pattern),
            )
        )
    if type:
        filters.append(SiteMessageTemplate.type == type)
    if is_active is not None:
        filters.append(SiteMessageTemplate.is_active == is_active)

    count_statement = select(func.count()).select_from(SiteMessageTemplate)
    if filters:
        count_statement = count_statement.where(*filters)
    count = session.exec(count_statement).one()

    statement = select(SiteMessageTemplate)
    if filters:
        statement = statement.where(*filters)
    templates = session.exec(
        statement.order_by(col(SiteMessageTemplate.updated_at).desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()
    return SiteMessageTemplatesPublic(
        items=[
            SiteMessageTemplatePublic.model_validate(template) for template in templates
        ],
        total=count,
        page=page,
        page_size=page_size,
    )


@router.post(
    "/templates",
    dependencies=[Depends(require_permission("system:site-message-template:create"))],
    response_model=SiteMessageTemplatePublic,
)
def create_site_message_template(
    *,
    session: SessionDep,
    tenant_context: CurrentTenant,
    template_in: SiteMessageTemplateCreate,
) -> SiteMessageTemplatePublic:
    ensure_template_code_unique(
        session=session,
        tenant_id=tenant_context.tenant_id,
        code=template_in.code,
    )
    template = SiteMessageTemplate.model_validate(
        template_in,
        update={
            "params": get_template_params(template_in.content),
            "tenant_id": tenant_context.tenant_id,
        },
    )
    session.add(template)
    session.commit()
    session.refresh(template)
    return SiteMessageTemplatePublic.model_validate(template)


@router.patch(
    "/templates/{template_id}",
    dependencies=[Depends(require_permission("system:site-message-template:update"))],
    response_model=SiteMessageTemplatePublic,
)
def update_site_message_template(
    *,
    session: SessionDep,
    tenant_context: CurrentTenant,
    template_id: uuid.UUID,
    template_in: SiteMessageTemplateUpdate,
) -> SiteMessageTemplatePublic:
    template = get_template_or_404(
        session=session,
        tenant_id=tenant_context.tenant_id,
        template_id=template_id,
    )
    update_data = template_in.model_dump(exclude_unset=True)
    if "code" in update_data and update_data["code"] != template.code:
        ensure_template_code_unique(
            session=session,
            tenant_id=tenant_context.tenant_id,
            code=update_data["code"],
            exclude_id=template.id,
        )
    if "content" in update_data:
        update_data["params"] = get_template_params(update_data["content"])
    template.sqlmodel_update(update_data)
    template.updated_at = get_datetime_utc()
    session.add(template)
    session.commit()
    session.refresh(template)
    return SiteMessageTemplatePublic.model_validate(template)


@router.delete(
    "/templates/{template_id}",
    dependencies=[Depends(require_permission("system:site-message-template:delete"))],
    status_code=204,
)
def delete_site_message_template(
    *,
    session: SessionDep,
    tenant_context: CurrentTenant,
    template_id: uuid.UUID,
) -> Response:
    template = get_template_or_404(
        session=session,
        tenant_id=tenant_context.tenant_id,
        template_id=template_id,
    )
    messages = session.exec(
        select(UserMessage).where(
            UserMessage.tenant_id == tenant_context.tenant_id,
            UserMessage.template_id == template_id,
        )
    ).all()
    for message in messages:
        message.template_id = None
        session.add(message)
    session.delete(template)
    session.commit()
    return Response(status_code=204)


@router.post(
    "/templates/{template_id}/send-test",
    dependencies=[Depends(require_permission("system:site-message-template:send"))],
    response_model=SiteMessagePublic,
)
def send_test_site_message(
    *,
    session: SessionDep,
    tenant_context: CurrentTenant,
    template_id: uuid.UUID,
    send_in: SiteMessageSendRequest,
) -> SiteMessagePublic:
    template = get_template_or_404(
        session=session,
        tenant_id=tenant_context.tenant_id,
        template_id=template_id,
    )
    if not template.is_active:
        raise HTTPException(status_code=400, detail="Site message template is disabled")
    user = session.exec(
        select(User)
        .join(TenantMembership, TenantMembership.user_id == User.id)
        .where(
            User.id == send_in.user_id,
            User.is_active,
            TenantMembership.tenant_id == tenant_context.tenant_id,
            TenantMembership.is_active,
        )
    ).first()
    if not user or not user.is_active:
        raise HTTPException(status_code=404, detail="User not found")
    validate_template_params(
        template=template,
        template_params=send_in.template_params,
    )
    content = render_template(template.content, send_in.template_params)
    message = UserMessage(
        tenant_id=tenant_context.tenant_id,
        user_id=user.id,
        template_id=template.id,
        template_code=template.code,
        template_name=template.name,
        sender_name=template.sender_name,
        template_params=json.dumps(
            send_in.template_params,
            ensure_ascii=False,
            sort_keys=True,
        ),
        title=template.name,
        content=content,
        type=template.type,
    )
    session.add(message)
    session.commit()
    session.refresh(message)
    return to_site_message_public(message=message, user=user)


@router.get(
    "/messages",
    dependencies=[Depends(require_permission("system:site-message:list"))],
    response_model=SiteMessagesPublic,
)
def read_site_messages(
    session: SessionDep,
    tenant_context: CurrentTenant,
    page: int = 1,
    page_size: int = 20,
    keyword: str | None = None,
    user_id: uuid.UUID | None = None,
    template_code: str | None = None,
    type: str | None = None,
    is_read: bool | None = None,
) -> Any:
    page, page_size = normalize_pagination(page=page, page_size=page_size)
    filters = [UserMessage.tenant_id == tenant_context.tenant_id]
    if keyword:
        pattern = f"%{keyword}%"
        filters.append(
            or_(
                col(UserMessage.title).ilike(pattern),
                col(UserMessage.content).ilike(pattern),
                col(UserMessage.template_code).ilike(pattern),
                col(UserMessage.sender_name).ilike(pattern),
            )
        )
    if user_id:
        filters.append(UserMessage.user_id == user_id)
    if template_code:
        filters.append(col(UserMessage.template_code).ilike(f"%{template_code}%"))
    if type:
        filters.append(UserMessage.type == type)
    if is_read is not None:
        filters.append(UserMessage.is_read == is_read)

    count_statement = select(func.count()).select_from(UserMessage)
    if filters:
        count_statement = count_statement.where(*filters)
    count = session.exec(count_statement).one()

    statement = select(UserMessage)
    if filters:
        statement = statement.where(*filters)
    messages = session.exec(
        statement.order_by(col(UserMessage.created_at).desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()
    users = {
        user.id: user
        for user in session.exec(
            select(User).where(User.id.in_([message.user_id for message in messages]))
        ).all()
    }
    return SiteMessagesPublic(
        items=[
            to_site_message_public(message=message, user=users.get(message.user_id))
            for message in messages
        ],
        total=count,
        page=page,
        page_size=page_size,
    )


@router.delete(
    "/messages/{message_id}",
    dependencies=[Depends(require_permission("system:site-message:delete"))],
    status_code=204,
)
def delete_site_message(
    *,
    session: SessionDep,
    tenant_context: CurrentTenant,
    message_id: uuid.UUID,
) -> Response:
    message = session.exec(
        select(UserMessage).where(
            UserMessage.id == message_id,
            UserMessage.tenant_id == tenant_context.tenant_id,
        )
    ).first()
    if not message:
        raise HTTPException(status_code=404, detail="Site message not found")
    session.delete(message)
    session.commit()
    return Response(status_code=204)
