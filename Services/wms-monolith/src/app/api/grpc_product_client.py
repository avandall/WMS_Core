from __future__ import annotations

import os

import grpc

from app.gen.wms.product.v1 import product_pb2, product_pb2_grpc


def _addr() -> str:
    return os.getenv("PRODUCT_GRPC_ADDR", "product-service:50053")


def list_products() -> list[dict]:
    with grpc.insecure_channel(_addr()) as channel:
        stub = product_pb2_grpc.ProductServiceStub(channel)
        resp = stub.ListProducts(product_pb2.ListProductsRequest(), timeout=10)
        return [
            {
                "product_id": int(p.product_id),
                "name": p.name,
                "price": float(p.price),
                "description": p.description,
            }
            for p in resp.products
        ]


def get_product(product_id: int) -> dict | None:
    with grpc.insecure_channel(_addr()) as channel:
        stub = product_pb2_grpc.ProductServiceStub(channel)
        try:
            p = stub.GetProduct(product_pb2.GetProductRequest(product_id=product_id), timeout=10)
        except grpc.RpcError as exc:
            if exc.code() == grpc.StatusCode.NOT_FOUND:
                return None
            raise
        return {
            "product_id": int(p.product_id),
            "name": p.name,
            "price": float(p.price),
            "description": p.description,
        }


def create_product(*, product_id: int | None, name: str, price: float, description: str | None) -> dict:
    with grpc.insecure_channel(_addr()) as channel:
        stub = product_pb2_grpc.ProductServiceStub(channel)
        resp = stub.CreateProduct(
            product_pb2.CreateProductRequest(
                product_id=int(product_id or 0),
                name=name,
                price=float(price),
                description=description or "",
            ),
            timeout=10,
        )
        return {
            "product_id": int(resp.product_id),
            "name": resp.name,
            "price": float(resp.price),
            "description": resp.description,
        }


def update_product(product_id: int, *, name: str | None, price: float | None, description: str | None) -> dict | None:
    with grpc.insecure_channel(_addr()) as channel:
        stub = product_pb2_grpc.ProductServiceStub(channel)
        req = product_pb2.UpdateProductRequest(
            product_id=int(product_id),
            name=name or "",
            price=float(price or 0),
            description=description or "",
        )
        try:
            resp = stub.UpdateProduct(req, timeout=10)
        except grpc.RpcError as exc:
            if exc.code() == grpc.StatusCode.NOT_FOUND:
                return None
            raise
        return {
            "product_id": int(resp.product_id),
            "name": resp.name,
            "price": float(resp.price),
            "description": resp.description,
        }


def delete_product(product_id: int) -> dict | None:
    with grpc.insecure_channel(_addr()) as channel:
        stub = product_pb2_grpc.ProductServiceStub(channel)
        try:
            resp = stub.DeleteProduct(product_pb2.DeleteProductRequest(product_id=product_id), timeout=10)
        except grpc.RpcError as exc:
            if exc.code() == grpc.StatusCode.NOT_FOUND:
                return None
            raise
        return {"message": resp.message}

