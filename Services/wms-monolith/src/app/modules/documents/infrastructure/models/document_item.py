from sqlalchemy import BigInteger, Column, Float, ForeignKey, Integer
from sqlalchemy.orm import relationship

from app.shared.core.database import Base


class DocumentItemModel(Base):
    __tablename__ = "document_items"

    id = Column(Integer, primary_key=True, autoincrement=True)
    document_id = Column(Integer, ForeignKey("documents.document_id"), nullable=False)
    product_id = Column(BigInteger, ForeignKey("products.product_id"), nullable=False)
    quantity = Column(Integer, nullable=False)
    unit_price = Column(Float, nullable=False)

    document = relationship("DocumentModel", back_populates="items")
    product = relationship("ProductModel", back_populates="document_items")
