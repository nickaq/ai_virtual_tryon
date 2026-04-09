"""Pydantic schemas for API request/response models."""
from pydantic import BaseModel, Field, EmailStr
from typing import Optional, List
from datetime import datetime


# ── Products ────────────────────────────────────────────────────────

class ProductOut(BaseModel):
    id: str
    name: str
    description: str
    price: float
    category: str
    sizes: list          # parsed JSON
    colors: list         # parsed JSON
    season: str
    composition: str
    inStock: bool
    imageUrl: Optional[str] = None
    createdAt: Optional[datetime] = None
    updatedAt: Optional[datetime] = None

    model_config = {"from_attributes": True}


class PaginationInfo(BaseModel):
    page: int
    limit: int
    total: int
    totalPages: int


class ProductListResponse(BaseModel):
    products: List[ProductOut]
    pagination: PaginationInfo


# ── Orders ──────────────────────────────────────────────────────────

class OrderItemCreate(BaseModel):
    productId: str
    quantity: int = Field(ge=1)
    selectedSize: str = Field(min_length=1)
    selectedColor: str = Field(min_length=1)


class OrderCreate(BaseModel):
    items: List[OrderItemCreate] = Field(min_length=1)
    contactName: str = Field(min_length=1)
    email: str = Field(min_length=1)
    phone: str = Field(min_length=1)
    address: str = Field(min_length=1)
    city: str = Field(min_length=1)
    postalCode: str = Field(min_length=1)
    country: str = Field(min_length=1)


class OrderItemOut(BaseModel):
    id: str
    productId: str
    quantity: int
    selectedSize: str
    selectedColor: str
    price: float
    product: Optional[ProductOut] = None

    model_config = {"from_attributes": True}


class OrderOut(BaseModel):
    id: str
    userId: str
    status: str
    total: float
    contactName: str
    email: str
    phone: str
    address: str
    city: str
    postalCode: str
    country: str
    createdAt: Optional[datetime] = None
    updatedAt: Optional[datetime] = None
    items: List[OrderItemOut] = []

    model_config = {"from_attributes": True}


class OrderCreateResponse(BaseModel):
    orderId: str
    status: str
    total: float


# ── Try-On ──────────────────────────────────────────────────────────

class TryOnUploadResponse(BaseModel):
    jobId: str
    status: str
    message: str


class TryOnStatusResponse(BaseModel):
    id: str
    status: str
    productId: Optional[str] = None
    userPhotoUrl: Optional[str] = None
    resultPhotoUrl: Optional[str] = None
    errorMessage: Optional[str] = None
    createdAt: Optional[datetime] = None
    updatedAt: Optional[datetime] = None


# ── Uploads ─────────────────────────────────────────────────────────

class UploadResponse(BaseModel):
    id: str
    filename: str
    filepath: str
    size: int
