/**
 * Root layout component for the (frontend) route group.
 * Loads fonts, wraps children in CartProvider, and renders Header + Footer.
 */
import type { Metadata } from "next";
import { Inter, Syne } from "next/font/google";
import { CartProvider } from "@/frontend/lib/cartContext";
import Header from "@/frontend/components/Header";
import Footer from "@/frontend/components/Footer";
import "./globals.css";

// Google Fonts — Inter for body copy, Syne for professional avant-garde headings
const inter = Inter({
    variable: "--font-inter",
    subsets: ["latin", "cyrillic"],
});

const syne = Syne({
    variable: "--font-syne",
    subsets: ["latin"],
});

// Page-level metadata (title & description)
export const metadata: Metadata = {
    title: "StyleAI | Future of Fashion",
    description: "Персональний AI-стиліст та віртуальне примірювання одягу майбутнього.",
};

export default function RootLayout({
    children,
}: Readonly<{
    children: React.ReactNode;
}>) {
    return (
        <html lang="ru">
            <body className={`${inter.variable} ${syne.variable}`} suppressHydrationWarning>
                <CartProvider>
                    <Header />
                    <main>{children}</main>
                    <Footer />
                </CartProvider>
            </body>
        </html>
    );
}
