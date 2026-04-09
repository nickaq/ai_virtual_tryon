"""
Products API router.
Handles listing products with filtering/pagination and fetching individual product details.
"""
import json
import math
from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import or_

from ..database import get_db
from ..models.db_models import Product
from ..models.schemas import ProductOut, ProductListResponse, PaginationInfo

router = APIRouter(prefix="/api/products", tags=["products"])


def _format_product(product: Product) -> dict:
    """Convert a Product ORM instance to a plain dict, parsing JSON-encoded fields."""
    return {
        "id": product.id,
        "name": product.name,
        "description": product.description,
        "price": product.price,
        "category": product.category,
        "sizes": json.loads(product.sizes) if isinstance(product.sizes, str) else product.sizes,
        "colors": json.loads(product.colors) if isinstance(product.colors, str) else product.colors,
        "season": product.season,
        "composition": product.composition,
        "inStock": product.inStock,
        "imageUrl": product.imageUrl,
        "createdAt": product.createdAt,
        "updatedAt": product.updatedAt,
    }


@router.get("", response_model=ProductListResponse)
def list_products(
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    category: str | None = None,
    search: str | None = None,
    minPrice: float | None = None,
    maxPrice: float | None = None,
    season: str | None = None,
    db: Session = Depends(get_db),
):
    """List products with optional category, price, season, and text-search filters."""
    query = db.query(Product)

    # Apply filters
    if category:
        query = query.filter(Product.category == category)
    if search:
        pattern = f"%{search}%"
        query = query.filter(or_(Product.name.ilike(pattern), Product.description.ilike(pattern)))
    if minPrice is not None:
        query = query.filter(Product.price >= minPrice)
    if maxPrice is not None:
        query = query.filter(Product.price <= maxPrice)
    if season:
        query = query.filter(Product.season == season)

    # Paginate
    total = query.count()
    skip = (page - 1) * limit
    products = query.order_by(Product.createdAt.desc()).offset(skip).limit(limit).all()
    formatted = [_format_product(p) for p in products]

    return ProductListResponse(
        products=[ProductOut(**p) for p in formatted],
        pagination=PaginationInfo(
            page=page,
            limit=limit,
            total=total,
            totalPages=math.ceil(total / limit) if limit else 0,
        ),
    )


@router.get("/{product_id}", response_model=ProductOut)
def get_product(product_id: str, db: Session = Depends(get_db)):
    """Get a single product by its ID."""
    product = db.query(Product).filter(Product.id == product_id).first()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    return ProductOut(**_format_product(product))
