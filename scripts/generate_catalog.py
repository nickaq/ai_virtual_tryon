import os
import sys
import json
import uuid
import random
import shutil
from pathlib import Path
from PIL import Image, ImageDraw

# Add project root to sys.path
project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

from backend.database import SessionLocal, engine, Base
from backend.models.db_models import Product
from backend.models.product import (
    CatalogProduct, ProductImages, ProductAIMetadata,
    ProductCategory, ProductFit, SleeveType, NeckType, LengthType
)

STORAGE_DIR = project_root / "storage" / "products"
STORAGE_DIR.mkdir(parents=True, exist_ok=True)

# Colors for mock images
COLORS = [
    ("Red", (255, 100, 100)),
    ("Blue", (100, 100, 255)),
    ("Green", (100, 255, 100)),
    ("Black", (50, 50, 50)),
    ("White", (240, 240, 240)),
]


def create_mock_image(text_lines, size=(512, 512), bg_color=(200, 200, 200), text_color=(0, 0, 0), filename="img.png"):
    """Create a mock image with text if stable diffusion is not available."""
    img = Image.new('RGB', size, color=bg_color)
    draw = ImageDraw.Draw(img)
    y = 50
    for line in text_lines:
        draw.text((50, y), line, fill=text_color)
        y += 20
    img.save(filename)


def create_mock_mask(size=(512, 512), filename="mask.png"):
    """Create a mock mask (white square in middle)."""
    img = Image.new('L', size, color=0)
    draw = ImageDraw.Draw(img)
    draw.rectangle([100, 100, 412, 412], fill=255)
    img.save(filename)


def generate_prompt(category, color, metadata, is_tryon=False):
    """Generate SD prompts as requested."""
    if is_tryon:
        return (
            f"clothing only, no human, front view, symmetric, no shadows, "
            f"white background, flat lay style, {color} {category.value}, "
            f"{metadata.fit.value} fit, {metadata.sleeve_type.value} sleeves, "
            f"{metadata.neck_type.value} neck, {metadata.length.value} length"
        )
    return (
        f"clothing on model, fashion photography, clean background, realistic lighting, "
        f"person wearing a {color} {category.value}, {metadata.fit.value} fit, "
        f"{metadata.sleeve_type.value} sleeves, {metadata.neck_type.value} neck, "
        f"{metadata.length.value} length"
    )


def generate_catalog():
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()

    categories = list(ProductCategory)
    
    print("Generating 25 products...")
    
    generated_count = 0
    for i in range(1, 26):
        prod_id = str(uuid.uuid4())[:8]
        category = random.choice(categories)
        color_name, color_rgb = random.choice(COLORS)
        
        # Metadata
        metadata = ProductAIMetadata(
            fit=random.choice(list(ProductFit)),
            sleeve_type=random.choice(list(SleeveType)),
            neck_type=random.choice(list(NeckType)),
            length=random.choice(list(LengthType))
        )
        
        # Prompts
        catalog_prompt = generate_prompt(category, color_name, metadata, is_tryon=False)
        tryon_prompt = generate_prompt(category, color_name, metadata, is_tryon=True)
        
        # Setup directories
        prod_dir = STORAGE_DIR / prod_id
        prod_dir.mkdir(parents=True, exist_ok=True)
        
        catalog_path = prod_dir / "catalog.jpg"
        tryon_path = prod_dir / "tryon.png"
        mask_path = prod_dir / "mask.png"
        
        # Image Generation (Copying strict high-quality base photos)
        asset_path = project_root / "scripts" / "assets" / f"{category.value}.png"
        if asset_path.exists():
            shutil.copy(asset_path, tryon_path)
            shutil.copy(asset_path, catalog_path)
        else:
            create_mock_image(
                [f"Catalog: {color_name} {category.value}", catalog_prompt[:50] + "..."], 
                size=(512, 512), bg_color=color_rgb, filename=str(catalog_path)
            )
            create_mock_image(
                [f"Try-On: {color_name} {category.value}", tryon_prompt[:50] + "..."], 
                size=(512, 512), bg_color=(255, 255, 255), filename=str(tryon_path)
            )
        
        create_mock_mask(size=(512, 512), filename=str(mask_path))
        
        # Models
        images = ProductImages(
            catalog=f"/products/{prod_id}/catalog.jpg",
            tryon=f"/products/{prod_id}/tryon.png",
            mask=f"/products/{prod_id}/mask.png"
        )
        
        catalog_product = CatalogProduct(
            id=prod_id,
            name=f"{color_name} {category.value.title()} (AI Mock)",
            category=category,
            description=f"Generated {color_name} {category.value} for try-on demo.",
            color=color_name,
            images=images,
            ai_metadata=metadata
        )
        
        # Save JSON
        json_path = prod_dir / "product.json"
        with open(json_path, "w") as f:
            f.write(catalog_product.model_dump_json(indent=2))
            
        # Update SQLite DB to keep existing Shop/Orders logic working
        db_product = db.query(Product).filter(Product.id == prod_id).first()
        if not db_product:
            db_product = Product(
                id=prod_id,
                name=catalog_product.name,
                description=catalog_product.description,
                price=random.choice([19.99, 29.99, 39.99, 49.99]),
                category=catalog_product.category.value,
                sizes=json.dumps(["S", "M", "L", "XL"]),
                colors=json.dumps([color_name]),
                season="All Season",
                composition="100% Cotton",
                inStock=True,
                imageUrl=catalog_product.images.catalog
            )
            db.add(db_product)
            
        generated_count += 1
        
    db.commit()
    db.close()
    
    print(f"Successfully generated {generated_count} products with JSON schemas and fallback images.")

if __name__ == "__main__":
    generate_catalog()
