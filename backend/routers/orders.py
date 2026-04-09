"""
Orders API router.
Handles order creation and listing recent orders with their items.
"""
import json
import uuid
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session, joinedload

from ..database import get_db
from ..models.db_models import Order, OrderItem, Product
from ..models.schemas import OrderCreate, OrderCreateResponse


router = APIRouter(prefix="/api/orders", tags=["orders"])


def _cuid() -> str:
    """Generate a short unique ID (similar to cuid)."""
    return uuid.uuid4().hex[:25]


def _format_product_for_order(product: Product) -> dict:
    """Serialize a Product ORM instance for inclusion in an order response."""
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


@router.post("", response_model=OrderCreateResponse, status_code=201)
def create_order(order_data: OrderCreate, db: Session = Depends(get_db)):
    """Create a new order from the cart items and shipping details."""
    # Validate that all referenced products exist
    product_ids = [item.productId for item in order_data.items]
    products = db.query(Product).filter(Product.id.in_(product_ids)).all()

    if len(products) != len(product_ids):
        raise HTTPException(status_code=400, detail="Some products were not found")

    product_map = {p.id: p for p in products}

    # Build order items and calculate total
    total = 0.0
    order_items = []
    for item in order_data.items:
        product = product_map[item.productId]
        item_total = product.price * item.quantity
        total += item_total

        order_items.append(
            OrderItem(
                id=_cuid(),
                productId=item.productId,
                quantity=item.quantity,
                selectedSize=item.selectedSize,
                selectedColor=item.selectedColor,
                price=product.price,
            )
        )

    # Persist order with items
    order = Order(
        id=_cuid(),
        userId="guest",  # Auth is handled separately in the Next.js layer
        status="PENDING",
        total=total,
        contactName=order_data.contactName,
        email=order_data.email,
        phone=order_data.phone,
        address=order_data.address,
        city=order_data.city,
        postalCode=order_data.postalCode,
        country=order_data.country,
    )

    for oi in order_items:
        oi.orderId = order.id
    order.items = order_items

    db.add(order)
    db.commit()
    db.refresh(order)

    return OrderCreateResponse(orderId=order.id, status=order.status, total=order.total)


@router.get("")
def list_orders(db: Session = Depends(get_db)):
    """List the 20 most recent orders with their items and product details."""
    orders = (
        db.query(Order)
        .options(joinedload(Order.items).joinedload(OrderItem.product))
        .order_by(Order.createdAt.desc())
        .limit(20)
        .all()
    )

    result = []
    for order in orders:
        order_dict = {
            "id": order.id,
            "userId": order.userId,
            "status": order.status,
            "total": order.total,
            "contactName": order.contactName,
            "email": order.email,
            "phone": order.phone,
            "address": order.address,
            "city": order.city,
            "postalCode": order.postalCode,
            "country": order.country,
            "createdAt": order.createdAt,
            "updatedAt": order.updatedAt,
            "items": [
                {
                    "id": item.id,
                    "productId": item.productId,
                    "quantity": item.quantity,
                    "selectedSize": item.selectedSize,
                    "selectedColor": item.selectedColor,
                    "price": item.price,
                    "product": _format_product_for_order(item.product) if item.product else None,
                }
                for item in order.items
            ],
        }
        result.append(order_dict)

    return {"orders": result}
