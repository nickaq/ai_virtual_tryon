"""Seed script to populate the database with initial product data."""
import sys
import os

# Add parent dir to path so we can import app modules
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.database import SessionLocal, engine, Base
from app.models.db_models import Product, OrderItem, Order, TryOnJob
import uuid


def _cuid() -> str:
    return uuid.uuid4().hex[:25]


products = [
    {
        "name": "Premium Wool Coat",
        "description": "Класичне вовняне пальто преміум якості з елегантним кроєм. Ідеально для холодної погоди.",
        "price": 299.99,
        "category": "jackets",
        "sizes": '["S", "M", "L", "XL"]',
        "colors": '["Чорний", "Темно-сірий", "Верблюжий"]',
        "season": "winter",
        "composition": "90% вовна, 10% кашемір",
        "inStock": True,
    },
    {
        "name": "Slim Fit Chinos",
        "description": "Стильні брюки чінос з зауженим кроєм. Універсальний вибір для повсякденного та smart casual образу.",
        "price": 89.99,
        "category": "pants",
        "sizes": '["28", "30", "32", "34", "36"]',
        "colors": '["Бежевий", "Синій", "Чорний", "Оливковий"]',
        "season": "all-season",
        "composition": "98% бавовна, 2% еластан",
        "inStock": True,
    },
    {
        "name": "Oxford Button-Down Shirt",
        "description": "Класична оксфордська сорочка на гудзиках. Обов'язковий елемент гардеробу.",
        "price": 69.99,
        "category": "shirts",
        "sizes": '["S", "M", "L", "XL", "XXL"]',
        "colors": '["Білий", "Блакитний", "Рожевий"]',
        "season": "all-season",
        "composition": "100% бавовна",
        "inStock": True,
    },
    {
        "name": "Leather Chelsea Boots",
        "description": "Преміум шкіряні черевики челсі з еластичними вставками по боках.",
        "price": 199.99,
        "category": "shoes",
        "sizes": '["40", "41", "42", "43", "44", "45"]',
        "colors": '["Чорний", "Коричневий"]',
        "season": "fall",
        "composition": "100% натуральна шкіра",
        "inStock": True,
    },
    {
        "name": "Designer Leather Wallet",
        "description": "Компактний шкіряний гаманець ручної роботи з RFID захистом.",
        "price": 79.99,
        "category": "accessories",
        "sizes": '["One Size"]',
        "colors": '["Чорний", "Коричневий", "Темно-синій"]',
        "season": "all-season",
        "composition": "100% натуральна шкіра",
        "inStock": True,
    },
    {
        "name": "Denim Jacket",
        "description": "Класична джинсова куртка trucker style. Вічний тренд.",
        "price": 119.99,
        "category": "jackets",
        "sizes": '["S", "M", "L", "XL"]',
        "colors": '["Світло-синій", "Темно-синій", "Чорний"]',
        "season": "spring",
        "composition": "100% бавовна",
        "inStock": True,
    },
    {
        "name": "Linen Summer Shirt",
        "description": "Легка лляна сорочка для спекотних днів. Дихаюча тканина.",
        "price": 59.99,
        "category": "shirts",
        "sizes": '["S", "M", "L", "XL"]',
        "colors": '["Білий", "Бежевий", "Блакитний"]',
        "season": "summer",
        "composition": "100% льон",
        "inStock": True,
    },
    {
        "name": "Cargo Pants",
        "description": "Практичні брюки cargo з великими кишенями. Street style.",
        "price": 99.99,
        "category": "pants",
        "sizes": '["28", "30", "32", "34"]',
        "colors": '["Хакі", "Чорний", "Темно-зелений"]',
        "season": "all-season",
        "composition": "65% поліестер, 35% бавовна",
        "inStock": True,
    },
    {
        "name": "White Sneakers",
        "description": "Мінімалістичні білі кросівки. Must-have для casual образу.",
        "price": 89.99,
        "category": "shoes",
        "sizes": '["40", "41", "42", "43", "44"]',
        "colors": '["Білий"]',
        "season": "all-season",
        "composition": "Шкіра та текстиль",
        "inStock": True,
    },
    {
        "name": "Wool Scarf",
        "description": "М'який вовняний шарф з класичним візерунком.",
        "price": 49.99,
        "category": "accessories",
        "sizes": '["One Size"]',
        "colors": '["Сірий", "Темно-синій", "Бордовий"]',
        "season": "winter",
        "composition": "100% мериносова вовна",
        "inStock": True,
    },
]


def seed():
    db = SessionLocal()
    try:
        print("Початок seed...")

        # Clear existing data
        db.query(TryOnJob).delete()
        db.query(OrderItem).delete()
        db.query(Order).delete()
        db.query(Product).delete()
        db.commit()

        # Add products
        for p_data in products:
            product = Product(id=_cuid(), **p_data)
            db.add(product)

        db.commit()
        print(f"✓ Створено {len(products)} товарів")

    except Exception as e:
        db.rollback()
        print(f"Помилка: {e}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    seed()
