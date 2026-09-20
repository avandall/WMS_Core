from __future__ import annotations

import asyncio
import grpc

from shared_utils.events import get_publisher

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
        return ProductService(ProductRepo(db), session=db), db

    def _to_proto_product(self, p) -> product_pb2.Product:
        uom_protos = []
        if hasattr(p, "uoms") and p.uoms:
            for u in p.uoms:
                uom_protos.append(
                    product_pb2.ProductUOM(
                        uom_code=u.uom_code,
                        conversion_factor=float(u.conversion_factor),
                        to_uom_code=u.to_uom_code,
                    )
                )
        return product_pb2.Product(
            product_id=int(p.product_id),
            name=p.name or "",
            price=float(p.price or 0),
            description=p.description or "",
            length_cm=float(getattr(p, "length_cm", 0.0)),
            width_cm=float(getattr(p, "width_cm", 0.0)),
            height_cm=float(getattr(p, "height_cm", 0.0)),
            gross_weight_kg=float(getattr(p, "gross_weight_kg", 0.0)),
            net_weight_kg=float(getattr(p, "net_weight_kg", 0.0)),
            volume_cbm=float(getattr(p, "volume_cbm", 0.0)),
            base_uom=getattr(p, "base_uom", "EACH"),
            uoms=uom_protos,
        )

    def ListProducts(self, request: product_pb2.ListProductsRequest, context: grpc.ServicerContext):
        service, db = self._service()
        try:
            products = asyncio.run(service.get_all_products())
            rows = [self._to_proto_product(p) for p in products]
            return product_pb2.ListProductsResponse(products=rows)
        finally:
            try:
                db.close()
            except Exception:
                pass

    def GetProduct(self, request: product_pb2.GetProductRequest, context: grpc.ServicerContext):
        service, db = self._service()
        try:
            p = asyncio.run(service.get_product_details(int(request.product_id)))
            return self._to_proto_product(p)
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
            p = asyncio.run(
                service.create_product(
                    product_id=int(request.product_id) if request.product_id else None,
                    name=request.name,
                    price=float(request.price),
                    description=request.description,
                    length_cm=float(getattr(request, "length_cm", 0.0)),
                    width_cm=float(getattr(request, "width_cm", 0.0)),
                    height_cm=float(getattr(request, "height_cm", 0.0)),
                    gross_weight_kg=float(getattr(request, "gross_weight_kg", 0.0)),
                    net_weight_kg=float(getattr(request, "net_weight_kg", 0.0)),
                    base_uom=getattr(request, "base_uom", "EACH"),
                )
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
            return self._to_proto_product(p)
        finally:
            try:
                db.close()
            except Exception:
                pass

    def UpdateProduct(self, request: product_pb2.UpdateProductRequest, context: grpc.ServicerContext):
        service, db = self._service()
        try:
            p = asyncio.run(
                service.update_product(
                    product_id=int(request.product_id),
                    name=request.name or None,
                    price=float(request.price) if request.price else None,
                    description=request.description or None,
                    length_cm=float(request.length_cm) if getattr(request, "length_cm", None) else None,
                    width_cm=float(request.width_cm) if getattr(request, "width_cm", None) else None,
                    height_cm=float(request.height_cm) if getattr(request, "height_cm", None) else None,
                    gross_weight_kg=float(request.gross_weight_kg) if getattr(request, "gross_weight_kg", None) else None,
                    net_weight_kg=float(request.net_weight_kg) if getattr(request, "net_weight_kg", None) else None,
                    base_uom=getattr(request, "base_uom", None) or None,
                )
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
            return self._to_proto_product(p)
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
            asyncio.run(service.delete_product(product_id))
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
