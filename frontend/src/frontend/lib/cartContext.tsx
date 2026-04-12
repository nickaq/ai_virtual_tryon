/**
 * Shopping cart context provider.
 * Persists cart state to localStorage and exposes add/remove/update helpers.
 */
'use client';

import React, { createContext, useContext, useState, useEffect } from 'react';
import { CartItem, Product } from '@/shared/types';

// ---------------------------------------------------------------------------
// Context type
// ---------------------------------------------------------------------------

interface CartContextType {
    items: CartItem[];
    addToCart: (product: Product, size: string, color: string, quantity?: number) => void;
    removeFromCart: (productId: string, size: string, color: string) => void;
    updateQuantity: (productId: string, size: string, color: string, quantity: number) => void;
    clearCart: () => void;
    getTotal: () => number;
    getItemCount: () => number;
}

const CartContext = createContext<CartContextType | undefined>(undefined);

// ---------------------------------------------------------------------------
// Hook
// ---------------------------------------------------------------------------

/** Access the cart from any component inside <CartProvider>. */
export const useCart = () => {
    const context = useContext(CartContext);
    if (!context) {
        throw new Error('useCart must be used within CartProvider');
    }
    return context;
};

// ---------------------------------------------------------------------------
// Provider
// ---------------------------------------------------------------------------

/** Wraps the app to provide shopping cart state and persistence. */
export const CartProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
    const [items, setItems] = useState<CartItem[]>([]);
    const [isHydrated, setIsHydrated] = useState(false);

    // Restore cart from localStorage on mount
    useEffect(() => {
        const savedCart = localStorage.getItem('cart');
        if (savedCart) {
            try {
                setItems(JSON.parse(savedCart));
            } catch {
                // Ignore malformed JSON
            }
        }
        setIsHydrated(true);
    }, []);

    // Persist cart to localStorage on every change (only after hydration)
    useEffect(() => {
        if (isHydrated) {
            localStorage.setItem('cart', JSON.stringify(items));
        }
    }, [items, isHydrated]);

    /** Add a product to the cart (or increment if already present). */
    const addToCart = (product: Product, size: string, color: string, quantity: number = 1) => {
        setItems(prev => {
            const existing = prev.find(
                i => i.product.id === product.id && i.selectedSize === size && i.selectedColor === color
            );
            if (existing) {
                return prev.map(i =>
                    i.product.id === product.id && i.selectedSize === size && i.selectedColor === color
                        ? { ...i, quantity: i.quantity + quantity }
                        : i
                );
            }
            return [...prev, { product, quantity, selectedSize: size, selectedColor: color }];
        });
    };

    /** Remove a specific item from the cart by product + variant key. */
    const removeFromCart = (productId: string, size: string, color: string) => {
        setItems(prev =>
            prev.filter(i => !(i.product.id === productId && i.selectedSize === size && i.selectedColor === color))
        );
    };

    /** Set the quantity for a specific cart item. Removes the item if quantity ≤ 0. */
    const updateQuantity = (productId: string, size: string, color: string, quantity: number) => {
        if (quantity <= 0) {
            removeFromCart(productId, size, color);
            return;
        }
        setItems(prev =>
            prev.map(i =>
                i.product.id === productId && i.selectedSize === size && i.selectedColor === color
                    ? { ...i, quantity }
                    : i
            )
        );
    };

    /** Empty the cart completely. */
    const clearCart = () => setItems([]);

    /** Calculate the total price of all items in the cart. */
    const getTotal = () => items.reduce((sum, i) => sum + i.product.price * i.quantity, 0);

    /** Count the total number of items (including duplicates). */
    const getItemCount = () => items.reduce((sum, i) => sum + i.quantity, 0);

    return (
        <CartContext.Provider
            value={{ items, addToCart, removeFromCart, updateQuantity, clearCart, getTotal, getItemCount }}
        >
            {children}
        </CartContext.Provider>
    );
};
