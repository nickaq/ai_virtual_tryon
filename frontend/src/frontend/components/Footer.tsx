/**
 * Site-wide footer with company info, help links, newsletter, and socials.
 */
import './Footer.css';

export default function Footer() {
    return (
        <footer className="footer">
            <div className="container footer-content">
                {/* About section */}
                <div className="footer-section">
                    <h3>Про нас</h3>
                    <ul>
                        <li><a href="#">Про компанію</a></li>
                        <li><a href="#">Кар&apos;єра</a></li>
                        <li><a href="#">Контакти</a></li>
                    </ul>
                </div>

                {/* Help section */}
                <div className="footer-section">
                    <h3>Допомога</h3>
                    <ul>
                        <li><a href="#">Доставка</a></li>
                        <li><a href="#">Повернення</a></li>
                        <li><a href="#">FAQ</a></li>
                    </ul>
                </div>

                {/* Newsletter */}
                <div className="footer-section">
                    <h3>Підписка</h3>
                    <p>Отримуйте новини про нові колекції та знижки</p>
                    <div className="newsletter-form">
                        <input type="email" placeholder="Ваш email" />
                        <button className="btn btn-primary">Підписатися</button>
                    </div>
                </div>

                {/* Social links */}
                <div className="footer-section">
                    <h3>Слідкуйте за нами</h3>
                    <div className="social-links">
                        <a href="#" aria-label="Instagram">📷</a>
                        <a href="#" aria-label="Facebook">📘</a>
                        <a href="#" aria-label="Twitter">🐦</a>
                    </div>
                </div>
            </div>

            {/* Copyright */}
            <div className="footer-bottom">
                <div className="container">
                    <p>&copy; 2026 StyleAI. Всі права захищені.</p>
                </div>
            </div>
        </footer>
    );
}
