import json
import re
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
from app.models import (
    SmsChannel,
    SmsChannelCreate,
    SmsChannelPublic,
    SmsChannelsPublic,
    SmsChannelUpdate,
    SmsDeliveryCallback,
    SmsLog,
    SmsLogPublic,
    SmsLogsPublic,
    SmsSendRequest,
    SmsTemplate,
    SmsTemplateCreate,
    SmsTemplatePublic,
    SmsTemplatesPublic,
    SmsTemplateUpdate,
    get_datetime_utc,
)

router = APIRouter(prefix="/sms", tags=["sms"])

SUPPORTED_SMS_PROVIDERS = {"debug", "aliyun", "tencent", "huawei"}
TEMPLATE_PARAM_PATTERN = re.compile(r"\{([A-Za-z_][A-Za-z0-9_]*)\}")


def mask_channel(channel: SmsChannel) -> SmsChannelPublic:
    data = SmsChannelPublic.model_validate(channel)
    if data.api_secret:
        data.api_secret = "******"
    return data


def ensure_supported_provider(provider: str) -> None:
    if provider not in SUPPORTED_SMS_PROVIDERS:
        raise HTTPException(status_code=400, detail="Unsupported SMS provider")


def ensure_channel_code_unique(
    *,
    session: SessionDep,
    tenant_id: uuid.UUID,
    code: str,
    exclude_id: uuid.UUID | None = None,
) -> None:
    statement = select(SmsChannel).where(
        SmsChannel.tenant_id == tenant_id,
        SmsChannel.code == code,
    )
    if exclude_id:
        statement = statement.where(SmsChannel.id != exclude_id)
    if session.exec(statement).first():
        raise HTTPException(status_code=409, detail="SMS channel code already exists")


def ensure_template_code_unique(
    *,
    session: SessionDep,
    tenant_id: uuid.UUID,
    code: str,
    exclude_id: uuid.UUID | None = None,
) -> None:
    statement = select(SmsTemplate).where(
        SmsTemplate.tenant_id == tenant_id,
        SmsTemplate.code == code,
    )
    if exclude_id:
        statement = statement.where(SmsTemplate.id != exclude_id)
    if session.exec(statement).first():
        raise HTTPException(status_code=409, detail="SMS template code already exists")


def clear_default_channels(
    *,
    session: SessionDep,
    tenant_id: uuid.UUID,
    exclude_id: uuid.UUID | None = None,
) -> None:
    statement = select(SmsChannel).where(
        SmsChannel.tenant_id == tenant_id,
        SmsChannel.is_default,
    )
    if exclude_id:
        statement = statement.where(SmsChannel.id != exclude_id)
    for channel in session.exec(statement).all():
        channel.is_default = False
        channel.updated_at = get_datetime_utc()
        session.add(channel)


def get_template_params(content: str) -> str:
    return ",".join(dict.fromkeys(TEMPLATE_PARAM_PATTERN.findall(content)))


def get_template_channel(
    *, session: SessionDep, template: SmsTemplate
) -> SmsChannel | None:
    if template.channel_id:
        return session.exec(
            select(SmsChannel).where(
                SmsChannel.id == template.channel_id,
                SmsChannel.tenant_id == template.tenant_id,
            )
        ).first()
    return session.exec(
        select(SmsChannel)
        .where(
            SmsChannel.tenant_id == template.tenant_id,
            SmsChannel.is_default,
            SmsChannel.is_active,
        )
        .order_by(col(SmsChannel.created_at))
    ).first()


def create_sms_log(
    *,
    session: SessionDep,
    channel: SmsChannel | None,
    template: SmsTemplate,
    mobile: str,
    content: str,
    params: dict[str, str],
    status: str,
    code: str,
    message: str,
) -> SmsLog:
    sms_log = SmsLog(
        tenant_id=template.tenant_id,
        channel_id=channel.id if channel else None,
        channel_code=channel.code if channel else template.channel_code,
        template_id=template.id,
        template_code=template.code,
        template_name=template.name,
        template_type=template.type,
        template_content=content,
        template_params=json.dumps(params, ensure_ascii=False, sort_keys=True),
        api_template_id=template.api_template_id,
        mobile=mobile,
        send_status=status,
        sent_at=get_datetime_utc(),
        api_send_code=code,
        api_send_message=message,
        api_request_id=str(uuid.uuid4()),
    )
    session.add(sms_log)
    session.commit()
    session.refresh(sms_log)
    return sms_log


@router.get(
    "/channels",
    dependencies=[Depends(require_permission("system:sms-channel:list"))],
    response_model=SmsChannelsPublic,
)
def read_sms_channels(
    session: SessionDep,
    tenant_context: CurrentTenant,
    page: int = 1,
    page_size: int = 20,
    keyword: str | None = None,
    provider: str | None = None,
    is_active: bool | None = None,
) -> Any:
    page, page_size = normalize_pagination(page=page, page_size=page_size)
    filters = [SmsChannel.tenant_id == tenant_context.tenant_id]
    if keyword:
        pattern = f"%{keyword}%"
        filters.append(
            or_(
                col(SmsChannel.name).ilike(pattern),
                col(SmsChannel.code).ilike(pattern),
                col(SmsChannel.signature).ilike(pattern),
            )
        )
    if provider:
        filters.append(SmsChannel.provider == provider)
    if is_active is not None:
        filters.append(SmsChannel.is_active == is_active)

    count_statement = select(func.count()).select_from(SmsChannel)
    if filters:
        count_statement = count_statement.where(*filters)
    count = session.exec(count_statement).one()

    statement = select(SmsChannel)
    if filters:
        statement = statement.where(*filters)
    channels = session.exec(
        statement.order_by(
            col(SmsChannel.is_default).desc(),
            col(SmsChannel.created_at),
        )
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()
    return SmsChannelsPublic(
        items=[mask_channel(channel) for channel in channels],
        total=count,
        page=page,
        page_size=page_size,
    )


@router.get(
    "/channels/simple",
    dependencies=[Depends(require_permission("system:sms-template:list"))],
    response_model=list[SmsChannelPublic],
)
def read_simple_sms_channels(
    session: SessionDep,
    tenant_context: CurrentTenant,
) -> Any:
    channels = session.exec(
        select(SmsChannel)
        .where(
            SmsChannel.tenant_id == tenant_context.tenant_id,
            SmsChannel.is_active,
        )
        .order_by(col(SmsChannel.is_default).desc(), col(SmsChannel.name))
    ).all()
    return [mask_channel(channel) for channel in channels]


@router.post(
    "/channels",
    dependencies=[Depends(require_permission("system:sms-channel:create"))],
    response_model=SmsChannelPublic,
)
def create_sms_channel(
    *,
    session: SessionDep,
    tenant_context: CurrentTenant,
    channel_in: SmsChannelCreate,
) -> SmsChannelPublic:
    ensure_supported_provider(channel_in.provider)
    ensure_channel_code_unique(
        session=session,
        tenant_id=tenant_context.tenant_id,
        code=channel_in.code,
    )
    channel = SmsChannel.model_validate(
        channel_in,
        update={"tenant_id": tenant_context.tenant_id},
    )
    if channel.is_default:
        clear_default_channels(
            session=session,
            tenant_id=tenant_context.tenant_id,
        )
    session.add(channel)
    session.commit()
    session.refresh(channel)
    return mask_channel(channel)


@router.patch(
    "/channels/{channel_id}",
    dependencies=[Depends(require_permission("system:sms-channel:update"))],
    response_model=SmsChannelPublic,
)
def update_sms_channel(
    *,
    session: SessionDep,
    tenant_context: CurrentTenant,
    channel_id: uuid.UUID,
    channel_in: SmsChannelUpdate,
) -> SmsChannelPublic:
    channel = session.exec(
        select(SmsChannel).where(
            SmsChannel.id == channel_id,
            SmsChannel.tenant_id == tenant_context.tenant_id,
        )
    ).first()
    if not channel:
        raise HTTPException(status_code=404, detail="SMS channel not found")

    update_data = channel_in.model_dump(exclude_unset=True)
    if "provider" in update_data and update_data["provider"] is not None:
        ensure_supported_provider(update_data["provider"])
    if "code" in update_data and update_data["code"] != channel.code:
        ensure_channel_code_unique(
            session=session,
            tenant_id=tenant_context.tenant_id,
            code=update_data["code"],
            exclude_id=channel.id,
        )
    if update_data.get("is_default"):
        clear_default_channels(
            session=session,
            tenant_id=tenant_context.tenant_id,
            exclude_id=channel.id,
        )

    channel.sqlmodel_update(update_data)
    channel.updated_at = get_datetime_utc()
    session.add(channel)
    session.commit()
    session.refresh(channel)
    return mask_channel(channel)


@router.delete(
    "/channels/{channel_id}",
    dependencies=[Depends(require_permission("system:sms-channel:delete"))],
    status_code=204,
)
def delete_sms_channel(
    session: SessionDep,
    tenant_context: CurrentTenant,
    channel_id: uuid.UUID,
) -> None:
    channel = session.exec(
        select(SmsChannel).where(
            SmsChannel.id == channel_id,
            SmsChannel.tenant_id == tenant_context.tenant_id,
        )
    ).first()
    if not channel:
        raise HTTPException(status_code=404, detail="SMS channel not found")
    if channel.is_default:
        raise HTTPException(status_code=400, detail="Cannot delete default SMS channel")
    if session.exec(
        select(SmsTemplate).where(
            SmsTemplate.tenant_id == tenant_context.tenant_id,
            SmsTemplate.channel_id == channel_id,
        )
    ).first():
        raise HTTPException(status_code=400, detail="SMS channel is used by templates")
    for sms_log in session.exec(
        select(SmsLog).where(
            SmsLog.tenant_id == tenant_context.tenant_id,
            SmsLog.channel_id == channel_id,
        )
    ).all():
        sms_log.channel_id = None
        session.add(sms_log)
    session.delete(channel)
    session.commit()
    return None


@router.get(
    "/templates",
    dependencies=[Depends(require_permission("system:sms-template:list"))],
    response_model=SmsTemplatesPublic,
)
def read_sms_templates(
    session: SessionDep,
    tenant_context: CurrentTenant,
    page: int = 1,
    page_size: int = 20,
    keyword: str | None = None,
    channel_id: uuid.UUID | None = None,
    is_active: bool | None = None,
    type: str | None = None,
) -> Any:
    page, page_size = normalize_pagination(page=page, page_size=page_size)
    filters = [SmsTemplate.tenant_id == tenant_context.tenant_id]
    if keyword:
        pattern = f"%{keyword}%"
        filters.append(
            or_(
                col(SmsTemplate.code).ilike(pattern),
                col(SmsTemplate.name).ilike(pattern),
                col(SmsTemplate.content).ilike(pattern),
            )
        )
    if channel_id:
        filters.append(SmsTemplate.channel_id == channel_id)
    if is_active is not None:
        filters.append(SmsTemplate.is_active == is_active)
    if type:
        filters.append(SmsTemplate.type == type)

    count_statement = select(func.count()).select_from(SmsTemplate)
    if filters:
        count_statement = count_statement.where(*filters)
    count = session.exec(count_statement).one()

    statement = select(SmsTemplate)
    if filters:
        statement = statement.where(*filters)
    templates = session.exec(
        statement.order_by(col(SmsTemplate.updated_at).desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()
    return SmsTemplatesPublic(
        items=[SmsTemplatePublic.model_validate(template) for template in templates],
        total=count,
        page=page,
        page_size=page_size,
    )


@router.post(
    "/templates",
    dependencies=[Depends(require_permission("system:sms-template:create"))],
    response_model=SmsTemplatePublic,
)
def create_sms_template(
    *,
    session: SessionDep,
    tenant_context: CurrentTenant,
    template_in: SmsTemplateCreate,
) -> SmsTemplatePublic:
    ensure_template_code_unique(
        session=session,
        tenant_id=tenant_context.tenant_id,
        code=template_in.code,
    )
    template = SmsTemplate.model_validate(
        template_in,
        update={
            "params": get_template_params(template_in.content),
            "tenant_id": tenant_context.tenant_id,
        },
    )
    if template.channel_id:
        channel = session.exec(
            select(SmsChannel).where(
                SmsChannel.id == template.channel_id,
                SmsChannel.tenant_id == tenant_context.tenant_id,
            )
        ).first()
        if not channel:
            raise HTTPException(status_code=400, detail="SMS channel not found")
        template.channel_code = channel.code
    session.add(template)
    session.commit()
    session.refresh(template)
    return SmsTemplatePublic.model_validate(template)


@router.patch(
    "/templates/{template_id}",
    dependencies=[Depends(require_permission("system:sms-template:update"))],
    response_model=SmsTemplatePublic,
)
def update_sms_template(
    *,
    session: SessionDep,
    tenant_context: CurrentTenant,
    template_id: uuid.UUID,
    template_in: SmsTemplateUpdate,
) -> SmsTemplatePublic:
    template = session.exec(
        select(SmsTemplate).where(
            SmsTemplate.id == template_id,
            SmsTemplate.tenant_id == tenant_context.tenant_id,
        )
    ).first()
    if not template:
        raise HTTPException(status_code=404, detail="SMS template not found")

    update_data = template_in.model_dump(exclude_unset=True)
    if "code" in update_data and update_data["code"] != template.code:
        ensure_template_code_unique(
            session=session,
            tenant_id=tenant_context.tenant_id,
            code=update_data["code"],
            exclude_id=template.id,
        )
    if "channel_id" in update_data:
        channel_id = update_data["channel_id"]
        if channel_id:
            channel = session.exec(
                select(SmsChannel).where(
                    SmsChannel.id == channel_id,
                    SmsChannel.tenant_id == tenant_context.tenant_id,
                )
            ).first()
            if not channel:
                raise HTTPException(status_code=400, detail="SMS channel not found")
            update_data["channel_code"] = channel.code
        else:
            update_data["channel_code"] = None
    if "content" in update_data:
        update_data["params"] = get_template_params(update_data["content"])

    template.sqlmodel_update(update_data)
    template.updated_at = get_datetime_utc()
    session.add(template)
    session.commit()
    session.refresh(template)
    return SmsTemplatePublic.model_validate(template)


@router.delete(
    "/templates/{template_id}",
    dependencies=[Depends(require_permission("system:sms-template:delete"))],
    status_code=204,
)
def delete_sms_template(
    session: SessionDep,
    tenant_context: CurrentTenant,
    template_id: uuid.UUID,
) -> Response:
    template = session.exec(
        select(SmsTemplate).where(
            SmsTemplate.id == template_id,
            SmsTemplate.tenant_id == tenant_context.tenant_id,
        )
    ).first()
    if not template:
        raise HTTPException(status_code=404, detail="SMS template not found")
    for sms_log in session.exec(
        select(SmsLog).where(
            SmsLog.tenant_id == tenant_context.tenant_id,
            SmsLog.template_id == template_id,
        )
    ).all():
        sms_log.template_id = None
        session.add(sms_log)
    session.delete(template)
    session.commit()
    return Response(status_code=204)


@router.post(
    "/templates/{template_id}/send-test",
    dependencies=[Depends(require_permission("system:sms-template:send"))],
    response_model=SmsLogPublic,
)
def send_test_sms(
    *,
    session: SessionDep,
    tenant_context: CurrentTenant,
    template_id: uuid.UUID,
    send_in: SmsSendRequest,
) -> SmsLogPublic:
    template = session.exec(
        select(SmsTemplate).where(
            SmsTemplate.id == template_id,
            SmsTemplate.tenant_id == tenant_context.tenant_id,
        )
    ).first()
    if not template:
        raise HTTPException(status_code=404, detail="SMS template not found")
    if not template.is_active:
        raise HTTPException(status_code=400, detail="SMS template is disabled")

    required_params = TEMPLATE_PARAM_PATTERN.findall(template.content)
    missing_params = [
        param
        for param in dict.fromkeys(required_params)
        if not send_in.template_params.get(param)
    ]
    if missing_params:
        raise HTTPException(
            status_code=400,
            detail=f"Missing template parameters: {', '.join(missing_params)}",
        )

    content = TEMPLATE_PARAM_PATTERN.sub(
        lambda match: send_in.template_params[match.group(1)],
        template.content,
    )
    channel = get_template_channel(session=session, template=template)
    if not channel:
        return SmsLogPublic.model_validate(
            create_sms_log(
                session=session,
                channel=None,
                template=template,
                mobile=send_in.mobile,
                content=content,
                params=send_in.template_params,
                status="failed",
                code="CHANNEL_NOT_FOUND",
                message="No active default SMS channel is available.",
            )
        )
    if not channel.is_active:
        return SmsLogPublic.model_validate(
            create_sms_log(
                session=session,
                channel=channel,
                template=template,
                mobile=send_in.mobile,
                content=content,
                params=send_in.template_params,
                status="failed",
                code="CHANNEL_DISABLED",
                message="The selected SMS channel is disabled.",
            )
        )
    if channel.provider != "debug":
        return SmsLogPublic.model_validate(
            create_sms_log(
                session=session,
                channel=channel,
                template=template,
                mobile=send_in.mobile,
                content=content,
                params=send_in.template_params,
                status="failed",
                code="PROVIDER_NOT_CONNECTED",
                message=f"{channel.provider} delivery is not connected in this deployment.",
            )
        )

    return SmsLogPublic.model_validate(
        create_sms_log(
            session=session,
            channel=channel,
            template=template,
            mobile=send_in.mobile,
            content=content,
            params=send_in.template_params,
            status="success",
            code="DEBUG_ACCEPTED",
            message="Debug channel accepted the SMS. No message was sent externally.",
        )
    )


@router.get(
    "/logs",
    dependencies=[Depends(require_permission("system:sms-log:list"))],
    response_model=SmsLogsPublic,
)
def read_sms_logs(
    session: SessionDep,
    tenant_context: CurrentTenant,
    page: int = 1,
    page_size: int = 20,
    channel_id: uuid.UUID | None = None,
    keyword: str | None = None,
    mobile: str | None = None,
    receive_status: str | None = None,
    send_status: str | None = None,
    template_code: str | None = None,
    template_id: uuid.UUID | None = None,
) -> Any:
    page, page_size = normalize_pagination(page=page, page_size=page_size)
    filters = [SmsLog.tenant_id == tenant_context.tenant_id]
    if keyword:
        pattern = f"%{keyword}%"
        filters.append(
            or_(
                col(SmsLog.mobile).ilike(pattern),
                col(SmsLog.template_code).ilike(pattern),
                col(SmsLog.template_name).ilike(pattern),
                col(SmsLog.channel_code).ilike(pattern),
            )
        )
    if mobile:
        filters.append(col(SmsLog.mobile).ilike(f"%{mobile}%"))
    if channel_id:
        filters.append(SmsLog.channel_id == channel_id)
    if template_id:
        filters.append(SmsLog.template_id == template_id)
    if template_code:
        filters.append(col(SmsLog.template_code).ilike(f"%{template_code}%"))
    if send_status:
        filters.append(SmsLog.send_status == send_status)
    if receive_status:
        filters.append(SmsLog.receive_status == receive_status)

    count_statement = select(func.count()).select_from(SmsLog)
    if filters:
        count_statement = count_statement.where(*filters)
    count = session.exec(count_statement).one()

    statement = select(SmsLog)
    if filters:
        statement = statement.where(*filters)
    logs = session.exec(
        statement.order_by(col(SmsLog.created_at).desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()
    return SmsLogsPublic(
        items=[SmsLogPublic.model_validate(log) for log in logs],
        total=count,
        page=page,
        page_size=page_size,
    )


@router.post(
    "/callbacks/{channel_code}",
    response_model=SmsLogPublic,
)
def receive_sms_callback(
    *,
    session: SessionDep,
    channel_code: str,
    callback_in: SmsDeliveryCallback,
    token: str | None = None,
) -> SmsLogPublic:
    sms_log = session.exec(
        select(SmsLog).where(SmsLog.api_request_id == callback_in.request_id)
    ).first()
    if not sms_log:
        raise HTTPException(status_code=404, detail="SMS log not found")
    channel = session.exec(
        select(SmsChannel).where(
            SmsChannel.tenant_id == sms_log.tenant_id,
            SmsChannel.code == channel_code,
        )
    ).first()
    if not channel:
        raise HTTPException(status_code=404, detail="SMS channel not found")
    if channel.api_secret and token != channel.api_secret:
        raise HTTPException(status_code=403, detail="Invalid SMS callback token")
    if callback_in.status not in {"success", "failed"}:
        raise HTTPException(status_code=400, detail="Invalid SMS delivery status")

    if sms_log.channel_id != channel.id:
        raise HTTPException(status_code=404, detail="SMS log not found")

    sms_log.receive_status = callback_in.status
    sms_log.received_at = get_datetime_utc()
    sms_log.api_receive_code = callback_in.status.upper()
    sms_log.api_receive_message = callback_in.message
    session.add(sms_log)
    session.commit()
    session.refresh(sms_log)
    return SmsLogPublic.model_validate(sms_log)
