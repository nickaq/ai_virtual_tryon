/**
 * Catalog page — displays all products with category, price, and season filters.
 * Products are fetched from the FastAPI backend via /api/products.
 */
'use client';

import { useState, useEffect } from 'react';
import ProductCard from '@/frontend/components/ProductCard';
import { getCategoryName, getSeasonName } from '@/shared/formatters';
import { Product } from '@/shared/types';
import './page.css';

export default function CatalogPage() {
    const [selectedCategories, setSelectedCategories] = useState<string[]>([]);
    const [priceRange, setPriceRange] = useState<[number, number]>([0, 500]);
    const [selectedSeasons, setSelectedSeasons] = useState<string[]>([]);
    const [searchQuery, setSearchQuery] = useState('');
    const [products, setProducts] = useState<Product[]>([]);
    const [loading, setLoading] = useState(true);

    useEffect(() => {
        async function fetchProducts() {
            setLoading(true);
            try {
                const params = new URLSearchParams();
                params.set('limit', '100');

                if (selectedCategories.length === 1) {
                    params.set('category', selectedCategories[0]);
                }
                if (searchQuery) {
                    params.set('search', searchQuery);
                }
                if (priceRange[0] > 0) {
                    params.set('minPrice', String(priceRange[0]));
                }
                if (priceRange[1] < 500) {
                    params.set('maxPrice', String(priceRange[1]));
                }
                if (selectedSeasons.length === 1) {
                    params.set('season', selectedSeasons[0]);
                }

                const res = await fetch(`/api/products?${params.toString()}`);
                if (!res.ok) throw new Error('Failed to fetch products');
                const data = await res.json();

                // Map API response to match frontend Product type
                const mapped: Product[] = data.products.map((p: Record<string, unknown>) => ({
                    ...p,
                    images: p.imageUrl ? [p.imageUrl as string] : ['/placeholder.jpg'],
                }));

                setProducts(mapped);
            } catch (err) {
                console.error('Error fetching products:', err);
            } finally {
                setLoading(false);
            }
        }

        fetchProducts();
    }, [selectedCategories, priceRange, selectedSeasons, searchQuery]);

    // Client-side filtering for multi-select category/season (API only supports single)
    const filteredProducts = products.filter(product => {
        if (selectedCategories.length > 1 && !selectedCategories.includes(product.category)) {
            return false;
        }
        if (selectedSeasons.length > 1 && !selectedSeasons.includes(product.season)) {
            return false;
        }
        return true;
    });

    const toggleCategory = (category: string) => {
        setSelectedCategories(prev =>
            prev.includes(category)
                ? prev.filter(c => c !== category)
                : [...prev, category]
        );
    };

    const toggleSeason = (season: string) => {
        setSelectedSeasons(prev =>
            prev.includes(season)
                ? prev.filter(s => s !== season)
                : [...prev, season]
        );
    };

    return (
        <div className="catalog-page">
            <div className="container">
                <div className="catalog-header">
                    <h1>Каталог</h1>
                    <div className="search-bar">
                        <input
                            type="text"
                            placeholder="Пошук товарів..."
                            value={searchQuery}
                            onChange={(e) => setSearchQuery(e.target.value)}
                        />
                    </div>
                </div>

                <div className="catalog-layout">
                    <aside className="filters-sidebar">
                        <div className="filter-section">
                            <h3>Категорії</h3>
                            <div className="filter-options">
                                {['jackets', 'pants', 'shirts', 'shoes', 'accessories'].map(cat => (
                                    <label key={cat} className="filter-checkbox">
                                        <input
                                            type="checkbox"
                                            checked={selectedCategories.includes(cat)}
                                            onChange={() => toggleCategory(cat)}
                                        />
                                        <span>{getCategoryName(cat)}</span>
                                    </label>
                                ))}
                            </div>
                        </div>

                        <div className="filter-section">
                            <h3>Ціна</h3>
                            <div className="price-range">
                                <input
                                    type="range"
                                    min="0"
                                    max="500"
                                    value={priceRange[1]}
                                    onChange={(e) => setPriceRange([0, parseInt(e.target.value)])}
                                />
                                <div className="price-labels">
                                    <span>€0</span>
                                    <span>€{priceRange[1]}</span>
                                </div>
                            </div>
                        </div>

                        <div className="filter-section">
                            <h3>Сезон</h3>
                            <div className="filter-options">
                                {['spring', 'summer', 'fall', 'winter', 'all-season'].map(season => (
                                    <label key={season} className="filter-checkbox">
                                        <input
                                            type="checkbox"
                                            checked={selectedSeasons.includes(season)}
                                            onChange={() => toggleSeason(season)}
                                        />
                                        <span>{getSeasonName(season)}</span>
                                    </label>
                                ))}
                            </div>
                        </div>

                        <button
                            className="btn btn-secondary"
                            onClick={() => {
                                setSelectedCategories([]);
                                setSelectedSeasons([]);
                                setPriceRange([0, 500]);
                                setSearchQuery('');
                            }}
                        >
                            Скинути фільтри
                        </button>
                    </aside>

                    <div className="catalog-content">
                        <div className="catalog-info">
                            <p className="results-count">
                                Знайдено товарів: <strong>{filteredProducts.length}</strong>
                            </p>
                        </div>

                        {loading ? (
                            <div className="no-results">
                                <p>Завантаження...</p>
                            </div>
                        ) : (
                            <div className="products-grid">
                                {filteredProducts.map(product => (
                                    <ProductCard key={product.id} product={product} />
                                ))}
                            </div>
                        )}

                        {!loading && filteredProducts.length === 0 && (
                            <div className="no-results">
                                <p>Товари не знайдено. Спробуйте змінити фільтри.</p>
                            </div>
                        )}
                    </div>
                </div>
            </div>
        </div>
    );
}
