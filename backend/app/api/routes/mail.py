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
from app.mail import get_template_params, render_template, send_mail
from app.models import (
    MailAccount,
    MailAccountCreate,
    MailAccountPublic,
    MailAccountsPublic,
    MailAccountUpdate,
    MailLog,
    MailLogPublic,
    MailLogsPublic,
    MailSendRequest,
    MailTemplate,
    MailTemplateCreate,
    MailTemplatePublic,
    MailTemplatesPublic,
    MailTemplateUpdate,
    get_datetime_utc,
)

router = APIRouter(prefix="/mail", tags=["mail"])


def mask_account(account: MailAccount) -> MailAccountPublic:
    data = MailAccountPublic.model_validate(account)
    if data.password:
        data.password = "******"
    return data


def ensure_account_code_unique(
    *,
    session: SessionDep,
    tenant_id: uuid.UUID,
    code: str,
    exclude_id: uuid.UUID | None = None,
) -> None:
    statement = select(MailAccount).where(
        MailAccount.tenant_id == tenant_id,
        MailAccount.code == code,
    )
    if exclude_id:
        statement = statement.where(MailAccount.id != exclude_id)
    if session.exec(statement).first():
        raise HTTPException(status_code=409, detail="Mail account code already exists")


def ensure_template_code_unique(
    *,
    session: SessionDep,
    tenant_id: uuid.UUID,
    code: str,
    exclude_id: uuid.UUID | None = None,
) -> None:
    statement = select(MailTemplate).where(
        MailTemplate.tenant_id == tenant_id,
        MailTemplate.code == code,
    )
    if exclude_id:
        statement = statement.where(MailTemplate.id != exclude_id)
    if session.exec(statement).first():
        raise HTTPException(status_code=409, detail="Mail template code already exists")


def clear_default_accounts(
    *,
    session: SessionDep,
    tenant_id: uuid.UUID,
    exclude_id: uuid.UUID | None = None,
) -> None:
    statement = select(MailAccount).where(
        MailAccount.tenant_id == tenant_id,
        MailAccount.is_default,
    )
    if exclude_id:
        statement = statement.where(MailAccount.id != exclude_id)
    for account in session.exec(statement).all():
        account.is_default = False
        account.updated_at = get_datetime_utc()
        session.add(account)


def get_template_account(
    *, session: SessionDep, template: MailTemplate
) -> MailAccount | None:
    if template.account_id:
        return session.exec(
            select(MailAccount).where(
                MailAccount.id == template.account_id,
                MailAccount.tenant_id == template.tenant_id,
            )
        ).first()
    return session.exec(
        select(MailAccount)
        .where(
            MailAccount.tenant_id == template.tenant_id,
            MailAccount.is_default,
            MailAccount.is_active,
        )
        .order_by(col(MailAccount.created_at))
    ).first()


def validate_template_params(
    *, template: MailTemplate, template_params: dict[str, str]
) -> None:
    required = [
        param
        for param in get_template_params(template.title, template.content).split(",")
        if param
    ]
    missing = [param for param in required if not template_params.get(param)]
    if missing:
        raise HTTPException(
            status_code=400,
            detail=f"Missing template parameters: {', '.join(missing)}",
        )


def create_mail_log(
    *,
    session: SessionDep,
    tenant_id: uuid.UUID,
    account: MailAccount | None,
    template: MailTemplate | None,
    to_email: str,
    title: str,
    content: str,
    params: dict[str, str] | None,
    status: str,
    code: str,
    message: str,
    message_id: str | None = None,
    from_name: str | None = None,
) -> MailLog:
    log = MailLog(
        tenant_id=tenant_id,
        account_id=account.id if account else None,
        account_code=account.code if account else None,
        account_name=account.name if account else None,
        template_id=template.id if template else None,
        template_code=template.code if template else None,
        template_name=template.name if template else None,
        from_email=str(account.email) if account else "",
        from_name=from_name or (account.name if account else None),
        to_email=to_email,
        title=title,
        content=content,
        template_params=(
            json.dumps(params, ensure_ascii=False, sort_keys=True) if params else None
        ),
        send_status=status,
        sent_at=get_datetime_utc(),
        message_id=message_id,
        send_code=code,
        send_message=message,
    )
    session.add(log)
    session.commit()
    session.refresh(log)
    return log


def send_with_account(
    *,
    session: SessionDep,
    tenant_id: uuid.UUID,
    account: MailAccount | None,
    template: MailTemplate | None,
    to_email: str,
    title: str,
    content: str,
    params: dict[str, str] | None,
    from_name: str | None = None,
) -> MailLog:
    if not account:
        return create_mail_log(
            session=session,
            tenant_id=tenant_id,
            account=None,
            template=template,
            to_email=to_email,
            title=title,
            content=content,
            params=params,
            status="failed",
            code="ACCOUNT_NOT_FOUND",
            message="No active default mail account is available.",
            from_name=from_name,
        )
    if not account.is_active:
        return create_mail_log(
            session=session,
            tenant_id=tenant_id,
            account=account,
            template=template,
            to_email=to_email,
            title=title,
            content=content,
            params=params,
            status="failed",
            code="ACCOUNT_DISABLED",
            message="The selected mail account is disabled.",
            from_name=from_name,
        )

    try:
        message_id = send_mail(
            account=account,
            to_email=to_email,
            subject=title,
            html_content=content,
            from_name=from_name,
        )
    except Exception as exc:
        return create_mail_log(
            session=session,
            tenant_id=tenant_id,
            account=account,
            template=template,
            to_email=to_email,
            title=title,
            content=content,
            params=params,
            status="failed",
            code="SMTP_ERROR",
            message=str(exc)[:2000],
            from_name=from_name,
        )
    return create_mail_log(
        session=session,
        tenant_id=tenant_id,
        account=account,
        template=template,
        to_email=to_email,
        title=title,
        content=content,
        params=params,
        status="success",
        code="SMTP_ACCEPTED",
        message="SMTP server accepted the message.",
        message_id=message_id,
        from_name=from_name,
    )


@router.get(
    "/accounts",
    dependencies=[Depends(require_permission("system:mail-account:list"))],
    response_model=MailAccountsPublic,
)
def read_mail_accounts(
    session: SessionDep,
    tenant_context: CurrentTenant,
    page: int = 1,
    page_size: int = 20,
    keyword: str | None = None,
    is_active: bool | None = None,
) -> Any:
    page, page_size = normalize_pagination(page=page, page_size=page_size)
    filters = [MailAccount.tenant_id == tenant_context.tenant_id]
    if keyword:
        pattern = f"%{keyword}%"
        filters.append(
            or_(
                col(MailAccount.name).ilike(pattern),
                col(MailAccount.code).ilike(pattern),
                col(MailAccount.email).ilike(pattern),
                col(MailAccount.host).ilike(pattern),
            )
        )
    if is_active is not None:
        filters.append(MailAccount.is_active == is_active)
    count_statement = select(func.count()).select_from(MailAccount)
    if filters:
        count_statement = count_statement.where(*filters)
    count = session.exec(count_statement).one()
    statement = select(MailAccount)
    if filters:
        statement = statement.where(*filters)
    accounts = session.exec(
        statement.order_by(
            col(MailAccount.is_default).desc(),
            col(MailAccount.created_at),
        )
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()
    return MailAccountsPublic(
        items=[mask_account(account) for account in accounts],
        total=count,
        page=page,
        page_size=page_size,
    )


@router.get(
    "/accounts/simple",
    dependencies=[Depends(require_permission("system:mail-template:list"))],
    response_model=list[MailAccountPublic],
)
def read_simple_mail_accounts(
    session: SessionDep,
    tenant_context: CurrentTenant,
) -> Any:
    accounts = session.exec(
        select(MailAccount)
        .where(
            MailAccount.tenant_id == tenant_context.tenant_id,
            MailAccount.is_active,
        )
        .order_by(col(MailAccount.is_default).desc(), col(MailAccount.name))
    ).all()
    return [mask_account(account) for account in accounts]


@router.post(
    "/accounts",
    dependencies=[Depends(require_permission("system:mail-account:create"))],
    response_model=MailAccountPublic,
)
def create_mail_account(
    *,
    session: SessionDep,
    tenant_context: CurrentTenant,
    account_in: MailAccountCreate,
) -> MailAccountPublic:
    ensure_account_code_unique(
        session=session,
        tenant_id=tenant_context.tenant_id,
        code=account_in.code,
    )
    account = MailAccount.model_validate(
        account_in,
        update={"tenant_id": tenant_context.tenant_id},
    )
    if account.is_default:
        clear_default_accounts(
            session=session,
            tenant_id=tenant_context.tenant_id,
        )
    session.add(account)
    session.commit()
    session.refresh(account)
    return mask_account(account)


@router.patch(
    "/accounts/{account_id}",
    dependencies=[Depends(require_permission("system:mail-account:update"))],
    response_model=MailAccountPublic,
)
def update_mail_account(
    *,
    session: SessionDep,
    tenant_context: CurrentTenant,
    account_id: uuid.UUID,
    account_in: MailAccountUpdate,
) -> MailAccountPublic:
    account = session.exec(
        select(MailAccount).where(
            MailAccount.id == account_id,
            MailAccount.tenant_id == tenant_context.tenant_id,
        )
    ).first()
    if not account:
        raise HTTPException(status_code=404, detail="Mail account not found")
    update_data = account_in.model_dump(exclude_unset=True)
    if "code" in update_data and update_data["code"] != account.code:
        ensure_account_code_unique(
            session=session,
            tenant_id=tenant_context.tenant_id,
            code=update_data["code"],
            exclude_id=account.id,
        )
    if update_data.get("password") in {"", "******"}:
        update_data.pop("password")
    if update_data.get("is_default"):
        clear_default_accounts(
            session=session,
            tenant_id=tenant_context.tenant_id,
            exclude_id=account.id,
        )
    account.sqlmodel_update(update_data)
    account.updated_at = get_datetime_utc()
    session.add(account)
    session.commit()
    session.refresh(account)
    return mask_account(account)


@router.delete(
    "/accounts/{account_id}",
    dependencies=[Depends(require_permission("system:mail-account:delete"))],
    status_code=204,
)
def delete_mail_account(
    session: SessionDep,
    tenant_context: CurrentTenant,
    account_id: uuid.UUID,
) -> None:
    account = session.exec(
        select(MailAccount).where(
            MailAccount.id == account_id,
            MailAccount.tenant_id == tenant_context.tenant_id,
        )
    ).first()
    if not account:
        raise HTTPException(status_code=404, detail="Mail account not found")
    if account.is_default:
        raise HTTPException(
            status_code=400, detail="Cannot delete default mail account"
        )
    if session.exec(
        select(MailTemplate).where(
            MailTemplate.tenant_id == tenant_context.tenant_id,
            MailTemplate.account_id == account_id,
        )
    ).first():
        raise HTTPException(status_code=400, detail="Mail account is used by templates")
    for mail_log in session.exec(
        select(MailLog).where(
            MailLog.tenant_id == tenant_context.tenant_id,
            MailLog.account_id == account_id,
        )
    ).all():
        mail_log.account_id = None
        session.add(mail_log)
    session.delete(account)
    session.commit()


@router.get(
    "/templates",
    dependencies=[Depends(require_permission("system:mail-template:list"))],
    response_model=MailTemplatesPublic,
)
def read_mail_templates(
    session: SessionDep,
    tenant_context: CurrentTenant,
    page: int = 1,
    page_size: int = 20,
    keyword: str | None = None,
    account_id: uuid.UUID | None = None,
    is_active: bool | None = None,
) -> Any:
    page, page_size = normalize_pagination(page=page, page_size=page_size)
    filters = [MailTemplate.tenant_id == tenant_context.tenant_id]
    if keyword:
        pattern = f"%{keyword}%"
        filters.append(
            or_(
                col(MailTemplate.name).ilike(pattern),
                col(MailTemplate.code).ilike(pattern),
                col(MailTemplate.title).ilike(pattern),
                col(MailTemplate.content).ilike(pattern),
            )
        )
    if account_id:
        filters.append(MailTemplate.account_id == account_id)
    if is_active is not None:
        filters.append(MailTemplate.is_active == is_active)
    count_statement = select(func.count()).select_from(MailTemplate)
    if filters:
        count_statement = count_statement.where(*filters)
    count = session.exec(count_statement).one()
    statement = select(MailTemplate)
    if filters:
        statement = statement.where(*filters)
    templates = session.exec(
        statement.order_by(col(MailTemplate.updated_at).desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()
    return MailTemplatesPublic(
        items=[MailTemplatePublic.model_validate(template) for template in templates],
        total=count,
        page=page,
        page_size=page_size,
    )


@router.post(
    "/templates",
    dependencies=[Depends(require_permission("system:mail-template:create"))],
    response_model=MailTemplatePublic,
)
def create_mail_template(
    *,
    session: SessionDep,
    tenant_context: CurrentTenant,
    template_in: MailTemplateCreate,
) -> MailTemplatePublic:
    ensure_template_code_unique(
        session=session,
        tenant_id=tenant_context.tenant_id,
        code=template_in.code,
    )
    template = MailTemplate.model_validate(
        template_in,
        update={
            "params": get_template_params(template_in.title, template_in.content),
            "tenant_id": tenant_context.tenant_id,
        },
    )
    if template.account_id:
        account = session.exec(
            select(MailAccount).where(
                MailAccount.id == template.account_id,
                MailAccount.tenant_id == tenant_context.tenant_id,
            )
        ).first()
        if not account:
            raise HTTPException(status_code=400, detail="Mail account not found")
        template.account_code = account.code
    session.add(template)
    session.commit()
    session.refresh(template)
    return MailTemplatePublic.model_validate(template)


@router.patch(
    "/templates/{template_id}",
    dependencies=[Depends(require_permission("system:mail-template:update"))],
    response_model=MailTemplatePublic,
)
def update_mail_template(
    *,
    session: SessionDep,
    tenant_context: CurrentTenant,
    template_id: uuid.UUID,
    template_in: MailTemplateUpdate,
) -> MailTemplatePublic:
    template = session.exec(
        select(MailTemplate).where(
            MailTemplate.id == template_id,
            MailTemplate.tenant_id == tenant_context.tenant_id,
        )
    ).first()
    if not template:
        raise HTTPException(status_code=404, detail="Mail template not found")
    update_data = template_in.model_dump(exclude_unset=True)
    if "code" in update_data and update_data["code"] != template.code:
        ensure_template_code_unique(
            session=session,
            tenant_id=tenant_context.tenant_id,
            code=update_data["code"],
            exclude_id=template.id,
        )
    if "account_id" in update_data:
        account_id = update_data["account_id"]
        if account_id:
            account = session.exec(
                select(MailAccount).where(
                    MailAccount.id == account_id,
                    MailAccount.tenant_id == tenant_context.tenant_id,
                )
            ).first()
            if not account:
                raise HTTPException(status_code=400, detail="Mail account not found")
            update_data["account_code"] = account.code
        else:
            update_data["account_code"] = None
    title = update_data.get("title", template.title)
    content = update_data.get("content", template.content)
    update_data["params"] = get_template_params(title, content)
    template.sqlmodel_update(update_data)
    template.updated_at = get_datetime_utc()
    session.add(template)
    session.commit()
    session.refresh(template)
    return MailTemplatePublic.model_validate(template)


@router.delete(
    "/templates/{template_id}",
    dependencies=[Depends(require_permission("system:mail-template:delete"))],
    status_code=204,
)
def delete_mail_template(
    session: SessionDep,
    tenant_context: CurrentTenant,
    template_id: uuid.UUID,
) -> Response:
    template = session.exec(
        select(MailTemplate).where(
            MailTemplate.id == template_id,
            MailTemplate.tenant_id == tenant_context.tenant_id,
        )
    ).first()
    if not template:
        raise HTTPException(status_code=404, detail="Mail template not found")
    for mail_log in session.exec(
        select(MailLog).where(
            MailLog.tenant_id == tenant_context.tenant_id,
            MailLog.template_id == template_id,
        )
    ).all():
        mail_log.template_id = None
        session.add(mail_log)
    session.delete(template)
    session.commit()
    return Response(status_code=204)


@router.post(
    "/templates/{template_id}/send-test",
    dependencies=[Depends(require_permission("system:mail-template:send"))],
    response_model=MailLogPublic,
)
def send_test_mail(
    *,
    session: SessionDep,
    tenant_context: CurrentTenant,
    template_id: uuid.UUID,
    send_in: MailSendRequest,
) -> MailLogPublic:
    template = session.exec(
        select(MailTemplate).where(
            MailTemplate.id == template_id,
            MailTemplate.tenant_id == tenant_context.tenant_id,
        )
    ).first()
    if not template:
        raise HTTPException(status_code=404, detail="Mail template not found")
    if not template.is_active:
        raise HTTPException(status_code=400, detail="Mail template is disabled")
    validate_template_params(template=template, template_params=send_in.template_params)
    account = get_template_account(session=session, template=template)
    return MailLogPublic.model_validate(
        send_with_account(
            session=session,
            tenant_id=tenant_context.tenant_id,
            account=account,
            template=template,
            to_email=str(send_in.to_email),
            title=render_template(template.title, send_in.template_params),
            content=render_template(template.content, send_in.template_params),
            params=send_in.template_params,
            from_name=template.nickname,
        )
    )


@router.get(
    "/logs",
    dependencies=[Depends(require_permission("system:mail-log:list"))],
    response_model=MailLogsPublic,
)
def read_mail_logs(
    session: SessionDep,
    tenant_context: CurrentTenant,
    page: int = 1,
    page_size: int = 20,
    keyword: str | None = None,
    account_id: uuid.UUID | None = None,
    template_id: uuid.UUID | None = None,
    to_email: str | None = None,
    send_status: str | None = None,
) -> Any:
    page, page_size = normalize_pagination(page=page, page_size=page_size)
    filters = [MailLog.tenant_id == tenant_context.tenant_id]
    if keyword:
        pattern = f"%{keyword}%"
        filters.append(
            or_(
                col(MailLog.to_email).ilike(pattern),
                col(MailLog.title).ilike(pattern),
                col(MailLog.template_code).ilike(pattern),
                col(MailLog.template_name).ilike(pattern),
                col(MailLog.account_code).ilike(pattern),
            )
        )
    if to_email:
        filters.append(col(MailLog.to_email).ilike(f"%{to_email}%"))
    if account_id:
        filters.append(MailLog.account_id == account_id)
    if template_id:
        filters.append(MailLog.template_id == template_id)
    if send_status:
        filters.append(MailLog.send_status == send_status)
    count_statement = select(func.count()).select_from(MailLog)
    if filters:
        count_statement = count_statement.where(*filters)
    count = session.exec(count_statement).one()
    statement = select(MailLog)
    if filters:
        statement = statement.where(*filters)
    logs = session.exec(
        statement.order_by(col(MailLog.created_at).desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()
    return MailLogsPublic(
        items=[MailLogPublic.model_validate(log) for log in logs],
        total=count,
        page=page,
        page_size=page_size,
    )


@router.post(
    "/logs/{log_id}/resend",
    dependencies=[Depends(require_permission("system:mail-log:resend"))],
    response_model=MailLogPublic,
)
def resend_mail_log(
    *,
    session: SessionDep,
    tenant_context: CurrentTenant,
    log_id: uuid.UUID,
) -> MailLogPublic:
    log = session.exec(
        select(MailLog).where(
            MailLog.id == log_id,
            MailLog.tenant_id == tenant_context.tenant_id,
        )
    ).first()
    if not log:
        raise HTTPException(status_code=404, detail="Mail log not found")
    account = (
        session.exec(
            select(MailAccount).where(
                MailAccount.id == log.account_id,
                MailAccount.tenant_id == tenant_context.tenant_id,
            )
        ).first()
        if log.account_id
        else None
    )
    return MailLogPublic.model_validate(
        send_with_account(
            session=session,
            tenant_id=tenant_context.tenant_id,
            account=account,
            template=None,
            to_email=log.to_email,
            title=log.title,
            content=log.content,
            params=json.loads(log.template_params) if log.template_params else None,
            from_name=log.from_name,
        )
    )
