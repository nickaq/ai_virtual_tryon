/**
 * AI Stylist page — chat-based personal fashion assistant.
 * Users can select quick filters (budget, season, style) and get
 * product recommendations from the backend API.
 */
'use client';

import { useState, useRef, useEffect } from 'react';
import ProductCard from '@/frontend/components/ProductCard';
import { Product } from '@/shared/types';
import './page.css';

/** A single chat message with optional product recommendations. */
interface ChatMessage {
    role: 'user' | 'assistant';
    content: string;
    products?: Product[];
}

export default function StylistPage() {
    const [messages, setMessages] = useState<ChatMessage[]>([
        {
            role: 'assistant',
            content: 'Привіт! Я ваш AI-стиліст. Допоможу підібрати ідеальний образ. Розкажіть про свої уподобання: який стиль вам близький, який у вас бюджет, для якого сезону підбираємо одяг?',
        },
    ]);
    const [input, setInput] = useState('');
    const [selectedFilters, setSelectedFilters] = useState<{
        budget?: string;
        season?: string;
        style?: string;
    }>({});
    const messagesEndRef = useRef<HTMLDivElement>(null);

    // Auto-scroll to the latest message
    useEffect(() => {
        messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
    }, [messages]);

    /** Fetch product recommendations from the API and format them. */
    const fetchRecommendations = async (): Promise<Product[]> => {
        try {
            const res = await fetch('/api/products?limit=3');
            if (!res.ok) return [];
            const data = await res.json();
            return data.products.map((p: Record<string, unknown>) => ({
                ...p,
                images: p.imageUrl ? [p.imageUrl as string] : ['/placeholder.jpg'],
            }));
        } catch {
            return [];
        }
    };

    /** Handle a quick-filter button press (budget / season / style). */
    const handleQuickFilter = (type: 'budget' | 'season' | 'style', value: string) => {
        setSelectedFilters(prev => ({ ...prev, [type]: value }));
        const label = type === 'style' ? 'образ в стилі' : type === 'season' ? 'одяг для сезону' : 'варіанти в бюджеті';
        sendMessage(`Чудово! Я підберу ${label} "${value}".`, true);
    };

    /** Send a message and generate an AI response with product recommendations. */
    const sendMessage = async (messageText: string, isAutoMessage = false) => {
        const userMessage = messageText || input;
        if (!userMessage.trim()) return;

        setMessages(prev => [...prev, { role: 'user', content: userMessage }]);
        if (!isAutoMessage) setInput('');

        // Simulate AI thinking time, then respond with product recommendations
        const recommendations = await fetchRecommendations();

        setMessages(prev => [
            ...prev,
            {
                role: 'assistant',
                content: 'Ось кілька варіантів, які можуть вам підійти:',
                products: recommendations,
            },
        ]);
    };

    return (
        <div className="stylist-page">
            <div className="container">
                {/* Page header */}
                <div className="stylist-header">
                    <h1>🤖 AI Стиліст</h1>
                    <p>Персональний помічник у виборі одягу</p>
                </div>

                <div className="stylist-layout">
                    {/* Quick filter sidebar */}
                    <div className="quick-filters">
                        {/* Budget filter */}
                        <div className="filter-group">
                            <h4>Бюджет:</h4>
                            <div className="filter-buttons">
                                {['< €100', '€100-€200', '> €200'].map(budget => (
                                    <button
                                        key={budget}
                                        className={`filter-btn ${selectedFilters.budget === budget ? 'active' : ''}`}
                                        onClick={() => handleQuickFilter('budget', budget)}
                                    >
                                        {budget}
                                    </button>
                                ))}
                            </div>
                        </div>

                        {/* Season filter */}
                        <div className="filter-group">
                            <h4>Сезон:</h4>
                            <div className="filter-buttons">
                                {['Весна', 'Літо', 'Осінь', 'Зима'].map(season => (
                                    <button
                                        key={season}
                                        className={`filter-btn ${selectedFilters.season === season ? 'active' : ''}`}
                                        onClick={() => handleQuickFilter('season', season)}
                                    >
                                        {season}
                                    </button>
                                ))}
                            </div>
                        </div>

                        {/* Style filter */}
                        <div className="filter-group">
                            <h4>Стиль:</h4>
                            <div className="filter-buttons">
                                {['Casual', 'Smart Casual', 'Formal', 'Street'].map(style => (
                                    <button
                                        key={style}
                                        className={`filter-btn ${selectedFilters.style === style ? 'active' : ''}`}
                                        onClick={() => handleQuickFilter('style', style)}
                                    >
                                        {style}
                                    </button>
                                ))}
                            </div>
                        </div>
                    </div>

                    {/* Chat interface */}
                    <div className="chat-container">
                        <div className="chat-messages">
                            {messages.map((message, index) => (
                                <div key={index} className={`message ${message.role}`}>
                                    <div className="message-content">
                                        <p>{message.content}</p>
                                        {message.products && (
                                            <div className="message-products">
                                                {message.products.map(product => (
                                                    <ProductCard key={product.id} product={product} />
                                                ))}
                                            </div>
                                        )}
                                    </div>
                                </div>
                            ))}
                            <div ref={messagesEndRef} />
                        </div>

                        {/* Chat text input */}
                        <div className="chat-input">
                            <input
                                type="text"
                                value={input}
                                onChange={(e) => setInput(e.target.value)}
                                onKeyDown={(e) => e.key === 'Enter' && sendMessage(input)}
                                placeholder="Опишіть, що ви шукаєте..."
                            />
                            <button onClick={() => sendMessage(input)} className="btn btn-primary">
                                Надіслати
                            </button>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    );
}
