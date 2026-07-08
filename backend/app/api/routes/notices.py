import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlmodel import col, func, or_, select

from app.api.deps import CurrentUser, SessionDep, require_permission
from app.models import (
    Notice,
    NoticeCreate,
    NoticePublic,
    NoticesPublic,
    NoticeUpdate,
    User,
    UserMessage,
    UserMessagePublic,
    UserMessagesPublic,
    get_datetime_utc,
)

router = APIRouter(tags=["notices"])


@router.get(
    "/notices",
    dependencies=[Depends(require_permission("system:notice:list"))],
    response_model=NoticesPublic,
)
def read_notices(
    session: SessionDep,
    page: int = 1,
    page_size: int = 20,
    keyword: str | None = None,
    status: str | None = None,
) -> Any:
    filters = []
    if status:
        filters.append(Notice.status == status)
    if keyword:
        pattern = f"%{keyword}%"
        filters.append(or_(col(Notice.title).ilike(pattern), col(Notice.content).ilike(pattern)))

    count_statement = select(func.count()).select_from(Notice)
    if filters:
        count_statement = count_statement.where(*filters)
    count = session.exec(count_statement).one()

    statement = select(Notice)
    if filters:
        statement = statement.where(*filters)
    statement = (
        statement.order_by(col(Notice.priority).desc(), col(Notice.created_at).desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    notices = session.exec(statement).all()
    return NoticesPublic(
        items=[NoticePublic.model_validate(notice) for notice in notices],
        total=count,
        page=page,
        page_size=page_size,
    )


@router.post(
    "/notices",
    dependencies=[Depends(require_permission("system:notice:create"))],
    response_model=NoticePublic,
)
def create_notice(
    *, session: SessionDep, current_user: CurrentUser, notice_in: NoticeCreate
) -> Any:
    notice = Notice.model_validate(notice_in, update={"created_by": current_user.id})
    session.add(notice)
    session.commit()
    session.refresh(notice)
    return notice


@router.patch(
    "/notices/{notice_id}",
    dependencies=[Depends(require_permission("system:notice:update"))],
    response_model=NoticePublic,
)
def update_notice(
    *, session: SessionDep, notice_id: uuid.UUID, notice_in: NoticeUpdate
) -> Any:
    notice = session.get(Notice, notice_id)
    if not notice:
        raise HTTPException(status_code=404, detail="Notice not found")
    if notice.status == "published" and notice_in.status == "draft":
        raise HTTPException(status_code=400, detail="Published notice cannot become draft")

    update_data = notice_in.model_dump(exclude_unset=True)
    if "status" in update_data and update_data["status"] not in {
        "draft",
        "published",
        "withdrawn",
    }:
        raise HTTPException(status_code=400, detail="Invalid notice status")
    notice.sqlmodel_update(update_data)
    notice.updated_at = get_datetime_utc()
    session.add(notice)
    session.commit()
    session.refresh(notice)
    return notice


@router.post(
    "/notices/{notice_id}/publish",
    dependencies=[Depends(require_permission("system:notice:update"))],
    response_model=NoticePublic,
)
def publish_notice(*, session: SessionDep, notice_id: uuid.UUID) -> Any:
    notice = session.get(Notice, notice_id)
    if not notice:
        raise HTTPException(status_code=404, detail="Notice not found")

    now = get_datetime_utc()
    notice.status = "published"
    notice.published_at = now
    notice.updated_at = now
    session.add(notice)

    users = session.exec(select(User).where(User.is_active)).all()
    for user in users:
        existing = session.exec(
            select(UserMessage).where(
                UserMessage.user_id == user.id,
                UserMessage.notice_id == notice.id,
            )
        ).first()
        if existing:
            continue
        session.add(
            UserMessage(
                user_id=user.id,
                notice_id=notice.id,
                title=notice.title,
                content=notice.content,
                type=notice.type,
            )
        )

    session.commit()
    session.refresh(notice)
    return notice


@router.post(
    "/notices/{notice_id}/withdraw",
    dependencies=[Depends(require_permission("system:notice:update"))],
    response_model=NoticePublic,
)
def withdraw_notice(*, session: SessionDep, notice_id: uuid.UUID) -> Any:
    notice = session.get(Notice, notice_id)
    if not notice:
        raise HTTPException(status_code=404, detail="Notice not found")
    notice.status = "withdrawn"
    notice.updated_at = get_datetime_utc()
    session.add(notice)
    session.commit()
    session.refresh(notice)
    return notice


@router.delete(
    "/notices/{notice_id}",
    dependencies=[Depends(require_permission("system:notice:delete"))],
    status_code=204,
)
def delete_notice(*, session: SessionDep, notice_id: uuid.UUID) -> Response:
    notice = session.get(Notice, notice_id)
    if not notice:
        raise HTTPException(status_code=404, detail="Notice not found")
    messages = session.exec(
        select(UserMessage).where(UserMessage.notice_id == notice_id)
    ).all()
    for message in messages:
        message.notice_id = None
        session.add(message)
    session.delete(notice)
    session.commit()
    return Response(status_code=204)


@router.get("/notices/current", response_model=list[NoticePublic])
def read_current_notices(session: SessionDep, current_user: CurrentUser) -> Any:
    _ = current_user
    now = get_datetime_utc()
    notices = session.exec(
        select(Notice)
        .where(
            Notice.status == "published",
            or_(Notice.published_at == None, Notice.published_at <= now),  # noqa: E711
        )
        .order_by(col(Notice.priority).desc(), col(Notice.published_at).desc())
    ).all()
    return [NoticePublic.model_validate(notice) for notice in notices]


@router.get("/messages/me", response_model=UserMessagesPublic)
def read_my_messages(
    session: SessionDep,
    current_user: CurrentUser,
    page: int = 1,
    page_size: int = 20,
    is_read: bool | None = None,
) -> Any:
    filters = [UserMessage.user_id == current_user.id]
    if is_read is not None:
        filters.append(UserMessage.is_read == is_read)

    count = session.exec(
        select(func.count()).select_from(UserMessage).where(*filters)
    ).one()
    messages = session.exec(
        select(UserMessage)
        .where(*filters)
        .order_by(col(UserMessage.created_at).desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()
    return UserMessagesPublic(
        items=[UserMessagePublic.model_validate(message) for message in messages],
        total=count,
        page=page,
        page_size=page_size,
    )


@router.post("/messages/{message_id}/read", response_model=UserMessagePublic)
def mark_message_read(
    *, session: SessionDep, current_user: CurrentUser, message_id: uuid.UUID
) -> Any:
    message = session.get(UserMessage, message_id)
    if not message or message.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Message not found")
    if not message.is_read:
        message.is_read = True
        message.read_at = get_datetime_utc()
        session.add(message)
        session.commit()
        session.refresh(message)
    return message
