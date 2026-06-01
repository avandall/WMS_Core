"""Dependency injection for Customer Service endpoints."""

from __future__ import annotations

from fastapi import Depends
from sqlalchemy.orm import Session

from app.modules.customers.application.services.customer_service import CustomerService
from app.modules.customers.infrastructure.repositories.customer_repo import CustomerRepo
from app.shared.core.database import get_session


def get_customer_repo(db: Session = Depends(get_session)) -> CustomerRepo:
    return CustomerRepo(db)


def get_customer_service(db: Session = Depends(get_session)) -> CustomerService:
    return CustomerService(customer_repo=CustomerRepo(db))

