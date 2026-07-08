import csv
import io
import uuid
from typing import Any

from fastapi import APIRouter, Depends, File, HTTPException, Response, UploadFile
from fastapi.responses import StreamingResponse
from sqlmodel import col, func, select

from app.api.deps import CurrentUser, SessionDep, require_permission
from app.models import (
    Item,
    ItemCreate,
    ItemPublic,
    ItemsPublic,
    ItemUpdate,
    get_datetime_utc,
)

router = APIRouter(prefix="/items", tags=["items"])


def item_to_csv_row(item: Item) -> list[Any]:
    return [
        item.id,
        item.title,
        item.description or "",
        item.owner_id,
        item.created_at or "",
        item.updated_at or "",
    ]


@router.get(
    "",
    dependencies=[Depends(require_permission("business:item:list"))],
    response_model=ItemsPublic,
)
def read_items(
    session: SessionDep,
    current_user: CurrentUser,
    page: int = 1,
    page_size: int = 20,
    keyword: str | None = None,
) -> Any:
    """
    Retrieve items.
    """

    offset = (page - 1) * page_size
    filters = []
    if keyword:
        pattern = f"%{keyword}%"
        filters.append(
            (col(Item.title).ilike(pattern)) | (col(Item.description).ilike(pattern))
        )

    if current_user.is_superuser:
        count_statement = select(func.count()).select_from(Item)
        if filters:
            count_statement = count_statement.where(*filters)
        count = session.exec(count_statement).one()
        statement = select(Item)
        if filters:
            statement = statement.where(*filters)
        statement = statement.order_by(col(Item.created_at).desc()).offset(offset).limit(page_size)
        items = session.exec(statement).all()
    else:
        user_filters = [Item.owner_id == current_user.id, *filters]
        count_statement = (
            select(func.count())
            .select_from(Item)
            .where(*user_filters)
        )
        count = session.exec(count_statement).one()
        statement = (
            select(Item)
            .where(*user_filters)
            .order_by(col(Item.created_at).desc())
            .offset(offset)
            .limit(page_size)
        )
        items = session.exec(statement).all()

    items_public = [ItemPublic.model_validate(item) for item in items]
    return ItemsPublic(
        items=items_public,
        total=count,
        page=page,
        page_size=page_size,
    )


@router.get(
    "/export",
    dependencies=[Depends(require_permission("business:item:list"))],
)
def export_items(session: SessionDep, current_user: CurrentUser) -> StreamingResponse:
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["id", "title", "description", "owner_id", "created_at", "updated_at"])
    statement = select(Item)
    if not current_user.is_superuser:
        statement = statement.where(Item.owner_id == current_user.id)
    items = session.exec(statement.order_by(col(Item.created_at).desc())).all()
    for item in items:
        writer.writerow(item_to_csv_row(item))
    output.seek(0)
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": 'attachment; filename="items.csv"'},
    )


@router.get(
    "/import-template",
    dependencies=[Depends(require_permission("business:item:create"))],
)
def download_import_template() -> StreamingResponse:
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["title", "description"])
    writer.writerow(["示例资源", "这是导入模板示例"])
    output.seek(0)
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": 'attachment; filename="items-import-template.csv"'},
    )


@router.post(
    "/import",
    dependencies=[Depends(require_permission("business:item:create"))],
)
async def import_items(
    session: SessionDep,
    current_user: CurrentUser,
    file: UploadFile = File(...),
) -> dict[str, Any]:
    if not file.filename or not file.filename.lower().endswith(".csv"):
        raise HTTPException(status_code=400, detail="Only CSV files are supported")

    raw_content = await file.read()
    try:
        content = raw_content.decode("utf-8-sig")
    except UnicodeDecodeError:
        raise HTTPException(status_code=400, detail="CSV file must be UTF-8 encoded")

    reader = csv.DictReader(io.StringIO(content))
    if not reader.fieldnames or "title" not in reader.fieldnames:
        raise HTTPException(status_code=400, detail="CSV must contain title column")

    success_count = 0
    errors: list[dict[str, Any]] = []
    for row_number, row in enumerate(reader, start=2):
        title = (row.get("title") or "").strip()
        description = (row.get("description") or "").strip() or None
        if not title:
            errors.append({"row": row_number, "error": "title is required"})
            continue
        item = Item(
            title=title[:255],
            description=description[:255] if description else None,
            owner_id=current_user.id,
        )
        session.add(item)
        success_count += 1

    session.commit()
    return {
        "errors": errors,
        "failed": len(errors),
        "success": success_count,
        "total": success_count + len(errors),
    }


@router.get(
    "/{id}",
    dependencies=[Depends(require_permission("business:item:list"))],
    response_model=ItemPublic,
)
def read_item(session: SessionDep, current_user: CurrentUser, id: uuid.UUID) -> Any:
    """
    Get item by ID.
    """
    item = session.get(Item, id)
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")
    if not current_user.is_superuser and (item.owner_id != current_user.id):
        raise HTTPException(status_code=403, detail="Not enough permissions")
    return item


@router.post(
    "",
    dependencies=[Depends(require_permission("business:item:create"))],
    response_model=ItemPublic,
)
def create_item(
    *, session: SessionDep, current_user: CurrentUser, item_in: ItemCreate
) -> Any:
    """
    Create new item.
    """
    item = Item.model_validate(item_in, update={"owner_id": current_user.id})
    session.add(item)
    session.commit()
    session.refresh(item)
    return item


@router.patch(
    "/{id}",
    dependencies=[Depends(require_permission("business:item:update"))],
    response_model=ItemPublic,
)
def update_item(
    *,
    session: SessionDep,
    current_user: CurrentUser,
    id: uuid.UUID,
    item_in: ItemUpdate,
) -> Any:
    """
    Update an item.
    """
    item = session.get(Item, id)
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")
    if not current_user.is_superuser and (item.owner_id != current_user.id):
        raise HTTPException(status_code=403, detail="Not enough permissions")
    update_dict = item_in.model_dump(exclude_unset=True)
    item.sqlmodel_update(update_dict)
    item.updated_at = get_datetime_utc()
    session.add(item)
    session.commit()
    session.refresh(item)
    return item


@router.delete(
    "/{id}",
    dependencies=[Depends(require_permission("business:item:delete"))],
    status_code=204,
)
def delete_item(
    session: SessionDep, current_user: CurrentUser, id: uuid.UUID
) -> Response:
    """
    Delete an item.
    """
    item = session.get(Item, id)
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")
    if not current_user.is_superuser and (item.owner_id != current_user.id):
        raise HTTPException(status_code=403, detail="Not enough permissions")
    session.delete(item)
    session.commit()
    return Response(status_code=204)
