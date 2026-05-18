from __future__ import annotations

import os

import grpc

from app.gen.wms.customer.v1 import customer_pb2, customer_pb2_grpc


def _addr() -> str:
    return os.getenv("CUSTOMER_GRPC_ADDR", "customer-service:50052")


def create_customer(*, name: str, email: str, phone: str, address: str) -> dict:
    with grpc.insecure_channel(_addr()) as channel:
        stub = customer_pb2_grpc.CustomerServiceStub(channel)
        resp = stub.CreateCustomer(
            customer_pb2.CreateCustomerRequest(name=name, email=email, phone=phone, address=address),
            timeout=10,
        )
        return {
            "customer_id": int(resp.customer_id),
            "name": resp.name,
            "email": resp.email,
            "phone": resp.phone,
            "address": resp.address,
            "debt_balance": float(resp.debt_balance),
            "created_at": resp.created_at,
        }


def list_customers() -> list[dict]:
    with grpc.insecure_channel(_addr()) as channel:
        stub = customer_pb2_grpc.CustomerServiceStub(channel)
        resp = stub.ListCustomers(customer_pb2.ListCustomersRequest(), timeout=10)
        return [
            {
                "customer_id": int(c.customer_id),
                "name": c.name,
                "email": c.email,
                "phone": c.phone,
                "address": c.address,
                "debt_balance": float(c.debt_balance),
                "created_at": c.created_at,
            }
            for c in resp.customers
        ]


def get_customer(customer_id: int) -> dict | None:
    with grpc.insecure_channel(_addr()) as channel:
        stub = customer_pb2_grpc.CustomerServiceStub(channel)
        try:
            c = stub.GetCustomer(customer_pb2.GetCustomerRequest(customer_id=customer_id), timeout=10)
        except grpc.RpcError as exc:
            if exc.code() == grpc.StatusCode.NOT_FOUND:
                return None
            raise
        return {
            "customer_id": int(c.customer_id),
            "name": c.name,
            "email": c.email,
            "phone": c.phone,
            "address": c.address,
            "debt_balance": float(c.debt_balance),
            "created_at": c.created_at,
        }


def update_customer(customer_id: int, *, name: str | None, email: str | None, phone: str | None, address: str | None) -> dict | None:
    with grpc.insecure_channel(_addr()) as channel:
        stub = customer_pb2_grpc.CustomerServiceStub(channel)
        req = customer_pb2.UpdateCustomerRequest(
            customer_id=customer_id,
            name=name or "",
            email=email or "",
            phone=phone or "",
            address=address or "",
        )
        try:
            c = stub.UpdateCustomer(req, timeout=10)
        except grpc.RpcError as exc:
            if exc.code() == grpc.StatusCode.NOT_FOUND:
                return None
            raise
        return {
            "customer_id": int(c.customer_id),
            "name": c.name,
            "email": c.email,
            "phone": c.phone,
            "address": c.address,
            "debt_balance": float(c.debt_balance),
            "created_at": c.created_at,
        }


def update_debt(customer_id: int, amount: float) -> dict:
    with grpc.insecure_channel(_addr()) as channel:
        stub = customer_pb2_grpc.CustomerServiceStub(channel)
        resp = stub.UpdateDebt(customer_pb2.UpdateDebtRequest(customer_id=customer_id, amount=amount), timeout=10)
        return {"message": resp.message, "delta": float(resp.delta)}


def list_purchases(customer_id: int) -> list[dict]:
    with grpc.insecure_channel(_addr()) as channel:
        stub = customer_pb2_grpc.CustomerServiceStub(channel)
        resp = stub.ListPurchases(customer_pb2.ListPurchasesRequest(customer_id=customer_id), timeout=10)
        return [
            {
                "purchase_id": int(p.purchase_id),
                "customer_id": int(p.customer_id),
                "amount": float(p.amount),
                "created_at": p.created_at,
            }
            for p in resp.purchases
        ]

