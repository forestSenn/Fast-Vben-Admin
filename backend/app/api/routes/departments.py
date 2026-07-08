import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlmodel import col, func, select

from app.api.deps import SessionDep, require_permission
from app.models import (
    Department,
    DepartmentCreate,
    DepartmentPublic,
    DepartmentsPublic,
    DepartmentUpdate,
    User,
    get_datetime_utc,
)

router = APIRouter(prefix="/departments", tags=["departments"])


@router.get(
    "",
    dependencies=[Depends(require_permission("system:department:list"))],
    response_model=DepartmentsPublic,
)
def read_departments(
    session: SessionDep,
    page: int = 1,
    page_size: int = 200,
    keyword: str | None = None,
) -> Any:
    filters = []
    if keyword:
        pattern = f"%{keyword}%"
        filters.append(
            (col(Department.name).ilike(pattern))
            | (col(Department.code).ilike(pattern))
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
            DepartmentPublic.model_validate(department)
            for department in departments
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
def create_department(*, session: SessionDep, department_in: DepartmentCreate) -> Any:
    if department_in.parent_id and not session.get(Department, department_in.parent_id):
        raise HTTPException(status_code=400, detail="Parent department does not exist")
    if department_in.leader_user_id and not session.get(User, department_in.leader_user_id):
        raise HTTPException(status_code=400, detail="Leader user does not exist")

    existing_department = session.exec(
        select(Department).where(Department.code == department_in.code)
    ).first()
    if existing_department:
        raise HTTPException(status_code=409, detail="Department code already exists")

    department = Department.model_validate(department_in)
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
    *, session: SessionDep, department_id: uuid.UUID, department_in: DepartmentUpdate
) -> Any:
    department = session.get(Department, department_id)
    if not department:
        raise HTTPException(status_code=404, detail="Department not found")
    if department_in.parent_id == department_id:
        raise HTTPException(
            status_code=400, detail="Department cannot be its own parent"
        )
    if department_in.parent_id and not session.get(Department, department_in.parent_id):
        raise HTTPException(status_code=400, detail="Parent department does not exist")
    if department_in.leader_user_id and not session.get(User, department_in.leader_user_id):
        raise HTTPException(status_code=400, detail="Leader user does not exist")
    if department_in.code and department_in.code != department.code:
        existing_department = session.exec(
            select(Department).where(Department.code == department_in.code)
        ).first()
        if existing_department:
            raise HTTPException(status_code=409, detail="Department code already exists")

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
def delete_department(*, session: SessionDep, department_id: uuid.UUID) -> Response:
    department = session.get(Department, department_id)
    if not department:
        raise HTTPException(status_code=404, detail="Department not found")

    child_department = session.exec(
        select(Department).where(Department.parent_id == department_id)
    ).first()
    if child_department:
        raise HTTPException(status_code=400, detail="Department has child departments")

    bound_user = session.exec(
        select(User).where(User.department_id == department_id)
    ).first()
    if bound_user:
        raise HTTPException(status_code=400, detail="Department has users")

    session.delete(department)
    session.commit()
    return Response(status_code=204)
