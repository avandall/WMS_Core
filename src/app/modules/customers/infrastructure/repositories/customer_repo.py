from typing import List, Optional
from sqlalchemy.orm import Session
from sqlalchemy import select
from app.shared.domain.customer_repo import ICustomerRepo
from app.infrastructure.persistence.models import CustomerModel, CustomerPurchaseModel


class CustomerRepo(ICustomerRepo):
    def __init__(self, session: Session):
        self.session = session
        self.auto_commit = True

    def set_auto_commit(self, enabled: bool) -> None:
        self.auto_commit = enabled

    def _commit_if_auto(self):
        if self.auto_commit:
            self.session.commit()

    def create(self, data: dict):
        model = CustomerModel(**data)
        self.session.add(model)
        self._commit_if_auto()
        return model

    def get(self, customer_id: int):
        return self.session.get(CustomerModel, customer_id)

    def get_all(self) -> List[CustomerModel]:
        # Ensure any pending transactions are flushed
        self.session.flush()
        result = self.session.execute(select(CustomerModel)).scalars().all()
        # Load all attributes before returning to prevent lazy load issues
        for customer in result:
            _ = customer.debt_balance  # Force attribute load
        return result

    def update_debt(self, customer_id: int, delta: float) -> None:
        customer = self.session.get(CustomerModel, customer_id)
        if not customer:
            return
        customer.debt_balance = (customer.debt_balance or 0) + delta
        self._commit_if_auto()
        if customer in self.session:
            self.session.refresh(customer)

    def record_purchase(self, customer_id: int, document_id: int, total_value: float) -> None:
        purchase = CustomerPurchaseModel(
            customer_id=customer_id,
            document_id=document_id,
            total_value=total_value,
        )
        self.session.add(purchase)
        self.update_debt(customer_id, total_value)
        self._commit_if_auto()

    def list_purchases(self, customer_id: int) -> List[dict]:
        purchases = (
            self.session.execute(
                select(CustomerPurchaseModel).where(CustomerPurchaseModel.customer_id == customer_id)
            )
            .scalars()
            .all()
        )
        return [
            {
                "document_id": p.document_id,
                "total_value": p.total_value,
                "created_at": p.created_at,
            }
            for p in purchases
        ]

    def update(self, customer_id: int, data: dict) -> None:
        customer = self.session.get(CustomerModel, customer_id)
        if not customer:
            return
        for field, value in data.items():
            if hasattr(customer, field) and value is not None:
                setattr(customer, field, value)
        self._commit_if_auto()
        if customer in self.session:
            self.session.refresh(customer)
