/**
 * Shared type definitions for the StyleAI application.
 * Used by both frontend pages and API response handling.
 */

/** Product categories available in the catalog. */
export type ProductCategory = 'jackets' | 'pants' | 'shirts' | 'shoes' | 'accessories';

/** Seasonal availability for products. */
export type ProductSeason = 'spring' | 'summer' | 'fall' | 'winter' | 'all-season';

/** Product listing from the catalog API. */
export interface Product {
    id: string;
    name: string;
    category: ProductCategory;
    price: number;
    description: string;
    composition: string;
    sizes: string[];
    colors: string[];
    season: ProductSeason;
    inStock: boolean;
    imageUrl?: string;
    images?: { catalog: string; tryon: string; mask?: string; } | string[];
}

/** A single item in the shopping cart. */
export interface CartItem {
    product: Product;
    quantity: number;
    selectedSize: string;
    selectedColor: string;
}

/** Order record returned by the orders API. */
export interface Order {
    id: string;
    date: string;
    items: CartItem[];
    total: number;
    status: 'pending' | 'processing' | 'shipped' | 'delivered';
    deliveryAddress: string;
}

/** Result of a virtual try-on job. */
export interface TryOnResult {
    id: string;
    productId: string;
    originalPhoto: string;
    resultPhoto: string;
    timestamp: string;
    status: 'pending' | 'processing' | 'completed' | 'failed';
}

/** Chat message in the AI Stylist interface. */
export interface ChatMessage {
    id: string;
    role: 'user' | 'assistant';
    content: string;
    timestamp: string;
    products?: Product[];
}

/** Filter state for catalog browsing. */
export interface FilterOptions {
    categories: string[];
    priceRange: [number, number];
    sizes: string[];
    colors: string[];
    seasons: string[];
}
