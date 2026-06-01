from __future__ import annotations

import grpc

from app.modules.customers.application.services.customer_service import CustomerService
from app.modules.customers.infrastructure.repositories.customer_repo import CustomerRepo
from app.shared.core.database import get_session

from customer_service.gen.wms.customer.v1 import customer_pb2, customer_pb2_grpc


class CustomerServiceServicer(customer_pb2_grpc.CustomerServiceServicer):
    def _service(self) -> tuple[CustomerService, object]:
        session_gen = get_session()
        db = next(session_gen)
        return CustomerService(customer_repo=CustomerRepo(db)), db

    def CreateCustomer(self, request: customer_pb2.CreateCustomerRequest, context: grpc.ServicerContext):
        service, db = self._service()
        try:
            model = service.create(
                {
                    "name": request.name,
                    "email": request.email,
                    "phone": request.phone,
                    "address": request.address,
                }
            )
            return customer_pb2.Customer(
                customer_id=int(model.customer_id),
                name=model.name or "",
                email=model.email or "",
                phone=model.phone or "",
                address=model.address or "",
                debt_balance=float(model.debt_balance or 0),
                created_at=str(getattr(model, "created_at", "") or ""),
            )
        finally:
            try:
                db.close()
            except Exception:
                pass

    def ListCustomers(self, request: customer_pb2.ListCustomersRequest, context: grpc.ServicerContext):
        service, db = self._service()
        try:
            data = service.list()
            customers = []
            for c in data:
                customers.append(
                    customer_pb2.Customer(
                        customer_id=int(c.get("customer_id") or 0),
                        name=str(c.get("name") or ""),
                        email=str(c.get("email") or ""),
                        phone=str(c.get("phone") or ""),
                        address=str(c.get("address") or ""),
                        debt_balance=float(c.get("debt_balance") or 0),
                        created_at=str(c.get("created_at") or ""),
                    )
                )
            return customer_pb2.ListCustomersResponse(customers=customers)
        finally:
            try:
                db.close()
            except Exception:
                pass

    def GetCustomer(self, request: customer_pb2.GetCustomerRequest, context: grpc.ServicerContext):
        service, db = self._service()
        try:
            c = service.get(int(request.customer_id))
            if not c:
                context.set_code(grpc.StatusCode.NOT_FOUND)
                context.set_details("Customer not found")
                return customer_pb2.Customer()
            return customer_pb2.Customer(
                customer_id=int(c.get("customer_id") or 0),
                name=str(c.get("name") or ""),
                email=str(c.get("email") or ""),
                phone=str(c.get("phone") or ""),
                address=str(c.get("address") or ""),
                debt_balance=float(c.get("debt_balance") or 0),
                created_at=str(c.get("created_at") or ""),
            )
        finally:
            try:
                db.close()
            except Exception:
                pass

    def UpdateCustomer(self, request: customer_pb2.UpdateCustomerRequest, context: grpc.ServicerContext):
        service, db = self._service()
        try:
            customer_id = int(request.customer_id)
            existing = service.get(customer_id)
            if not existing:
                context.set_code(grpc.StatusCode.NOT_FOUND)
                context.set_details("Customer not found")
                return customer_pb2.Customer()

            payload = {}
            if request.name:
                payload["name"] = request.name
            if request.email:
                payload["email"] = request.email
            if request.phone:
                payload["phone"] = request.phone
            if request.address:
                payload["address"] = request.address

            service.update(customer_id, payload)
            updated = service.get(customer_id) or {}
            return customer_pb2.Customer(
                customer_id=int(updated.get("customer_id") or 0),
                name=str(updated.get("name") or ""),
                email=str(updated.get("email") or ""),
                phone=str(updated.get("phone") or ""),
                address=str(updated.get("address") or ""),
                debt_balance=float(updated.get("debt_balance") or 0),
                created_at=str(updated.get("created_at") or ""),
            )
        finally:
            try:
                db.close()
            except Exception:
                pass

    def UpdateDebt(self, request: customer_pb2.UpdateDebtRequest, context: grpc.ServicerContext):
        service, db = self._service()
        try:
            service.update_debt(int(request.customer_id), float(request.amount))
            return customer_pb2.UpdateDebtResponse(message="Debt updated", delta=float(request.amount))
        finally:
            try:
                db.close()
            except Exception:
                pass

    def ListPurchases(self, request: customer_pb2.ListPurchasesRequest, context: grpc.ServicerContext):
        service, db = self._service()
        try:
            purchases = service.purchases(int(request.customer_id))
            rows = []
            for p in purchases:
                rows.append(
                    customer_pb2.Purchase(
                        purchase_id=int(p.get("purchase_id") or 0),
                        customer_id=int(p.get("customer_id") or request.customer_id),
                        amount=float(p.get("amount") or 0),
                        created_at=str(p.get("created_at") or ""),
                    )
                )
            return customer_pb2.ListPurchasesResponse(purchases=rows)
        finally:
            try:
                db.close()
            except Exception:
                pass


add_CustomerServiceServicer_to_server = customer_pb2_grpc.add_CustomerServiceServicer_to_server

