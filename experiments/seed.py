"""Seed script to populate the database with initial product data and generate mock images."""
import sys
import os
from pathlib import Path
import cv2
import numpy as np

# Add parent dir to path so we can import app modules
PROJ_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJ_ROOT))

# Ensure dummy image directory exists
PRODUCTS_DIR = PROJ_ROOT / "storage" / "products"
PRODUCTS_DIR.mkdir(parents=True, exist_ok=True)

from backend.database import SessionLocal, engine, Base
from backend.models.db_models import Product, OrderItem, Order, TryOnJob


def generate_mock_image(product_id: str, color_bgr: tuple, category: str, text_color: tuple = (255, 255, 255)):
    """Generate a clean mock garment image with text describing its category."""
    img = np.full((512, 512, 3), color_bgr, dtype=np.uint8)
    
    # Add a border
    cv2.rectangle(img, (20, 20), (492, 492), text_color, 4)
    
    # Add text
    font = cv2.FONT_HERSHEY_SIMPLEX
    cv2.putText(img, f"ID: {product_id}", (50, 100), font, 1, text_color, 2)
    cv2.putText(img, f"CAT: {category.upper()}", (50, 150), font, 1.5, text_color, 3)
    cv2.putText(img, "MOCK GARMENT", (50, 250), font, 1.2, text_color, 2)
    
    file_path = PRODUCTS_DIR / f"{product_id}.jpg"
    cv2.imwrite(str(file_path), img)
    return f"/products/{product_id}.jpg"


products = [
    {
        "id": "prod_jacket_01",
        "name": "Premium Wool Coat",
        "description": "Класичне вовняне пальто преміум якості з елегантним кроєм. Ідеально для холодної погоди.",
        "price": 299.99,
        "category": "jackets",
        "sizes": '["S", "M", "L", "XL"]',
        "colors": '["Чорний", "Темно-сірий", "Верблюжий"]',
        "season": "winter",
        "composition": "90% вовна, 10% кашемір",
        "inStock": True,
        "_mock_color": (50, 50, 50)  # Dark Gray BGR
    },
    {
        "id": "prod_pants_01",
        "name": "Slim Fit Chinos",
        "description": "Стильні брюки чінос з зауженим кроєм. Універсальний вибір для повсякденного та smart casual образу.",
        "price": 89.99,
        "category": "pants",
        "sizes": '["28", "30", "32", "34", "36"]',
        "colors": '["Бежевий", "Синій", "Чорний", "Оливковий"]',
        "season": "all-season",
        "composition": "98% бавовна, 2% еластан",
        "inStock": True,
        "_mock_color": (150, 200, 200) # Beige BGR
    },
    {
        "id": "prod_shirt_01",
        "name": "Oxford Button-Down Shirt",
        "description": "Класична оксфордська сорочка на гудзиках. Обов'язковий елемент гардеробу.",
        "price": 69.99,
        "category": "shirts",
        "sizes": '["S", "M", "L", "XL", "XXL"]',
        "colors": '["Білий", "Блакитний", "Рожевий"]',
        "season": "all-season",
        "composition": "100% бавовна",
        "inStock": True,
        "_mock_color": (255, 255, 230), # White/blueish
        "_mock_text": (50, 50, 50)
    },
    {
        "id": "prod_dress_01",
        "name": "Summer Floral Dress",
        "description": "Легке літнє плаття з квітковим принтом. Дихаюча тканина, ідеальний вибір для спекотних днів.",
        "price": 129.99,
        "category": "dress",
        "sizes": '["XS", "S", "M", "L"]',
        "colors": '["Червоний", "Синій", "Зелений"]',
        "season": "summer",
        "composition": "100% віскоза",
        "inStock": True,
        "_mock_color": (100, 100, 255) # Red BGR
    }
]


def seed():
    print("Ініціалізація бази даних та створення таблиць...")
    Base.metadata.create_all(bind=engine)
    
    db = SessionLocal()
    try:
        print("Початок seed та генерації mock-зображень...")

        # Clear existing data
        db.query(TryOnJob).delete()
        db.query(OrderItem).delete()
        db.query(Order).delete()
        db.query(Product).delete()
        db.commit()

        # Add products
        for p_data in products:
            p_data_clean = p_data.copy()
            mock_color = p_data_clean.pop("_mock_color", (100, 100, 100))
            mock_text = p_data_clean.pop("_mock_text", (255, 255, 255))
            
            # Generate mock image
            image_url = generate_mock_image(
                product_id=p_data_clean["id"], 
                color_bgr=mock_color, 
                category=p_data_clean["category"],
                text_color=mock_text
            )
            
            p_data_clean["imageUrl"] = image_url
            
            product = Product(**p_data_clean)
            db.add(product)

        db.commit()
        print(f"✓ Створено {len(products)} товарів зі згенерованими заглушками (.jpg)")

    except Exception as e:
        db.rollback()
        print(f"Помилка: {e}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    seed()
