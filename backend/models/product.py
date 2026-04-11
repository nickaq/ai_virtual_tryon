from pydantic import BaseModel
from typing import Optional
from enum import Enum


class ProductCategory(str, Enum):
    t_shirt = "t-shirt"
    shirt = "shirt"
    jacket = "jacket"
    dress = "dress"


class ProductFit(str, Enum):
    regular = "regular"
    slim = "slim"
    oversized = "oversized"


class SleeveType(str, Enum):
    short = "short"
    long = "long"
    none = "none"


class NeckType(str, Enum):
    round = "round"
    v_neck = "v-neck"
    shirt = "shirt"
    none = "none"


class LengthType(str, Enum):
    cropped = "cropped"
    normal = "normal"
    long = "long"


class ProductImages(BaseModel):
    catalog: str
    tryon: str
    mask: Optional[str] = None


class ProductAIMetadata(BaseModel):
    fit: ProductFit
    sleeve_type: SleeveType
    neck_type: NeckType
    length: LengthType


class CatalogProduct(BaseModel):
    """
    Pydantic model representing the JSON structure of a product stored on disk.
    Compatible with the AI Try-on pipeline.
    """
    id: str
    name: str
    category: ProductCategory
    description: str
    color: str
    images: ProductImages
    ai_metadata: ProductAIMetadata
