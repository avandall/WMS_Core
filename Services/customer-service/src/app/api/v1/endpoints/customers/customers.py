from __future__ import annotations

from typing import List

from fastapi import APIRouter, Depends, HTTPException, status

from app.api.auth_deps import get_current_user, require_permissions
from app.api.api_deps import get_customer_service
from app.modules.customers.application.dtos.customer import (
    CustomerCreate,
    CustomerDetailResponse,
    CustomerResponse,
    CustomerUpdate,
    DebtUpdate,
    PurchaseResponse,
)
from app.modules.customers.application.services.customer_service import CustomerService
from app.shared.core.permissions import Permission

router = APIRouter(dependencies=[Depends(get_current_user)])


@router.post(
    "/",
    response_model=CustomerResponse,
    dependencies=[Depends(require_permissions(Permission.MANAGE_PRODUCTS))],
)
async def create_customer(payload: CustomerCreate, service: CustomerService = Depends(get_customer_service)):
    model = await service.create(payload.model_dump())
    return CustomerResponse(
        customer_id=model.customer_id,
        name=model.name,
        email=model.email,
        phone=model.phone,
        address=model.address,
        debt_balance=model.debt_balance,
        created_at=model.created_at,
    )


@router.get("/", response_model=List[CustomerResponse])
def list_customers(service: CustomerService = Depends(get_customer_service)):
    data = service.list()
    return [CustomerResponse(**c) for c in data]


@router.get("/{customer_id}", response_model=CustomerDetailResponse)
def get_customer(customer_id: int, service: CustomerService = Depends(get_customer_service)):
    c = service.get(customer_id)
    if not c:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Customer not found")
    return CustomerDetailResponse(**c)


@router.patch("/{customer_id}/debt")
def update_debt(customer_id: int, payload: DebtUpdate, service: CustomerService = Depends(get_customer_service)):
    service.update_debt(customer_id, payload.amount)
    return {"message": "Debt updated", "delta": payload.amount}


@router.patch(
    "/{customer_id}",
    response_model=CustomerResponse,
    dependencies=[Depends(require_permissions(Permission.MANAGE_PRODUCTS))],
)
def update_customer(customer_id: int, payload: CustomerUpdate, service: CustomerService = Depends(get_customer_service)):
    existing = service.get(customer_id)
    if not existing:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Customer not found")
    service.update(customer_id, payload.model_dump(exclude_unset=True))
    updated = service.get(customer_id)
    return CustomerResponse(**updated)


@router.get("/{customer_id}/purchases", response_model=List[PurchaseResponse])
def list_purchases(customer_id: int, service: CustomerService = Depends(get_customer_service)):
    purchases = service.purchases(customer_id)
    return [PurchaseResponse(**p) for p in purchases]

