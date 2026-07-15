import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlmodel import col, func, select

from app.api.deps import (
    CurrentTenant,
    SessionDep,
    normalize_pagination,
    require_permission,
)
from app.models import (
    Post,
    PostCreate,
    PostPublic,
    PostsPublic,
    PostUpdate,
    UserPost,
    get_datetime_utc,
)

router = APIRouter(prefix="/posts", tags=["posts"])


def get_post_or_404(
    *, session: SessionDep, tenant_id: uuid.UUID, post_id: uuid.UUID
) -> Post:
    post = session.exec(
        select(Post).where(Post.id == post_id, Post.tenant_id == tenant_id)
    ).first()
    if post is None:
        raise HTTPException(status_code=404, detail="Post not found")
    return post


@router.get(
    "",
    dependencies=[Depends(require_permission("system:post:list"))],
    response_model=PostsPublic,
)
def read_posts(
    session: SessionDep,
    tenant_context: CurrentTenant,
    page: int = 1,
    page_size: int = 20,
    keyword: str | None = None,
    is_active: bool | None = None,
) -> Any:
    page, page_size = normalize_pagination(page=page, page_size=page_size)
    filters = [Post.tenant_id == tenant_context.tenant_id]
    if keyword:
        pattern = f"%{keyword}%"
        filters.append(
            (col(Post.name).ilike(pattern))
            | (col(Post.code).ilike(pattern))
            | (col(Post.remark).ilike(pattern))
        )
    if is_active is not None:
        filters.append(Post.is_active == is_active)

    count_statement = select(func.count()).select_from(Post)
    if filters:
        count_statement = count_statement.where(*filters)
    count = session.exec(count_statement).one()

    statement = select(Post)
    if filters:
        statement = statement.where(*filters)
    statement = (
        statement.order_by(col(Post.sort), col(Post.created_at).desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    posts = session.exec(statement).all()
    return PostsPublic(
        items=[PostPublic.model_validate(post) for post in posts],
        total=count,
        page=page,
        page_size=page_size,
    )


@router.post(
    "",
    dependencies=[Depends(require_permission("system:post:create"))],
    response_model=PostPublic,
)
def create_post(
    *, session: SessionDep, tenant_context: CurrentTenant, post_in: PostCreate
) -> Any:
    existing_post = session.exec(
        select(Post).where(
            Post.tenant_id == tenant_context.tenant_id,
            Post.code == post_in.code,
        )
    ).first()
    if existing_post:
        raise HTTPException(status_code=409, detail="Post code already exists")

    post = Post.model_validate(
        post_in,
        update={"tenant_id": tenant_context.tenant_id},
    )
    session.add(post)
    session.commit()
    session.refresh(post)
    return post


@router.patch(
    "/{post_id}",
    dependencies=[Depends(require_permission("system:post:update"))],
    response_model=PostPublic,
)
def update_post(
    *,
    session: SessionDep,
    tenant_context: CurrentTenant,
    post_id: uuid.UUID,
    post_in: PostUpdate,
) -> Any:
    post = get_post_or_404(
        session=session,
        tenant_id=tenant_context.tenant_id,
        post_id=post_id,
    )
    if post_in.code and post_in.code != post.code:
        existing_post = session.exec(
            select(Post).where(
                Post.tenant_id == tenant_context.tenant_id,
                Post.code == post_in.code,
            )
        ).first()
        if existing_post:
            raise HTTPException(status_code=409, detail="Post code already exists")

    post.sqlmodel_update(post_in.model_dump(exclude_unset=True))
    post.updated_at = get_datetime_utc()
    session.add(post)
    session.commit()
    session.refresh(post)
    return post


@router.delete(
    "/{post_id}",
    dependencies=[Depends(require_permission("system:post:delete"))],
    status_code=204,
)
def delete_post(
    *, session: SessionDep, tenant_context: CurrentTenant, post_id: uuid.UUID
) -> Response:
    post = get_post_or_404(
        session=session,
        tenant_id=tenant_context.tenant_id,
        post_id=post_id,
    )

    bound_user = session.exec(
        select(UserPost).where(
            UserPost.tenant_id == tenant_context.tenant_id,
            UserPost.post_id == post_id,
        )
    ).first()
    if bound_user:
        raise HTTPException(status_code=400, detail="Post has users")

    session.delete(post)
    session.commit()
    return Response(status_code=204)
