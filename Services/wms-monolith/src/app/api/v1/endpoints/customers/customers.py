from __future__ import annotations

import os
from typing import List

from fastapi import APIRouter, Depends, HTTPException, Request, status

from app.api.auth_deps import get_current_user, require_permissions
from app.api.api_deps import get_customer_service
from app.api.service_proxy import proxy_request
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
async def create_customer(
    payload: CustomerCreate,
    request: Request,
    service: CustomerService = Depends(get_customer_service),
):
    base = os.getenv("CUSTOMER_SERVICE_URL")
    if base:
        return await proxy_request(request, base_url=base)
    model = service.create(payload.model_dump())
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
async def list_customers(request: Request, service: CustomerService = Depends(get_customer_service)):
    base = os.getenv("CUSTOMER_SERVICE_URL")
    if base:
        return await proxy_request(request, base_url=base)
    data = service.list()
    return [CustomerResponse(**c) for c in data]


@router.get("/{customer_id}", response_model=CustomerDetailResponse)
async def get_customer(
    customer_id: int,
    request: Request,
    service: CustomerService = Depends(get_customer_service),
):
    base = os.getenv("CUSTOMER_SERVICE_URL")
    if base:
        return await proxy_request(request, base_url=base)
    c = service.get(customer_id)
    if not c:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Customer not found")
    return CustomerDetailResponse(**c)


@router.patch("/{customer_id}/debt")
async def update_debt(
    customer_id: int,
    payload: DebtUpdate,
    request: Request,
    service: CustomerService = Depends(get_customer_service),
):
    base = os.getenv("CUSTOMER_SERVICE_URL")
    if base:
        return await proxy_request(request, base_url=base)
    service.update_debt(customer_id, payload.amount)
    return {"message": "Debt updated", "delta": payload.amount}


@router.patch(
    "/{customer_id}",
    response_model=CustomerResponse,
    dependencies=[Depends(require_permissions(Permission.MANAGE_PRODUCTS))],
)
async def update_customer(
    customer_id: int,
    payload: CustomerUpdate,
    request: Request,
    service: CustomerService = Depends(get_customer_service),
):
    base = os.getenv("CUSTOMER_SERVICE_URL")
    if base:
        return await proxy_request(request, base_url=base)
    existing = service.get(customer_id)
    if not existing:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Customer not found")
    service.update(customer_id, payload.model_dump(exclude_unset=True))
    updated = service.get(customer_id)
    return CustomerResponse(**updated)


@router.get("/{customer_id}/purchases", response_model=List[PurchaseResponse])
async def list_purchases(
    customer_id: int,
    request: Request,
    service: CustomerService = Depends(get_customer_service),
):
    base = os.getenv("CUSTOMER_SERVICE_URL")
    if base:
        return await proxy_request(request, base_url=base)
    purchases = service.purchases(customer_id)
    return [PurchaseResponse(**p) for p in purchases]
