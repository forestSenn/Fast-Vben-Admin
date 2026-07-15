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
    Department,
    DepartmentCreate,
    DepartmentPublic,
    DepartmentsPublic,
    DepartmentUpdate,
    TenantMembership,
    get_datetime_utc,
)

router = APIRouter(prefix="/departments", tags=["departments"])


def is_descendant_department(
    *,
    session: SessionDep,
    tenant_id: uuid.UUID,
    department_id: uuid.UUID,
    possible_descendant_id: uuid.UUID,
) -> bool:
    current_id: uuid.UUID | None = possible_descendant_id
    visited: set[uuid.UUID] = set()
    while current_id:
        if current_id == department_id:
            return True
        if current_id in visited:
            return True
        visited.add(current_id)
        current = session.exec(
            select(Department).where(
                Department.id == current_id,
                Department.tenant_id == tenant_id,
            )
        ).first()
        current_id = current.parent_id if current else None
    return False


def get_department_or_404(
    *, session: SessionDep, tenant_id: uuid.UUID, department_id: uuid.UUID
) -> Department:
    department = session.exec(
        select(Department).where(
            Department.id == department_id,
            Department.tenant_id == tenant_id,
        )
    ).first()
    if department is None:
        raise HTTPException(status_code=404, detail="Department not found")
    return department


@router.get(
    "",
    dependencies=[Depends(require_permission("system:department:list"))],
    response_model=DepartmentsPublic,
)
def read_departments(
    session: SessionDep,
    tenant_context: CurrentTenant,
    page: int = 1,
    page_size: int = 200,
    keyword: str | None = None,
) -> Any:
    page, page_size = normalize_pagination(
        page=page, page_size=page_size, max_page_size=500
    )
    filters = [Department.tenant_id == tenant_context.tenant_id]
    if keyword:
        pattern = f"%{keyword}%"
        filters.append(
            (col(Department.name).ilike(pattern))
            | (col(Department.code).ilike(pattern))
            | (col(Department.remark).ilike(pattern))
        )

    count_statement = select(func.count()).select_from(Department)
    if filters:
        count_statement = count_statement.where(*filters)
    count = session.exec(count_statement).one()

    statement = select(Department)
    if filters:
        statement = statement.where(*filters)
    statement = (
        statement.order_by(col(Department.sort), col(Department.created_at).desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    departments = session.exec(statement).all()
    return DepartmentsPublic(
        items=[
            DepartmentPublic.model_validate(department) for department in departments
        ],
        total=count,
        page=page,
        page_size=page_size,
    )


@router.post(
    "",
    dependencies=[Depends(require_permission("system:department:create"))],
    response_model=DepartmentPublic,
)
def create_department(
    *,
    session: SessionDep,
    tenant_context: CurrentTenant,
    department_in: DepartmentCreate,
) -> Any:
    if department_in.parent_id:
        get_department_or_404(
            session=session,
            tenant_id=tenant_context.tenant_id,
            department_id=department_in.parent_id,
        )
    if department_in.leader_user_id:
        membership = session.exec(
            select(TenantMembership).where(
                TenantMembership.user_id == department_in.leader_user_id,
                TenantMembership.tenant_id == tenant_context.tenant_id,
            )
        ).first()
        if membership is None:
            raise HTTPException(status_code=400, detail="Leader user does not exist")

    existing_department = session.exec(
        select(Department).where(
            Department.tenant_id == tenant_context.tenant_id,
            Department.code == department_in.code,
        )
    ).first()
    if existing_department:
        raise HTTPException(status_code=409, detail="Department code already exists")

    department = Department.model_validate(
        department_in,
        update={"tenant_id": tenant_context.tenant_id},
    )
    session.add(department)
    session.commit()
    session.refresh(department)
    return department


@router.patch(
    "/{department_id}",
    dependencies=[Depends(require_permission("system:department:update"))],
    response_model=DepartmentPublic,
)
def update_department(
    *,
    session: SessionDep,
    department_id: uuid.UUID,
    department_in: DepartmentUpdate,
    tenant_context: CurrentTenant,
) -> Any:
    department = get_department_or_404(
        session=session,
        tenant_id=tenant_context.tenant_id,
        department_id=department_id,
    )
    if department_in.parent_id == department_id:
        raise HTTPException(
            status_code=400, detail="Department cannot be its own parent"
        )
    if department_in.parent_id:
        get_department_or_404(
            session=session,
            tenant_id=tenant_context.tenant_id,
            department_id=department_in.parent_id,
        )
    if department_in.parent_id and is_descendant_department(
        session=session,
        tenant_id=tenant_context.tenant_id,
        department_id=department_id,
        possible_descendant_id=department_in.parent_id,
    ):
        raise HTTPException(
            status_code=400, detail="Department parent cannot be a child"
        )
    if department_in.leader_user_id:
        membership = session.exec(
            select(TenantMembership).where(
                TenantMembership.user_id == department_in.leader_user_id,
                TenantMembership.tenant_id == tenant_context.tenant_id,
            )
        ).first()
        if membership is None:
            raise HTTPException(status_code=400, detail="Leader user does not exist")
    if department_in.code and department_in.code != department.code:
        existing_department = session.exec(
            select(Department).where(
                Department.tenant_id == tenant_context.tenant_id,
                Department.code == department_in.code,
            )
        ).first()
        if existing_department:
            raise HTTPException(
                status_code=409, detail="Department code already exists"
            )

    department.sqlmodel_update(department_in.model_dump(exclude_unset=True))
    department.updated_at = get_datetime_utc()
    session.add(department)
    session.commit()
    session.refresh(department)
    return department


@router.delete(
    "/{department_id}",
    dependencies=[Depends(require_permission("system:department:delete"))],
    status_code=204,
)
def delete_department(
    *,
    session: SessionDep,
    tenant_context: CurrentTenant,
    department_id: uuid.UUID,
) -> Response:
    department = get_department_or_404(
        session=session,
        tenant_id=tenant_context.tenant_id,
        department_id=department_id,
    )

    child_department = session.exec(
        select(Department).where(
            Department.tenant_id == tenant_context.tenant_id,
            Department.parent_id == department_id,
        )
    ).first()
    if child_department:
        raise HTTPException(status_code=400, detail="Department has child departments")

    bound_user = session.exec(
        select(TenantMembership).where(
            TenantMembership.tenant_id == tenant_context.tenant_id,
            TenantMembership.department_id == department_id,
        )
    ).first()
    if bound_user:
        raise HTTPException(status_code=400, detail="Department has users")

    session.delete(department)
    session.commit()
    return Response(status_code=204)
