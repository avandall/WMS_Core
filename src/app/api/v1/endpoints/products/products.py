from __future__ import annotations

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile

from app.api.auth_deps import get_current_user, require_permissions
from app.api.authorization.product_authorizers import ProductAuthorizer
from app.api.api_deps import get_product_service
from app.modules.products.application.dtos.product import ProductCreate, ProductResponse, ProductUpdate
from app.modules.products.application.services.product_service import ProductService
from app.shared.core.permissions import Permission

router = APIRouter(dependencies=[Depends(get_current_user)])


@router.get(
    "/",
    response_model=list[ProductResponse],
    dependencies=[Depends(require_permissions(Permission.VIEW_PRODUCTS))],
)
async def get_all_products(service: ProductService = Depends(get_product_service)):
    products = await service.get_all_products()
    return [ProductResponse.from_domain(product) for product in products]


@router.post(
    "/",
    response_model=ProductResponse,
    status_code=200,
    dependencies=[Depends(require_permissions(Permission.VIEW_PRODUCTS))],
)
async def create_product(
    product: ProductCreate, 
    service: ProductService = Depends(get_product_service),
    user=Depends(get_current_user),
):
    ProductAuthorizer.can_create_product(user.role)
    
    created_product = await service.create_product(
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
async def get_product(product_id: int, service: ProductService = Depends(get_product_service)):
    product = await service.get_product_details(product_id)
    return ProductResponse.from_domain(product)


@router.put("/{product_id}", response_model=ProductResponse)
async def update_product(
    product_id: int,
    product_update: ProductUpdate,
    service: ProductService = Depends(get_product_service),
    user=Depends(get_current_user),
):
    ProductAuthorizer.can_update_product(user.role, product_update)

    updated_product = await service.update_product(
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
async def delete_product(product_id: int, service: ProductService = Depends(get_product_service)):
    await service.delete_product(product_id)
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
    result = await service.import_products_from_csv(content)
    return result

