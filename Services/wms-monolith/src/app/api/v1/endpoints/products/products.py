from __future__ import annotations

import os

from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile

from app.api.auth_deps import get_current_user, require_permissions
from app.api.authorization.product_authorizers import ProductAuthorizer
from app.api.api_deps import get_product_service
from app.api.grpc_product_client import (
    create_product as grpc_create_product,
    delete_product as grpc_delete_product,
    get_product as grpc_get_product,
    list_products as grpc_list_products,
    update_product as grpc_update_product,
)
from app.modules.products.application.dtos.product import ProductCreate, ProductResponse, ProductUpdate
from app.modules.products.application.services.product_service import ProductService
from app.shared.core.permissions import Permission

router = APIRouter(dependencies=[Depends(get_current_user)])


@router.get(
    "/",
    response_model=list[ProductResponse],
    dependencies=[Depends(require_permissions(Permission.VIEW_PRODUCTS))],
)
async def get_all_products(request: Request, service: ProductService = Depends(get_product_service)):
    if os.getenv("PRODUCT_GRPC", "1") == "1":
        products = grpc_list_products()
        return [ProductResponse(**p) for p in products]
    products = service.get_all_products()
    return [ProductResponse.from_domain(product) for product in products]


@router.post(
    "/",
    response_model=ProductResponse,
    status_code=200,
    dependencies=[Depends(require_permissions(Permission.VIEW_PRODUCTS))],
)
async def create_product(
    product: ProductCreate, 
    request: Request,
    service: ProductService = Depends(get_product_service),
    user=Depends(get_current_user),
):
    if os.getenv("PRODUCT_GRPC", "1") == "1":
        created = grpc_create_product(
            product_id=getattr(product, "product_id", None),
            name=product.name,
            price=float(product.price),
            description=product.description,
        )
        return ProductResponse(**created)
    ProductAuthorizer.can_create_product(user.role)
    
    created_product = service.create_product(
        product_id=product.product_id,
        name=product.name,
        price=product.price,
        description=product.description,
    )
    return ProductResponse.from_domain(created_product)


@router.get(
    "/{product_id}",
    response_model=ProductResponse,
    dependencies=[Depends(require_permissions(Permission.VIEW_PRODUCTS))],
)
async def get_product(
    product_id: int,
    request: Request,
    service: ProductService = Depends(get_product_service),
):
    if os.getenv("PRODUCT_GRPC", "1") == "1":
        p = grpc_get_product(product_id)
        if not p:
            raise HTTPException(status_code=404, detail="Product not found")
        return ProductResponse(**p)
    product = service.get_product_details(product_id)
    return ProductResponse.from_domain(product)


@router.put("/{product_id}", response_model=ProductResponse)
async def update_product(
    product_id: int,
    product_update: ProductUpdate,
    request: Request,
    service: ProductService = Depends(get_product_service),
    user=Depends(get_current_user),
):
    if os.getenv("PRODUCT_GRPC", "1") == "1":
        updated = grpc_update_product(
            product_id,
            name=product_update.name,
            price=float(product_update.price) if product_update.price is not None else None,
            description=product_update.description,
        )
        if not updated:
            raise HTTPException(status_code=404, detail="Product not found")
        return ProductResponse(**updated)
    ProductAuthorizer.can_update_product(user.role, product_update)

    updated_product = service.update_product(
        product_id=product_id,
        name=product_update.name,
        price=product_update.price,
        description=product_update.description,
    )
    return ProductResponse.from_domain(updated_product)


@router.delete(
    "/{product_id}",
    dependencies=[Depends(require_permissions(Permission.MANAGE_PRODUCTS))],
)
async def delete_product(
    product_id: int,
    request: Request,
    service: ProductService = Depends(get_product_service),
):
    if os.getenv("PRODUCT_GRPC", "1") == "1":
        resp = grpc_delete_product(product_id)
        if not resp:
            raise HTTPException(status_code=404, detail="Product not found")
        return resp
    service.delete_product(product_id)
    return {"message": f"Product {product_id} deleted successfully"}


@router.post(
    "/import-csv",
    dependencies=[Depends(require_permissions(Permission.MANAGE_PRODUCTS))],
)
async def import_products_csv(
    file: UploadFile = File(...),
    service: ProductService = Depends(get_product_service),
):
    if file.content_type not in {"text/csv", "application/vnd.ms-excel", "application/csv"}:
        raise HTTPException(status_code=400, detail="CSV file required")
    content = await file.read()
    result = service.import_products_from_csv(content)
    return result
