from __future__ import annotations

import grpc

from shared_utils.events import get_publisher

from app.modules.inventory.infrastructure.repositories.inventory_repo import InventoryRepo
from app.modules.products.application.services.product_service import ProductService
from app.modules.products.infrastructure.repositories.product_repo import ProductRepo
from app.shared.core.database import get_session

from product_service.gen.wms.product.v1 import product_pb2, product_pb2_grpc


class ProductServiceServicer(product_pb2_grpc.ProductServiceServicer):
    _publisher = get_publisher("product-service")

    @staticmethod
    def _request_id(context: grpc.ServicerContext) -> str | None:
        for k, v in context.invocation_metadata() or []:
            if k.lower() == "x-request-id":
                return v
        return None

    def _service(self) -> tuple[ProductService, object]:
        session_gen = get_session()
        db = next(session_gen)
        return ProductService(ProductRepo(db), InventoryRepo(db)), db

    def ListProducts(self, request: product_pb2.ListProductsRequest, context: grpc.ServicerContext):
        service, db = self._service()
        try:
            products = service.get_all_products()
            rows = [
                product_pb2.Product(
                    product_id=int(p.product_id),
                    name=p.name or "",
                    price=float(p.price or 0),
                    description=p.description or "",
                )
                for p in products
            ]
            return product_pb2.ListProductsResponse(products=rows)
        finally:
            try:
                db.close()
            except Exception:
                pass

    def GetProduct(self, request: product_pb2.GetProductRequest, context: grpc.ServicerContext):
        service, db = self._service()
        try:
            p = service.get_product_details(int(request.product_id))
            return product_pb2.Product(
                product_id=int(p.product_id),
                name=p.name or "",
                price=float(p.price or 0),
                description=p.description or "",
            )
        except Exception:
            context.set_code(grpc.StatusCode.NOT_FOUND)
            context.set_details("Product not found")
            return product_pb2.Product()
        finally:
            try:
                db.close()
            except Exception:
                pass

    def CreateProduct(self, request: product_pb2.CreateProductRequest, context: grpc.ServicerContext):
        service, db = self._service()
        try:
            p = service.create_product(
                product_id=int(request.product_id) if request.product_id else None,
                name=request.name,
                price=float(request.price),
                description=request.description,
            )
            self._publisher.publish(
                event_type="ProductCreated",
                payload={
                    "request_id": self._request_id(context),
                    "entity_type": "product",
                    "entity_id": int(p.product_id),
                    "product_id": int(p.product_id),
                    "name": p.name,
                },
            )
            return product_pb2.Product(
                product_id=int(p.product_id),
                name=p.name or "",
                price=float(p.price or 0),
                description=p.description or "",
            )
        finally:
            try:
                db.close()
            except Exception:
                pass

    def UpdateProduct(self, request: product_pb2.UpdateProductRequest, context: grpc.ServicerContext):
        service, db = self._service()
        try:
            p = service.update_product(
                product_id=int(request.product_id),
                name=request.name or None,
                price=float(request.price) if request.price else None,
                description=request.description or None,
            )
            self._publisher.publish(
                event_type="ProductUpdated",
                payload={
                    "request_id": self._request_id(context),
                    "entity_type": "product",
                    "entity_id": int(p.product_id),
                    "product_id": int(p.product_id),
                    "name": p.name,
                },
            )
            return product_pb2.Product(
                product_id=int(p.product_id),
                name=p.name or "",
                price=float(p.price or 0),
                description=p.description or "",
            )
        except Exception:
            context.set_code(grpc.StatusCode.NOT_FOUND)
            context.set_details("Product not found")
            return product_pb2.Product()
        finally:
            try:
                db.close()
            except Exception:
                pass

    def DeleteProduct(self, request: product_pb2.DeleteProductRequest, context: grpc.ServicerContext):
        service, db = self._service()
        try:
            product_id = int(request.product_id)
            service.delete_product(product_id)
            self._publisher.publish(
                event_type="ProductDeleted",
                payload={
                    "request_id": self._request_id(context),
                    "entity_type": "product",
                    "entity_id": product_id,
                    "product_id": product_id,
                },
            )
            return product_pb2.DeleteProductResponse(
                message=f"Product {product_id} deleted successfully"
            )
        except Exception:
            context.set_code(grpc.StatusCode.NOT_FOUND)
            context.set_details("Product not found")
            return product_pb2.DeleteProductResponse(message="Product not found")
        finally:
            try:
                db.close()
            except Exception:
                pass


add_ProductServiceServicer_to_server = product_pb2_grpc.add_ProductServiceServicer_to_server
