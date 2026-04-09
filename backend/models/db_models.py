"""
SQLAlchemy ORM models.
Mirrors the Prisma schema but without a User table (auth is handled by Next.js).
"""
from sqlalchemy import (
    Column, String, Float, Boolean, Integer, DateTime, Text, ForeignKey
)
from sqlalchemy.orm import relationship
from datetime import datetime, timezone

from ..database import Base


def _utcnow():
    return datetime.now(timezone.utc)


class Product(Base):
    __tablename__ = "Product"

    id = Column(String, primary_key=True)
    name = Column(String, nullable=False)
    description = Column(Text, nullable=False)
    price = Column(Float, nullable=False)
    category = Column(String, nullable=False)
    sizes = Column(String, nullable=False)      # JSON array as string
    colors = Column(String, nullable=False)      # JSON array as string
    season = Column(String, nullable=False)
    composition = Column(String, nullable=False)
    inStock = Column(Boolean, default=True)
    imageUrl = Column(String, nullable=True)
    createdAt = Column(DateTime, default=_utcnow)
    updatedAt = Column(DateTime, default=_utcnow, onupdate=_utcnow)

    order_items = relationship("OrderItem", back_populates="product")


class Order(Base):
    __tablename__ = "Order"

    id = Column(String, primary_key=True)
    userId = Column(String, nullable=False)  # No FK — User table managed by Prisma
    status = Column(String, default="PENDING")
    total = Column(Float, nullable=False)

    contactName = Column(String, nullable=False)
    email = Column(String, nullable=False)
    phone = Column(String, nullable=False)
    address = Column(String, nullable=False)
    city = Column(String, nullable=False)
    postalCode = Column(String, nullable=False)
    country = Column(String, nullable=False)

    createdAt = Column(DateTime, default=_utcnow)
    updatedAt = Column(DateTime, default=_utcnow, onupdate=_utcnow)

    items = relationship("OrderItem", back_populates="order")


class OrderItem(Base):
    __tablename__ = "OrderItem"

    id = Column(String, primary_key=True)
    orderId = Column(String, ForeignKey("Order.id"), nullable=False)
    productId = Column(String, ForeignKey("Product.id"), nullable=False)
    quantity = Column(Integer, nullable=False)
    selectedSize = Column(String, nullable=False)
    selectedColor = Column(String, nullable=False)
    price = Column(Float, nullable=False)

    order = relationship("Order", back_populates="items")
    product = relationship("Product", back_populates="order_items")


class Upload(Base):
    __tablename__ = "Upload"

    id = Column(String, primary_key=True)
    userId = Column(String, nullable=True)
    filename = Column(String, nullable=False)
    filepath = Column(String, unique=True, nullable=False)
    mimeType = Column(String, nullable=False)
    size = Column(Integer, nullable=False)
    createdAt = Column(DateTime, default=_utcnow)

    user_jobs = relationship("TryOnJob", foreign_keys="TryOnJob.userImageId", back_populates="user_image")
    product_jobs = relationship("TryOnJob", foreign_keys="TryOnJob.productImageId", back_populates="product_image")


class TryOnJob(Base):
    __tablename__ = "TryOnJob"

    id = Column(String, primary_key=True)
    userId = Column(String, nullable=True)  # No FK — User table managed by Prisma
    productId = Column(String, nullable=True)

    userImageId = Column(String, ForeignKey("Upload.id"), nullable=False)
    productImageId = Column(String, ForeignKey("Upload.id"), nullable=False)

    garmentType = Column(String, nullable=True)
    mode = Column(String, default="final")
    realismLevel = Column(Integer, default=3)
    preserveFace = Column(Boolean, default=True)
    preserveBackground = Column(Boolean, default=True)

    status = Column(String, default="QUEUED")
    resultPath = Column(String, nullable=True)
    qualityScore = Column(Float, nullable=True)
    errorCode = Column(String, nullable=True)
    errorMessage = Column(String, nullable=True)
    retryCount = Column(Integer, default=0)
    maxRetries = Column(Integer, default=2)

    createdAt = Column(DateTime, default=_utcnow)
    updatedAt = Column(DateTime, default=_utcnow, onupdate=_utcnow)
    startedAt = Column(DateTime, nullable=True)
    completedAt = Column(DateTime, nullable=True)

    user_image = relationship("Upload", foreign_keys=[userImageId], back_populates="user_jobs")
    product_image = relationship("Upload", foreign_keys=[productImageId], back_populates="product_jobs")


# Note: User, Account, Session, VerificationToken models are not needed
# since auth stays in Next.js. We reference User.id as a string FK only.
