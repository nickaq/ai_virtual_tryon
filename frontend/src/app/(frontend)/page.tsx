/**
 * Home page — hero section, feature highlights, featured products, and CTA.
 * Featured products are fetched from the backend API at runtime.
 */
'use client';

import { useState, useEffect } from 'react';
import Link from 'next/link';
import ProductCard from '@/frontend/components/ProductCard';
import { Product } from '@/shared/types';
import './page.css';

export default function Home() {
    const [featuredProducts, setFeaturedProducts] = useState<Product[]>([]);

    useEffect(() => {
        async function loadFeatured() {
            try {
                const res = await fetch('/api/products?limit=6');
                if (!res.ok) return;
                const data = await res.json();
                const mapped: Product[] = data.products.map((p: Record<string, unknown>) => ({
                    ...p,
                    images: p.imageUrl ? [p.imageUrl as string] : ['/placeholder.jpg'],
                }));
                setFeaturedProducts(mapped);
            } catch (err) {
                console.error('Failed to load featured products:', err);
            }
        }
        loadFeatured();
    }, []);

    return (
        <div className="home">
            {/* Hero Section */}
            <section className="hero">
                <div className="container hero-content">
                    <div className="hero-text reveal">
                        <h1 className="hero-title">
                            Стиль <br />
                            <span className="gradient-text">майбутнього</span>
                        </h1>
                        <p className="hero-description">
                            Досліджуйте моду за допомогою штучного інтелекту. 
                            Віртуальне примірювання, персональні рекомендації та унікальні колекції.
                        </p>
                        <div className="hero-actions">
                            <Link href="/catalog" className="btn btn-primary btn-lg">
                                Перейти до каталогу
                            </Link>
                            <Link href="/tryon" className="btn btn-secondary btn-lg">
                                Спробувати AI
                            </Link>
                        </div>
                    </div>
                    <div className="hero-visual reveal">
                        <div className="hero-card">
                            <div className="hero-image">
                                <span>✨</span>
                            </div>
                        </div>
                    </div>
                </div>
            </section>

            {/* Features Section */}
            <section className="features">
                <div className="container">
                    <div className="features-grid">
                        <div className="feature-card reveal">
                            <span className="feature-icon">🤖</span>
                            <h3>AI Технології</h3>
                            <p>Ми використовуємо передові нейромережі для ідеального поєднання стилю та комфорту.</p>
                        </div>
                        <div className="feature-card reveal">
                            <span className="feature-icon">👔</span>
                            <h3>Віртуальна примірка</h3>
                            <p>Побачте, як одяг сидить на вас, не виходячи з дому, завдяки технології AI Vision.</p>
                        </div>
                        <div className="feature-card reveal">
                            <span className="feature-icon">⚡</span>
                            <h3>Ексклюзивність</h3>
                            <p>Колекції, що створюються за участю AI стилістів спеціально для поціновувачів інновацій.</p>
                        </div>
                    </div>
                </div>
            </section>

            {/* Featured Products */}
            <section className="featured-products">
                <div className="container">
                    <div className="section-header reveal">
                        <h2>Нова Колекція</h2>
                        <Link href="/catalog" className="view-all-link">
                            Дивитись все &mdash;
                        </Link>
                    </div>
                    <div className="products-grid reveal">
                        {featuredProducts.map(product => (
                            <ProductCard key={product.id} product={product} />
                        ))}
                    </div>
                </div>
            </section>

            {/* CTA Section */}
            <section className="cta-section reveal">
                <div className="container">
                    <div className="cta-card">
                        <h2>Готові до змін?</h2>
                        <p>
                            Приєднуйтесь до тисяч користувачів, які вже змінили свій підхід до шопінгу разом зі StyleAI.
                        </p>
                        <Link href="/tryon" className="btn btn-primary btn-lg">
                            Почати примірювання
                        </Link>
                    </div>
                </div>
            </section>
        </div>
    );
}
