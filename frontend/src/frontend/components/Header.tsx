/**
 * Site-wide header with navigation and cart badge.
 */
'use client';

import Link from 'next/link';
import { useCart } from '@/frontend/lib/cartContext';
import './Header.css';

export default function Header() {
    const { getItemCount } = useCart();
    const itemCount = getItemCount();

    return (
        <header className="header">
            <div className="container header-content">
                {/* Logo */}
                <Link href="/" className="logo">
                    <span className="logo-icon">👔</span>
                    <span className="logo-text">StyleAI</span>
                </Link>

                {/* Main navigation */}
                <nav className="nav">
                    <Link href="/catalog" className="nav-link">Каталог</Link>
                    <Link href="/stylist" className="nav-link">AI Стиліст</Link>
                </nav>

                {/* Cart button with badge */}
                <div className="header-actions">
                    <Link href="/cart" className="cart-button">
                        <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                            <path d="M9 2L7 6H3L6 20H18L21 6H17L15 2H9Z" />
                            <circle cx="10" cy="20" r="1" />
                            <circle cx="16" cy="20" r="1" />
                        </svg>
                        {itemCount > 0 && <span className="cart-badge">{itemCount}</span>}
                    </Link>
                </div>
            </div>
        </header>
    );
}
