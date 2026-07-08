import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlmodel import col, func, select

from app.api.deps import SessionDep, require_permission
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
    page: int = 1,
    page_size: int = 20,
    keyword: str | None = None,
) -> Any:
    filters = []
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
    *, session: SessionDep, type_in: DictionaryTypeCreate
) -> Any:
    existing_type = session.exec(
        select(DictionaryType).where(DictionaryType.code == type_in.code)
    ).first()
    if existing_type:
        raise HTTPException(status_code=409, detail="Dictionary type code already exists")

    type_ = DictionaryType.model_validate(type_in)
    session.add(type_)
    session.commit()
    session.refresh(type_)
    return type_


@router.patch(
    "/dictionary-types/{type_id}",
    dependencies=[Depends(require_permission("system:dict:update"))],
    response_model=DictionaryTypePublic,
)
def update_dictionary_type(
    *, session: SessionDep, type_id: uuid.UUID, type_in: DictionaryTypeUpdate
) -> Any:
    type_ = session.get(DictionaryType, type_id)
    if not type_:
        raise HTTPException(status_code=404, detail="Dictionary type not found")
    if type_in.code and type_in.code != type_.code:
        existing_type = session.exec(
            select(DictionaryType).where(DictionaryType.code == type_in.code)
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
    return type_


@router.delete(
    "/dictionary-types/{type_id}",
    dependencies=[Depends(require_permission("system:dict:delete"))],
    status_code=204,
)
def delete_dictionary_type(*, session: SessionDep, type_id: uuid.UUID) -> Response:
    type_ = session.get(DictionaryType, type_id)
    if not type_:
        raise HTTPException(status_code=404, detail="Dictionary type not found")

    bound_item = session.exec(
        select(DictionaryItem).where(DictionaryItem.type_id == type_id)
    ).first()
    if bound_item:
        raise HTTPException(status_code=400, detail="Dictionary type has items")

    session.delete(type_)
    session.commit()
    return Response(status_code=204)


@router.get(
    "/dictionary-items",
    dependencies=[Depends(require_permission("system:dict:list"))],
    response_model=DictionaryItemsPublic,
)
def read_dictionary_items(
    session: SessionDep,
    type_id: uuid.UUID | None = None,
    page: int = 1,
    page_size: int = 200,
    keyword: str | None = None,
) -> Any:
    filters = []
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
def read_dictionary_items_by_code(session: SessionDep, code: str) -> Any:
    type_ = session.exec(
        select(DictionaryType).where(
            DictionaryType.code == code,
            DictionaryType.is_active,
        )
    ).first()
    if not type_:
        raise HTTPException(status_code=404, detail="Dictionary type not found")

    items = session.exec(
        select(DictionaryItem)
        .where(DictionaryItem.type_id == type_.id, DictionaryItem.is_active)
        .order_by(col(DictionaryItem.sort), col(DictionaryItem.created_at))
    ).all()
    return [DictionaryItemPublic.model_validate(item) for item in items]


@router.post(
    "/dictionary-items",
    dependencies=[Depends(require_permission("system:dict:create"))],
    response_model=DictionaryItemPublic,
)
def create_dictionary_item(
    *, session: SessionDep, item_in: DictionaryItemCreate
) -> Any:
    if not session.get(DictionaryType, item_in.type_id):
        raise HTTPException(status_code=400, detail="Dictionary type does not exist")

    item = DictionaryItem.model_validate(item_in)
    session.add(item)
    session.commit()
    session.refresh(item)
    return item


@router.patch(
    "/dictionary-items/{item_id}",
    dependencies=[Depends(require_permission("system:dict:update"))],
    response_model=DictionaryItemPublic,
)
def update_dictionary_item(
    *, session: SessionDep, item_id: uuid.UUID, item_in: DictionaryItemUpdate
) -> Any:
    item = session.get(DictionaryItem, item_id)
    if not item:
        raise HTTPException(status_code=404, detail="Dictionary item not found")
    if item_in.type_id and not session.get(DictionaryType, item_in.type_id):
        raise HTTPException(status_code=400, detail="Dictionary type does not exist")

    item.sqlmodel_update(item_in.model_dump(exclude_unset=True))
    item.updated_at = get_datetime_utc()
    session.add(item)
    session.commit()
    session.refresh(item)
    return item


@router.delete(
    "/dictionary-items/{item_id}",
    dependencies=[Depends(require_permission("system:dict:delete"))],
    status_code=204,
)
def delete_dictionary_item(*, session: SessionDep, item_id: uuid.UUID) -> Response:
    item = session.get(DictionaryItem, item_id)
    if not item:
        raise HTTPException(status_code=404, detail="Dictionary item not found")

    session.delete(item)
    session.commit()
    return Response(status_code=204)
