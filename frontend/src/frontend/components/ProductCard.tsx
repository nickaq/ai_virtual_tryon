/**
 * Product card component used in catalog grids and recommendation lists.
 * Displays product thumbnail, name, price, colors, and a "Try On" shortcut.
 */
'use client';

import Link from 'next/link';
import { Product } from '@/shared/types';
import { getCategoryName } from '@/shared/formatters';
import './ProductCard.css';

interface ProductCardProps {
    product: Product;
}

export default function ProductCard({ product }: ProductCardProps) {
    return (
        <Link href={`/product/${product.id}`} className="product-card">
            {/* Product image */}
            <div className="product-image">
                {(() => {
                    const bestImage = product.images && !Array.isArray(product.images) && product.images.catalog 
                        ? product.images.catalog 
                        : product.imageUrl;
                    
                    if (bestImage) {
                        return <img src={bestImage} alt={product.name} className="product-img" />;
                    }
                    return (
                        <div className="img-placeholder">
                            <span>📸</span>
                        </div>
                    );
                })()}
                {!product.inStock && <div className="out-of-stock-badge">Немає в наявності</div>}
            </div>

            <div className="product-info">
                {/* Category badge */}
                <div className="product-category">{getCategoryName(product.category)}</div>
                <h3 className="product-name">{product.name}</h3>
                <p className="product-description">{product.description.substring(0, 80)}...</p>

                {/* Price and color dots */}
                <div className="product-footer">
                    <div className="product-price">€{product.price}</div>
                    <div className="product-colors">
                        {product.colors.slice(0, 3).map((color, index) => (
                            <div key={index} className="color-dot" title={color} />
                        ))}
                        {product.colors.length > 3 && (
                            <span className="color-more">+{product.colors.length - 3}</span>
                        )}
                    </div>
                </div>

                {/* Quick "Try On" link — navigates to the product page's try-on section */}
                <Link
                    href={`/product/${product.id}#try-on`}
                    className="try-on-button"
                    onClick={(e) => e.stopPropagation()}
                >
                    <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943 9.542 7-1.274 4.057-5.064 7-9.542 7-4.477 0-8.268-2.943-9.542-7z" />
                    </svg>
                    Try On
                </Link>
            </div>
        </Link>
    );
}
