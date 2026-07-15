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
from app.core.cache import CacheNamespace, redis_cache
from app.models import (
    DictionaryItem,
    DictionaryItemCreate,
    DictionaryItemPublic,
    DictionaryItemsPublic,
    DictionaryItemUpdate,
    DictionaryType,
    DictionaryTypeCreate,
    DictionaryTypePublic,
    DictionaryTypesPublic,
    DictionaryTypeUpdate,
    get_datetime_utc,
)

router = APIRouter(tags=["dictionaries"])


@router.get(
    "/dictionary-types",
    dependencies=[Depends(require_permission("system:dict:list"))],
    response_model=DictionaryTypesPublic,
)
def read_dictionary_types(
    session: SessionDep,
    tenant_context: CurrentTenant,
    page: int = 1,
    page_size: int = 20,
    keyword: str | None = None,
) -> Any:
    page, page_size = normalize_pagination(page=page, page_size=page_size)
    filters = [DictionaryType.tenant_id == tenant_context.tenant_id]
    if keyword:
        pattern = f"%{keyword}%"
        filters.append(
            (col(DictionaryType.name).ilike(pattern))
            | (col(DictionaryType.code).ilike(pattern))
        )

    count_statement = select(func.count()).select_from(DictionaryType)
    if filters:
        count_statement = count_statement.where(*filters)
    count = session.exec(count_statement).one()

    statement = select(DictionaryType)
    if filters:
        statement = statement.where(*filters)
    statement = (
        statement.order_by(col(DictionaryType.created_at).desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    types = session.exec(statement).all()
    return DictionaryTypesPublic(
        items=[DictionaryTypePublic.model_validate(type_) for type_ in types],
        total=count,
        page=page,
        page_size=page_size,
    )


@router.post(
    "/dictionary-types",
    dependencies=[Depends(require_permission("system:dict:create"))],
    response_model=DictionaryTypePublic,
)
def create_dictionary_type(
    *,
    session: SessionDep,
    tenant_context: CurrentTenant,
    type_in: DictionaryTypeCreate,
) -> Any:
    existing_type = session.exec(
        select(DictionaryType).where(
            DictionaryType.tenant_id == tenant_context.tenant_id,
            DictionaryType.code == type_in.code,
        )
    ).first()
    if existing_type:
        raise HTTPException(
            status_code=409, detail="Dictionary type code already exists"
        )

    type_ = DictionaryType.model_validate(
        type_in,
        update={"tenant_id": tenant_context.tenant_id},
    )
    session.add(type_)
    session.commit()
    session.refresh(type_)
    redis_cache.bump_namespace(CacheNamespace.DICTIONARY_ITEMS)
    return type_


@router.patch(
    "/dictionary-types/{type_id}",
    dependencies=[Depends(require_permission("system:dict:update"))],
    response_model=DictionaryTypePublic,
)
def update_dictionary_type(
    *,
    session: SessionDep,
    tenant_context: CurrentTenant,
    type_id: uuid.UUID,
    type_in: DictionaryTypeUpdate,
) -> Any:
    type_ = session.exec(
        select(DictionaryType).where(
            DictionaryType.id == type_id,
            DictionaryType.tenant_id == tenant_context.tenant_id,
        )
    ).first()
    if not type_:
        raise HTTPException(status_code=404, detail="Dictionary type not found")
    if type_in.code and type_in.code != type_.code:
        existing_type = session.exec(
            select(DictionaryType).where(
                DictionaryType.tenant_id == tenant_context.tenant_id,
                DictionaryType.code == type_in.code,
            )
        ).first()
        if existing_type:
            raise HTTPException(
                status_code=409, detail="Dictionary type code already exists"
            )

    type_.sqlmodel_update(type_in.model_dump(exclude_unset=True))
    type_.updated_at = get_datetime_utc()
    session.add(type_)
    session.commit()
    session.refresh(type_)
    redis_cache.bump_namespace(CacheNamespace.DICTIONARY_ITEMS)
    return type_


@router.delete(
    "/dictionary-types/{type_id}",
    dependencies=[Depends(require_permission("system:dict:delete"))],
    status_code=204,
)
def delete_dictionary_type(
    *,
    session: SessionDep,
    tenant_context: CurrentTenant,
    type_id: uuid.UUID,
) -> Response:
    type_ = session.exec(
        select(DictionaryType).where(
            DictionaryType.id == type_id,
            DictionaryType.tenant_id == tenant_context.tenant_id,
        )
    ).first()
    if not type_:
        raise HTTPException(status_code=404, detail="Dictionary type not found")

    bound_item = session.exec(
        select(DictionaryItem).where(
            DictionaryItem.tenant_id == tenant_context.tenant_id,
            DictionaryItem.type_id == type_id,
        )
    ).first()
    if bound_item:
        raise HTTPException(status_code=400, detail="Dictionary type has items")

    session.delete(type_)
    session.commit()
    redis_cache.bump_namespace(CacheNamespace.DICTIONARY_ITEMS)
    return Response(status_code=204)


@router.get(
    "/dictionary-items",
    dependencies=[Depends(require_permission("system:dict:list"))],
    response_model=DictionaryItemsPublic,
)
def read_dictionary_items(
    session: SessionDep,
    tenant_context: CurrentTenant,
    type_id: uuid.UUID | None = None,
    page: int = 1,
    page_size: int = 200,
    keyword: str | None = None,
) -> Any:
    page, page_size = normalize_pagination(
        page=page, page_size=page_size, max_page_size=500
    )
    filters = [DictionaryItem.tenant_id == tenant_context.tenant_id]
    if type_id:
        filters.append(DictionaryItem.type_id == type_id)
    if keyword:
        pattern = f"%{keyword}%"
        filters.append(
            (col(DictionaryItem.label).ilike(pattern))
            | (col(DictionaryItem.value).ilike(pattern))
        )

    count_statement = select(func.count()).select_from(DictionaryItem)
    if filters:
        count_statement = count_statement.where(*filters)
    count = session.exec(count_statement).one()

    statement = select(DictionaryItem)
    if filters:
        statement = statement.where(*filters)
    statement = (
        statement.order_by(col(DictionaryItem.sort), col(DictionaryItem.created_at))
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    items = session.exec(statement).all()
    return DictionaryItemsPublic(
        items=[DictionaryItemPublic.model_validate(item) for item in items],
        total=count,
        page=page,
        page_size=page_size,
    )


@router.get(
    "/dictionaries/{code}/items",
    response_model=list[DictionaryItemPublic],
)
def read_dictionary_items_by_code(
    session: SessionDep,
    tenant_context: CurrentTenant,
    code: str,
) -> Any:
    cache_key = redis_cache.build_versioned_key(
        CacheNamespace.DICTIONARY_ITEMS,
        str(tenant_context.tenant_id),
        code,
    )
    cached_items = redis_cache.get_json(cache_key)
    if cached_items is not None:
        return [DictionaryItemPublic.model_validate(item) for item in cached_items]

    type_ = session.exec(
        select(DictionaryType).where(
            DictionaryType.tenant_id == tenant_context.tenant_id,
            DictionaryType.code == code,
            DictionaryType.is_active,
        )
    ).first()
    if not type_:
        raise HTTPException(status_code=404, detail="Dictionary type not found")

    items = session.exec(
        select(DictionaryItem)
        .where(
            DictionaryItem.tenant_id == tenant_context.tenant_id,
            DictionaryItem.type_id == type_.id,
            DictionaryItem.is_active,
        )
        .order_by(col(DictionaryItem.sort), col(DictionaryItem.created_at))
    ).all()
    public_items = [DictionaryItemPublic.model_validate(item) for item in items]
    redis_cache.set_json(
        cache_key,
        [item.model_dump(mode="json") for item in public_items],
    )
    return public_items


@router.post(
    "/dictionary-items",
    dependencies=[Depends(require_permission("system:dict:create"))],
    response_model=DictionaryItemPublic,
)
def create_dictionary_item(
    *,
    session: SessionDep,
    tenant_context: CurrentTenant,
    item_in: DictionaryItemCreate,
) -> Any:
    type_ = session.exec(
        select(DictionaryType).where(
            DictionaryType.id == item_in.type_id,
            DictionaryType.tenant_id == tenant_context.tenant_id,
        )
    ).first()
    if type_ is None:
        raise HTTPException(status_code=400, detail="Dictionary type does not exist")
    existing_item = session.exec(
        select(DictionaryItem).where(
            DictionaryItem.tenant_id == tenant_context.tenant_id,
            DictionaryItem.type_id == item_in.type_id,
            DictionaryItem.value == item_in.value,
        )
    ).first()
    if existing_item:
        raise HTTPException(
            status_code=409, detail="Dictionary item value already exists"
        )

    item = DictionaryItem.model_validate(
        item_in,
        update={"tenant_id": tenant_context.tenant_id},
    )
    session.add(item)
    session.commit()
    session.refresh(item)
    redis_cache.bump_namespace(CacheNamespace.DICTIONARY_ITEMS)
    return item


@router.patch(
    "/dictionary-items/{item_id}",
    dependencies=[Depends(require_permission("system:dict:update"))],
    response_model=DictionaryItemPublic,
)
def update_dictionary_item(
    *,
    session: SessionDep,
    tenant_context: CurrentTenant,
    item_id: uuid.UUID,
    item_in: DictionaryItemUpdate,
) -> Any:
    item = session.exec(
        select(DictionaryItem).where(
            DictionaryItem.id == item_id,
            DictionaryItem.tenant_id == tenant_context.tenant_id,
        )
    ).first()
    if not item:
        raise HTTPException(status_code=404, detail="Dictionary item not found")
    if item_in.type_id:
        target_type = session.exec(
            select(DictionaryType).where(
                DictionaryType.id == item_in.type_id,
                DictionaryType.tenant_id == tenant_context.tenant_id,
            )
        ).first()
        if target_type is None:
            raise HTTPException(
                status_code=400,
                detail="Dictionary type does not exist",
            )
    next_type_id = item_in.type_id or item.type_id
    next_value = item_in.value or item.value
    existing_item = session.exec(
        select(DictionaryItem).where(
            DictionaryItem.tenant_id == tenant_context.tenant_id,
            DictionaryItem.type_id == next_type_id,
            DictionaryItem.value == next_value,
            DictionaryItem.id != item.id,
        )
    ).first()
    if existing_item:
        raise HTTPException(
            status_code=409, detail="Dictionary item value already exists"
        )

    item.sqlmodel_update(item_in.model_dump(exclude_unset=True))
    item.updated_at = get_datetime_utc()
    session.add(item)
    session.commit()
    session.refresh(item)
    redis_cache.bump_namespace(CacheNamespace.DICTIONARY_ITEMS)
    return item


@router.delete(
    "/dictionary-items/{item_id}",
    dependencies=[Depends(require_permission("system:dict:delete"))],
    status_code=204,
)
def delete_dictionary_item(
    *,
    session: SessionDep,
    tenant_context: CurrentTenant,
    item_id: uuid.UUID,
) -> Response:
    item = session.exec(
        select(DictionaryItem).where(
            DictionaryItem.id == item_id,
            DictionaryItem.tenant_id == tenant_context.tenant_id,
        )
    ).first()
    if not item:
        raise HTTPException(status_code=404, detail="Dictionary item not found")

    session.delete(item)
    session.commit()
    redis_cache.bump_namespace(CacheNamespace.DICTIONARY_ITEMS)
    return Response(status_code=204)
