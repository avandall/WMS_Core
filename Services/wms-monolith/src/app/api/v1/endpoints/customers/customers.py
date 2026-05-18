from __future__ import annotations

import os
from typing import List

from fastapi import APIRouter, Depends, HTTPException, Request, status

from app.api.auth_deps import get_current_user, require_permissions
from app.api.api_deps import get_customer_service
from app.api.grpc_customer_client import (
    create_customer as grpc_create_customer,
    get_customer as grpc_get_customer,
    list_customers as grpc_list_customers,
    list_purchases as grpc_list_purchases,
    update_customer as grpc_update_customer,
    update_debt as grpc_update_debt,
)
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
    if os.getenv("CUSTOMER_GRPC", "1") == "1":
        model = grpc_create_customer(
            name=payload.name,
            email=payload.email or "",
            phone=payload.phone or "",
            address=payload.address or "",
        )
        return CustomerResponse(**model)
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
    if os.getenv("CUSTOMER_GRPC", "1") == "1":
        data = grpc_list_customers()
        return [CustomerResponse(**c) for c in data]
    data = service.list()
    return [CustomerResponse(**c) for c in data]


@router.get("/{customer_id}", response_model=CustomerDetailResponse)
async def get_customer(
    customer_id: int,
    request: Request,
    service: CustomerService = Depends(get_customer_service),
):
    if os.getenv("CUSTOMER_GRPC", "1") == "1":
        c = grpc_get_customer(customer_id)
        if not c:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Customer not found")
        return CustomerDetailResponse(**c)
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
    if os.getenv("CUSTOMER_GRPC", "1") == "1":
        return grpc_update_debt(customer_id, float(payload.amount))
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
    if os.getenv("CUSTOMER_GRPC", "1") == "1":
        updated = grpc_update_customer(
            customer_id,
            name=payload.name if payload.name is not None else None,
            email=payload.email if payload.email is not None else None,
            phone=payload.phone if payload.phone is not None else None,
            address=payload.address if payload.address is not None else None,
        )
        if not updated:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Customer not found")
        return CustomerResponse(**updated)
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
    if os.getenv("CUSTOMER_GRPC", "1") == "1":
        purchases = grpc_list_purchases(customer_id)
        return [PurchaseResponse(**p) for p in purchases]
    purchases = service.purchases(customer_id)
    return [PurchaseResponse(**p) for p in purchases]
