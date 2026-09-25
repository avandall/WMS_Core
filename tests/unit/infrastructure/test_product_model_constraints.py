"""
Unit tests for ProductModel constraints (TASK-079 / TECH-01).
Verifies UniqueConstraint("name", name="uq_products_name") and data integrity.
"""
import pytest
from sqlalchemy import create_engine, UniqueConstraint
from sqlalchemy.orm import sessionmaker
from sqlalchemy.exc import IntegrityError

from app.shared.core.database import Base
from app.modules.products.infrastructure.models.product import ProductModel


class TestProductModelConstraints:
    """Test table constraints on ProductModel."""

    @pytest.fixture
    def db_session(self):
        """In-memory SQLite session isolated for ProductModel."""
        engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(bind=engine)
        Session = sessionmaker(bind=engine)
        session = Session()
        try:
            yield session
        finally:
            session.close()
            Base.metadata.drop_all(bind=engine)

    def test_unique_constraint_metadata(self):
        """ProductModel table args must contain UniqueConstraint on 'name' named 'uq_products_name'."""
        constraints = [
            c for c in ProductModel.__table__.constraints
            if isinstance(c, UniqueConstraint)
        ]
        uq_names = [c.name for c in constraints]
        assert "uq_products_name" in uq_names

        uq = next(c for c in constraints if c.name == "uq_products_name")
        col_names = [col.name for col in uq.columns]
        assert "name" in col_names

    def test_duplicate_product_name_raises_integrity_error(self, db_session):
        """Inserting two products with the exact same name must raise IntegrityError."""
        p1 = ProductModel(
            product_id=1,
            name="15\" Professional Laptop",
            price=1200.0,
            description="Laptop 1",
        )
        db_session.add(p1)
        db_session.commit()

        p2 = ProductModel(
            product_id=2,
            name="15\" Professional Laptop",
            price=1300.0,
            description="Laptop 2 duplicate name",
        )
        db_session.add(p2)
        with pytest.raises(IntegrityError):
            db_session.commit()
        db_session.rollback()

    def test_distinct_product_names_succeed(self, db_session):
        """Distinct product names can be persisted without conflict."""
        p1 = ProductModel(product_id=10, name="15\" Laptop", price=1000.0)
        p2 = ProductModel(product_id=20, name="17\" Laptop", price=1400.0)
        db_session.add_all([p1, p2])
        db_session.commit()

        assert db_session.get(ProductModel, 10).name == "15\" Laptop"
        assert db_session.get(ProductModel, 20).name == "17\" Laptop"
