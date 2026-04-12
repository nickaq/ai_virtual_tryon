/**
 * Shopping cart page.
 * Displays cart items with quantity controls, an order summary sidebar,
 * and navigation to the checkout flow.
 */
'use client';

import { useRouter } from 'next/navigation';
import { useCart } from '@/frontend/lib/cartContext';
import Link from 'next/link';
import './page.css';

export default function CartPage() {
    const { items, removeFromCart, updateQuantity, clearCart, getTotal, getItemCount } = useCart();
    const router = useRouter();

    // Empty cart state
    if (items.length === 0) {
        return (
            <div className="cart-page">
                <div className="container">
                    <div className="empty-cart reveal">
                        <div className="empty-cart-icon">🛒</div>
                        <h2>Ваш кошик порожній</h2>
                        <p>Додайте товари з каталогу, щоб почати створення свого унікального стилю.</p>
                        <Link href="/catalog" className="btn btn-primary btn-lg">
                            Перейти до каталогу
                        </Link>
                    </div>
                </div>
            </div>
        );
    }

    return (
        <div className="cart-page">
            <div className="container">
                {/* Cart header */}
                <div className="cart-header reveal">
                    <h1>Ваш <span className="gradient-text">Кошик</span></h1>
                    <button onClick={clearCart} className="btn btn-secondary">
                        Очистити
                    </button>
                </div>

                <div className="cart-layout">
                    {/* Cart item list */}
                    <div className="cart-items">
                        {items.map((item, index) => (
                            <div 
                                key={`${item.product.id}-${item.selectedSize}-${item.selectedColor}`} 
                                className="cart-item reveal" 
                                style={{ animationDelay: `${index * 0.1}s` }}
                            >
                                {/* Product thumbnail */}
                                <div className="item-image">
                                    <img 
                                        src={item.product.imageUrl || '/placeholder.jpg'} 
                                        alt={item.product.name} 
                                    />
                                </div>

                                {/* Product details */}
                                <div className="item-details">
                                    <Link href={`/product/${item.product.id}`} className="item-name">
                                        {item.product.name}
                                    </Link>
                                    <div className="item-options">
                                        <span>Розмір: {item.selectedSize}</span>
                                        <span>Колір: {item.selectedColor}</span>
                                    </div>
                                    <div className="item-price">€{item.product.price}</div>
                                </div>

                                {/* Quantity controls and remove */}
                                <div className="item-actions">
                                    <div className="quantity-control">
                                        <button
                                            onClick={() => updateQuantity(item.product.id, item.selectedSize, item.selectedColor, Math.max(1, item.quantity - 1))}
                                            disabled={item.quantity <= 1}
                                        >−</button>
                                        <span>{item.quantity}</span>
                                        <button
                                            onClick={() => updateQuantity(item.product.id, item.selectedSize, item.selectedColor, item.quantity + 1)}
                                        >+</button>
                                    </div>
                                    <div className="item-total">€{(item.product.price * item.quantity).toFixed(2)}</div>
                                    <button
                                        onClick={() => removeFromCart(item.product.id, item.selectedSize, item.selectedColor)}
                                        className="btn-icon remove-btn"
                                        title="Видалити"
                                    >
                                        <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M3 6h18m-2 0v14c0 1-1 2-2 2H7c-1 0-2-1-2-2V6m3 0V4c0-1 1-2 2-2h4c1 0 2 1 2 2v2M10 11v6m4-6v6"/></svg>
                                    </button>
                                </div>
                            </div>
                        ))}
                    </div>

                    {/* Order summary sidebar */}
                    <aside className="cart-summary reveal">
                        <h2>Підсумок</h2>
                        <div className="summary-row">
                            <span>Товари ({getItemCount()})</span>
                            <span>€{getTotal().toFixed(2)}</span>
                        </div>
                        <div className="summary-row">
                            <span>Доставка</span>
                            <span style={{ color: 'var(--primary)', fontWeight: 800 }}>Безкоштовно</span>
                        </div>
                        
                        <div className="summary-total">
                            <span>Разом</span>
                            <span>€{getTotal().toFixed(2)}</span>
                        </div>
                        
                        <button onClick={() => router.push('/checkout')} className="btn btn-primary btn-lg checkout-btn">
                            До оплати
                        </button>
                        <Link href="/catalog" className="continue-shopping">← Продовжити покупки</Link>
                    </aside>
                </div>
            </div>
        </div>
    );
}
