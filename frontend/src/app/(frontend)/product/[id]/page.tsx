/**
 * Product detail page — displays product info, size/color selectors,
 * add-to-cart action, inline virtual try-on uploader, and similar products.
 * Data is fetched from the FastAPI backend via /api/products/:id.
 */
'use client';

import { useState, useEffect, useRef } from 'react';
import { useParams } from 'next/navigation';
import Link from 'next/link';
import { useCart } from '@/frontend/lib/cartContext';
import { getCategoryName, getSeasonName } from '@/shared/formatters';
import { Product } from '@/shared/types';
import ProductCard from '@/frontend/components/ProductCard';
import './page.css';

export default function ProductPage() {
    const params = useParams();
    const productId = params.id as string;
    const { addToCart } = useCart();

    const [product, setProduct] = useState<Product | null>(null);
    const [similarProducts, setSimilarProducts] = useState<Product[]>([]);
    const [loading, setLoading] = useState(true);

    const [selectedSize, setSelectedSize] = useState('');
    const [selectedColor, setSelectedColor] = useState('');
    const [showTryOn, setShowTryOn] = useState(false);
    const [uploadedPhoto, setUploadedPhoto] = useState<string | null>(null);
    const tryOnRef = useRef<HTMLDivElement>(null);
    const [tryOnStatus, setTryOnStatus] = useState<'idle' | 'uploading' | 'processing' | 'done' | 'error'>('idle');
    const [tryOnResultUrl, setTryOnResultUrl] = useState<string | null>(null);
    const [tryOnError, setTryOnError] = useState<string | null>(null);
    const [notification, setNotification] = useState<{ type: 'success' | 'error'; message: string } | null>(null);

    // Fetch product from API
    useEffect(() => {
        async function fetchProduct() {
            setLoading(true);
            try {
                const res = await fetch(`/api/products/${productId}`);
                if (!res.ok) {
                    setProduct(null);
                    return;
                }
                const data = await res.json();
                const mapped: Product = {
                    ...data,
                    images: data.images || (data.imageUrl ? [data.imageUrl] : ['/placeholder.jpg']),
                };
                setProduct(mapped);

                // Fetch similar products
                const simRes = await fetch(`/api/products?category=${data.category}&limit=4`);
                if (simRes.ok) {
                    const simData = await simRes.json();
                    const simMapped: Product[] = simData.products
                        .filter((p: Record<string, unknown>) => p.id !== productId)
                        .slice(0, 3)
                        .map((p: Record<string, unknown>) => ({
                            ...p,
                            images: p.images || (p.imageUrl ? [p.imageUrl as string] : ['/placeholder.jpg']),
                        }));
                    setSimilarProducts(simMapped);
                }
            } catch (err) {
                console.error('Error fetching product:', err);
                setProduct(null);
            } finally {
                setLoading(false);
            }
        }

        fetchProduct();
    }, [productId]);

    if (loading) {
        return (
            <div className="container" style={{ padding: '4rem 0', textAlign: 'center' }}>
                <p>Завантаження...</p>
            </div>
        );
    }

    if (!product) {
        return (
            <div className="container" style={{ padding: '4rem 0', textAlign: 'center' }}>
                <h1>Товар не знайдено</h1>
                <Link href="/catalog" className="btn btn-primary">Повернутися до каталогу</Link>
            </div>
        );
    }

    const handleAddToCart = () => {
        if (!selectedSize || !selectedColor) {
            setNotification({ type: 'error', message: 'Будь ласка, оберіть розмір та колір' });
            setTimeout(() => setNotification(null), 3000);
            return;
        }
        addToCart(product, selectedSize, selectedColor);
        setNotification({ type: 'success', message: 'Товар додано до кошика!' });
        setTimeout(() => setNotification(null), 3000);
    };

    const handlePhotoUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
        const file = e.target.files?.[0];
        if (!file) return;

        // Show preview
        const reader = new FileReader();
        reader.onload = (ev) => {
            setUploadedPhoto(ev.target?.result as string);
        };
        reader.readAsDataURL(file);

        // Submit to API
        setTryOnStatus('uploading');
        setTryOnError(null);
        setTryOnResultUrl(null);

        try {
            const formData = new FormData();
            formData.append('photo', file);
            formData.append('productId', product.id);

            const response = await fetch('/api/try-on/upload', {
                method: 'POST',
                body: formData,
            });

            if (!response.ok) {
                const errorData = await response.json().catch(() => ({}));
                throw new Error(errorData.error || errorData.detail || `Upload failed (${response.status})`);
            }

            const data = await response.json();
            setTryOnStatus('processing');

            // Poll for result
            const jobId = data.jobId;
            let attempts = 0;
            const maxAttempts = 60;

            const pollInterval = setInterval(async () => {
                attempts++;
                try {
                    const statusRes = await fetch(`/api/try-on/${jobId}`);
                    const statusData = await statusRes.json();

                    if (statusData.status === 'DONE') {
                        clearInterval(pollInterval);
                        setTryOnStatus('done');
                        setTryOnResultUrl(statusData.resultPhotoUrl || statusData.resultPath);
                    } else if (statusData.status === 'FAILED') {
                        clearInterval(pollInterval);
                        setTryOnStatus('error');
                        setTryOnError(statusData.errorMessage || 'Обробка не вдалася');
                    } else if (attempts >= maxAttempts) {
                        clearInterval(pollInterval);
                        setTryOnStatus('error');
                        setTryOnError('Час очікування вичерпано');
                    }
                } catch {
                    clearInterval(pollInterval);
                    setTryOnStatus('error');
                    setTryOnError('Помилка перевірки статусу');
                }
            }, 2000);
        } catch (err) {
            setTryOnStatus('error');
            setTryOnError(err instanceof Error ? err.message : 'Помилка завантаження');
        }
    };

    const resetTryOn = () => {
        setUploadedPhoto(null);
        setTryOnStatus('idle');
        setTryOnResultUrl(null);
        setTryOnError(null);
    };

    return (
        <div className="product-page">
            <div className="container">
                <div className="breadcrumbs">
                    <Link href="/">Головна</Link>
                    <span>/</span>
                    <Link href="/catalog">Каталог</Link>
                    <span>/</span>
                    <span>{product.name}</span>
                </div>

                <div className="product-layout">
                    <div className="product-gallery">
                        <div className="main-image">
                            {(() => {
                                const bestImage = product.images && !Array.isArray(product.images) && product.images.catalog 
                                    ? product.images.catalog 
                                    : product.imageUrl;
                                
                                if (bestImage) {
                                    return <img src={bestImage} alt={product.name} className="product-img" style={{width: '100%', height: '100%', objectFit: 'cover', objectPosition: 'center'}} />;
                                }
                                return (
                                    <div className="img-placeholder">
                                        <span>📸</span>
                                    </div>
                                );
                            })()}
                        </div>
                    </div>

                    <div className="product-details">
                        <div className="product-header">
                            <h1>{product.name}</h1>
                            <div className="product-price-large">€{product.price}</div>
                        </div>

                        <p className="product-description-full">{product.description}</p>

                        <div className="product-options">
                            <div className="option-group">
                                <label>Розмір</label>
                                <div className="size-options">
                                    {product.sizes.map(size => (
                                        <button
                                            key={size}
                                            className={`size-btn ${selectedSize === size ? 'active' : ''}`}
                                            onClick={() => setSelectedSize(size)}
                                        >
                                            {size}
                                        </button>
                                    ))}
                                </div>
                            </div>

                            <div className="option-group">
                                <label>Колір</label>
                                <div className="color-options">
                                    {product.colors.map(color => (
                                        <button
                                            key={color}
                                            className={`color-btn ${selectedColor === color ? 'active' : ''}`}
                                            onClick={() => setSelectedColor(color)}
                                            title={color}
                                        >
                                            {color}
                                        </button>
                                    ))}
                                </div>
                            </div>
                        </div>

                        {notification && (
                            <div className={`notification ${notification.type}`}>
                                {notification.message}
                            </div>
                        )}

                        <div className="product-actions">
                            <button className="btn btn-primary btn-lg" onClick={handleAddToCart}>
                                Додати до кошика
                            </button>
                            <button className="btn btn-secondary btn-lg" onClick={() => setShowTryOn(!showTryOn)}>
                                👔 Примірити
                            </button>
                        </div>

                        {showTryOn && (
                            <div className="try-on-section" ref={tryOnRef}>
                                <h3>Віртуальне примірювання</h3>
                                <p>Завантажте своє фото, щоб побачити, як на вас виглядатиме ця річ</p>

                                {!uploadedPhoto ? (
                                    <div className="photo-upload">
                                        <input
                                            type="file"
                                            id="photo-upload"
                                            accept="image/*"
                                            onChange={handlePhotoUpload}
                                            style={{ display: 'none' }}
                                        />
                                        <label htmlFor="photo-upload" className="upload-area">
                                            <div className="upload-icon">📸</div>
                                            <p>Натисніть для завантаження фото</p>
                                            <span className="upload-hint">JPG, PNG (макс. 10MB)</span>
                                        </label>
                                    </div>
                                ) : (
                                    <div className="try-on-result">
                                        <div className="result-images">
                                            <div className="result-image">
                                                <p>Ваше фото</p>
                                                <div className="img-placeholder">
                                                    {/* eslint-disable-next-line @next/next/no-img-element */}
                                                    <img src={uploadedPhoto} alt="Ваше фото" style={{ width: '100%', height: '100%', objectFit: 'contain' }} />
                                                </div>
                                            </div>
                                            <div className="result-arrow">→</div>
                                            <div className="result-image">
                                                {tryOnStatus === 'done' && tryOnResultUrl ? (
                                                    <>
                                                        <p>Результат</p>
                                                        <div className="img-placeholder">
                                                            {/* eslint-disable-next-line @next/next/no-img-element */}
                                                            <img src={tryOnResultUrl} alt="Результат" style={{ width: '100%', height: '100%', objectFit: 'contain' }} />
                                                        </div>
                                                    </>
                                                ) : tryOnStatus === 'error' ? (
                                                    <>
                                                        <p>Помилка</p>
                                                        <div className="img-placeholder">
                                                            <span>❌</span>
                                                            <p style={{ fontSize: '0.85rem', color: '#e74c3c' }}>{tryOnError}</p>
                                                        </div>
                                                    </>
                                                ) : (
                                                    <>
                                                        <p>{tryOnStatus === 'uploading' ? 'Завантаження...' : 'Обробляється...'}</p>
                                                        <div className="img-placeholder">
                                                            <div className="spinner"></div>
                                                        </div>
                                                    </>
                                                )}
                                            </div>
                                        </div>
                                        <button className="btn btn-secondary" onClick={resetTryOn}>
                                            Завантажити інше фото
                                        </button>
                                    </div>
                                )}
                            </div>
                        )}

                        <div className="product-info-section">
                            <h3>Склад</h3>
                            <p>{product.composition}</p>

                            <h3>Опис</h3>
                            <ul>
                                <li>Категорія: {getCategoryName(product.category)}</li>
                                <li>Сезон: {getSeasonName(product.season)}</li>
                                <li>Наявність: {product.inStock ? 'В наявності' : 'Немає в наявності'}</li>
                            </ul>
                        </div>
                    </div>
                </div>

                {similarProducts.length > 0 && (
                    <div className="similar-products">
                        <h2>Схожі товари</h2>
                        <div className="products-grid">
                            {similarProducts.map(p => (
                                <ProductCard key={p.id} product={p} />
                            ))}
                        </div>
                    </div>
                )}
            </div>
        </div>
    );
}
