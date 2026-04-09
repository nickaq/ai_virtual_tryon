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
                    <div className="empty-cart">
                        <div className="empty-cart-icon">🛒</div>
                        <h2>Ваш кошик порожній</h2>
                        <p>Додайте товари з каталогу, щоб продовжити покупки</p>
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
                {/* Cart header with clear button */}
                <div className="cart-header">
                    <h1>Кошик</h1>
                    <button onClick={clearCart} className="btn btn-secondary">
                        Очистити кошик
                    </button>
                </div>

                <div className="cart-layout">
                    {/* Cart item list */}
                    <div className="cart-items">
                        {items.map((item) => (
                            <div key={`${item.product.id}-${item.selectedSize}-${item.selectedColor}`} className="cart-item">
                                {/* Product thumbnail */}
                                <div className="cart-item-image">
                                    <div className="img-placeholder"><span>📸</span></div>
                                </div>

                                {/* Product details */}
                                <div className="cart-item-info">
                                    <Link href={`/product/${item.product.id}`}><h3>{item.product.name}</h3></Link>
                                    <div className="cart-item-details">
                                        <span>Розмір: <strong>{item.selectedSize}</strong></span>
                                        <span>Колір: <strong>{item.selectedColor}</strong></span>
                                    </div>
                                    <div className="cart-item-price">€{item.product.price}</div>
                                </div>

                                {/* Quantity controls and remove */}
                                <div className="cart-item-actions">
                                    <div className="quantity-controls">
                                        <button
                                            onClick={() => updateQuantity(item.product.id, item.selectedSize, item.selectedColor, Math.max(1, item.quantity - 1))}
                                            className="quantity-btn"
                                        >−</button>
                                        <span className="quantity">{item.quantity}</span>
                                        <button
                                            onClick={() => updateQuantity(item.product.id, item.selectedSize, item.selectedColor, item.quantity + 1)}
                                            className="quantity-btn"
                                        >+</button>
                                    </div>
                                    <div className="cart-item-total">€{(item.product.price * item.quantity).toFixed(2)}</div>
                                    <button
                                        onClick={() => removeFromCart(item.product.id, item.selectedSize, item.selectedColor)}
                                        className="remove-btn"
                                    >🗑️</button>
                                </div>
                            </div>
                        ))}
                    </div>

                    {/* Order summary sidebar */}
                    <aside className="cart-summary">
                        <div className="summary-card">
                            <h3>Підсумок замовлення</h3>
                            <div className="summary-row">
                                <span>Товарів ({getItemCount()})</span>
                                <span>€{getTotal().toFixed(2)}</span>
                            </div>
                            <div className="summary-row">
                                <span>Доставка</span>
                                <span className="free-shipping">Безкоштовно</span>
                            </div>
                            <div className="summary-divider"></div>
                            <div className="summary-row summary-total">
                                <span>Разом</span>
                                <span>€{getTotal().toFixed(2)}</span>
                            </div>
                            <button onClick={() => router.push('/checkout')} className="btn btn-primary btn-lg btn-block">
                                Оформити замовлення
                            </button>
                            <Link href="/catalog" className="continue-shopping">← Продовжити покупки</Link>
                        </div>
                    </aside>
                </div>
            </div>
        </div>
    );
}
