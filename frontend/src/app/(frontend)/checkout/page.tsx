/**
 * Checkout page — multi-step form for completing an order.
 * Steps: 1) Contact info  2) Shipping address  3) Confirmation.
 * Submits the order to the FastAPI /api/orders endpoint.
 */
'use client';

import { useState, useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { useCart } from '@/frontend/lib/cartContext';
import './page.css';

export default function CheckoutPage() {
    const router = useRouter();
    const { items, getTotal, clearCart } = useCart();
    const [step, setStep] = useState(1);
    const [isSubmitting, setIsSubmitting] = useState(false);
    const [orderError, setOrderError] = useState<string | null>(null);

    // Form fields
    const [formData, setFormData] = useState({
        name: '',
        email: '',
        phone: '',
        address: '',
        city: '',
        postalCode: '',
        country: '',
    });

    // Redirect to cart if there are no items
    useEffect(() => {
        if (items.length === 0) router.push('/cart');
    }, [items.length, router]);

    if (items.length === 0) return null;

    /** Advance to the next step, or submit the order on the final step. */
    const handleSubmit = async (e: React.FormEvent) => {
        e.preventDefault();
        if (step < 3) {
            setStep(step + 1);
            window.scrollTo({ top: 0, behavior: 'smooth' });
            return;
        }

        // Final step — submit order via API
        setIsSubmitting(true);
        setOrderError(null);

        try {
            const response = await fetch('/api/orders', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    items: items.map(item => ({
                        productId: item.product.id,
                        quantity: item.quantity,
                        selectedSize: item.selectedSize,
                        selectedColor: item.selectedColor,
                    })),
                    contactName: formData.name,
                    email: formData.email,
                    phone: formData.phone,
                    address: formData.address,
                    city: formData.city,
                    postalCode: formData.postalCode,
                    country: formData.country,
                }),
            });

            if (!response.ok) {
                const errorData = await response.json().catch(() => ({}));
                throw new Error(errorData.error || `Order failed (${response.status})`);
            }

            clearCart();
            router.push('/');
        } catch (err) {
            setOrderError(err instanceof Error ? err.message : 'Failed to place order');
        } finally {
            setIsSubmitting(false);
        }
    };

    /** Generic handler for text input changes. */
    const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
        setFormData({ ...formData, [e.target.name]: e.target.value });
    };

    return (
        <div className="checkout-page">
            <div className="container">
                <h1 className="reveal">Оформлення <span className="gradient-text">Замовлення</span></h1>

                {/* Step indicator */}
                <div className="checkout-steps reveal">
                    <div className={`step ${step >= 1 ? 'active' : ''}`}>
                        <div className="step-number">01</div>
                        <span>Контакт</span>
                    </div>
                    <div className={`step ${step >= 2 ? 'active' : ''}`}>
                        <div className="step-number">02</div>
                        <span>Доставка</span>
                    </div>
                    <div className={`step ${step >= 3 ? 'active' : ''}`}>
                        <div className="step-number">03</div>
                        <span>Оплата</span>
                    </div>
                </div>

                {/* Error banner */}
                {orderError && (
                    <div className="checkout-error reveal">
                        <p>{orderError}</p>
                    </div>
                )}

                <div className="checkout-layout">
                    <form className="checkout-form reveal" onSubmit={handleSubmit}>
                        {/* Step 1 — Contact info */}
                        {step === 1 && (
                            <div className="form-section">
                                <h2>Контактні дані</h2>
                                <div className="form-grid">
                                    <input type="text" name="name" placeholder="Повне ім'я *" value={formData.name} onChange={handleChange} required />
                                    <input type="email" name="email" placeholder="Email *" value={formData.email} onChange={handleChange} required />
                                    <input type="tel" name="phone" placeholder="Телефон *" value={formData.phone} onChange={handleChange} required style={{ gridColumn: '1 / -1' }} />
                                </div>
                                <button type="submit" className="btn btn-primary btn-lg">Продовжити</button>
                            </div>
                        )}

                        {/* Step 2 — Shipping address */}
                        {step === 2 && (
                            <div className="form-section">
                                <h2>Адреса доставки</h2>
                                <div className="form-grid">
                                    <input type="text" name="address" placeholder="Адреса *" value={formData.address} onChange={handleChange} required style={{ gridColumn: '1 / -1' }} />
                                    <input type="text" name="city" placeholder="Місто *" value={formData.city} onChange={handleChange} required />
                                    <input type="text" name="postalCode" placeholder="Поштовий індекс *" value={formData.postalCode} onChange={handleChange} required />
                                    <input type="text" name="country" placeholder="Країна *" value={formData.country} onChange={handleChange} required style={{ gridColumn: '1 / -1' }} />
                                </div>
                                <div className="form-actions">
                                    <button type="button" className="btn btn-secondary" onClick={() => setStep(1)}>Назад</button>
                                    <button type="submit" className="btn btn-primary btn-lg">Продовжити</button>
                                </div>
                            </div>
                        )}

                        {/* Step 3 — Confirmation */}
                        {step === 3 && (
                            <div className="form-section">
                                <h2>Підтвердження</h2>
                                <div className="confirmation-details">
                                    <div className="detail-group">
                                        <h3>Отримувач</h3>
                                        <p>{formData.name}</p>
                                        <p>{formData.email} • {formData.phone}</p>
                                    </div>
                                    <div className="detail-group">
                                        <h3>Доставка</h3>
                                        <p>{formData.address}</p>
                                        <p>{formData.city}, {formData.postalCode}, {formData.country}</p>
                                    </div>
                                    <div className="payment-stub">
                                        <h3>Метод оплати</h3>
                                        <p className="payment-note">💳 Оплата картою при отриманні</p>
                                    </div>
                                </div>
                                <div className="form-actions">
                                    <button type="button" className="btn btn-secondary" onClick={() => setStep(2)}>Назад</button>
                                    <button type="submit" className="btn btn-primary btn-lg" disabled={isSubmitting}>
                                        {isSubmitting ? 'Обробка...' : 'Підтвердити замовлення'}
                                    </button>
                                </div>
                            </div>
                        )}
                    </form>

                    {/* Order summary sidebar */}
                    <aside className="order-summary reveal">
                        <h2>Ваше замовлення</h2>
                        <div className="summary-items">
                            {items.map((item) => (
                                <div key={`${item.product.id}-${item.selectedSize}`} className="summary-item">
                                    <div className="summary-item-info">
                                        <p className="summary-item-name">{item.product.name}</p>
                                        <p className="summary-item-details">{item.selectedSize} • {item.selectedColor} • x{item.quantity}</p>
                                    </div>
                                    <div className="summary-item-price">€{(item.product.price * item.quantity).toFixed(2)}</div>
                                </div>
                            ))}
                        </div>
                        <div className="summary-totals">
                            <div className="summary-row">
                                <span>Товари</span>
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
                        </div>
                    </aside>
                </div>
            </div>
        </div>
    );
}
