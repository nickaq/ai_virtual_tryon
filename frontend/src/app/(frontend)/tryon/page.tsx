/**
 * Virtual Try-On page.
 * Users upload their photo + a product image, tweak processing options,
 * and submit the job. Results are polled and displayed via TryOnResult.
 */
'use client';

import { Suspense, useState } from 'react';
import { useSearchParams } from 'next/navigation';
import TryOnUploader from '@/frontend/components/TryOnUploader';
import TryOnResult from '@/frontend/components/TryOnResult';
import { submitTryOnJob, pollJobUntilComplete, TryOnApiError } from '@/frontend/lib/tryonApi';
import type { TryOnStatusResponse } from '@/frontend/lib/tryonApi';
import './page.css';

/** Inner content (uses useSearchParams which requires Suspense). */
function TryOnContent() {
    const searchParams = useSearchParams();
    const productId = searchParams.get('product');

    // Form state
    const [userImage, setUserImage] = useState<File | null>(null);
    const [productImage, setProductImage] = useState<File | null>(null);
    const [garmentType, setGarmentType] = useState<string>('');
    const [mode, setMode] = useState<'draft' | 'final'>('final');
    const [realismLevel, setRealismLevel] = useState<1 | 2 | 3 | 4 | 5>(3);

    // Processing state
    const [isSubmitting, setIsSubmitting] = useState(false);
    const [jobStatus, setJobStatus] = useState<TryOnStatusResponse | null>(null);
    const [error, setError] = useState<string | null>(null);
    const [userImagePreview, setUserImagePreview] = useState<string | null>(null);

    /** Handle user photo selection — also generate a preview URL. */
    const handleUserImageSelect = (file: File | null) => {
        if (!file) {
            setUserImage(null);
            setUserImagePreview(null);
            return;
        }
        setUserImage(file);
        const reader = new FileReader();
        reader.onloadend = () => setUserImagePreview(reader.result as string);
        reader.readAsDataURL(file);
    };

    /** Submit the try-on job and poll until done or failed. */
    const handleSubmit = async () => {
        if (!userImage || !productImage) {
            setError('Please upload both your photo and select a product');
            return;
        }

        setError(null);
        setIsSubmitting(true);
        setJobStatus(null);

        try {
            const response = await submitTryOnJob({
                userImage,
                productImage,
                productId: productId || undefined,
                garmentType: garmentType || undefined,
                mode,
                realismLevel,
                preserveFace: true,
                preserveBackground: true,
                maxRetries: 2,
            });

            // Poll until terminal state
            const finalStatus = await pollJobUntilComplete(response.job_id, {
                onStatusUpdate: (s) => setJobStatus(s),
                pollInterval: 2000,
            });

            setJobStatus(finalStatus);
            if (finalStatus.status === 'FAILED') {
                setError(finalStatus.error_message || 'Try-on failed');
            }
        } catch (err) {
            setError(err instanceof TryOnApiError ? err.message : 'Failed to process try-on request');
        } finally {
            setIsSubmitting(false);
        }
    };

    const showForm = !jobStatus || jobStatus.status === 'FAILED';

    return (
        <div className="tryon-page">
            <div className="tryon-container container">
                {/* Header */}
                <div className="tryon-header reveal">
                    <h1>Віртуальна <span className="gradient-text">Примірка</span></h1>
                    <p>Відчуйте майбутнє шопінгу з нашою передовою технологією AI Vision.</p>
                </div>

                {/* Error banner */}
                {error && (
                    <div className="tryon-error reveal">
                        <p className="error-title">Помилка</p>
                        <p className="error-text">{error}</p>
                    </div>
                )}

                {/* Upload form */}
                {showForm ? (
                    <div className="tryon-form-card reveal">
                        {/* Image upload grid */}
                        <div className="tryon-upload-grid">
                            <TryOnUploader label="Ваше фото" onImageSelect={handleUserImageSelect} currentImage={userImage} />
                            <TryOnUploader label="Фото товару" onImageSelect={(f) => setProductImage(f)} currentImage={productImage} />
                        </div>

                        {/* Processing options */}
                        <div className="tryon-options-grid">
                            <div>
                                <label className="tryon-option-label">Тип одягу</label>
                                <select value={garmentType} onChange={(e) => setGarmentType(e.target.value)} className="tryon-select">
                                    <option value="">Авто-визначення</option>
                                    <option value="tshirt">Футболка</option>
                                    <option value="shirt">Сорочка</option>
                                    <option value="jacket">Піджак/Куртка</option>
                                    <option value="hoodie">Худі</option>
                                    <option value="dress">Сукня</option>
                                    <option value="pants">Штани</option>
                                </select>
                            </div>

                            <div>
                                <label className="tryon-option-label">Режим обробки</label>
                                <select value={mode} onChange={(e) => setMode(e.target.value as 'draft' | 'final')} className="tryon-select">
                                    <option value="final">Фінальний (Фотореалізм)</option>
                                    <option value="draft">Чернетка (Швидко)</option>
                                </select>
                            </div>

                            <div>
                                <label className="tryon-option-label">Рівень деталізації: {realismLevel}</label>
                                <div className="tryon-range-wrapper">
                                    <input
                                        type="range" min="1" max="5"
                                        value={realismLevel}
                                        onChange={(e) => setRealismLevel(Number(e.target.value) as 1 | 2 | 3 | 4 | 5)}
                                        disabled={mode === 'draft'}
                                    />
                                    <div className="tryon-range-labels">
                                        <span>Швидко</span>
                                        <span>Детально</span>
                                    </div>
                                </div>
                            </div>
                        </div>

                        {/* Submit */}
                        <div className="tryon-submit-wrapper">
                            <button
                                onClick={handleSubmit}
                                disabled={!userImage || !productImage || isSubmitting}
                                className="tryon-submit-btn btn btn-primary btn-lg"
                            >
                                {isSubmitting ? (
                                    <span className="tryon-submit-content">
                                        <div className="tryon-submit-spinner"></div>
                                        Обробка...
                                    </span>
                                ) : 'Почати примірювання'}
                            </button>
                            <p className="tryon-info-text">Обробка зазвичай триває від 10 до 30 секунд</p>
                        </div>
                    </div>
                ) : null}

                {/* Job result display */}
                {jobStatus && (
                    <TryOnResult status={jobStatus} userImagePreview={userImagePreview || undefined} />
                )}

                {/* "How it works" explainer */}
                {!jobStatus && (
                    <div className="tryon-how-it-works reveal">
                        <h2>Як це працює</h2>
                        <div className="tryon-steps-grid">
                            <div className="tryon-step">
                                <div className="tryon-step-number">1</div>
                                <h3>Завантажте фото</h3>
                                <p>Зробіть селфі або завантажте фото у повний зріст при хорошому освітленні.</p>
                            </div>
                            <div className="tryon-step">
                                <div className="tryon-step-number">2</div>
                                <h3>Оберіть товар</h3>
                                <p>Виберіть річ, яку хочете приміряти, з нашого великого каталогу.</p>
                            </div>
                            <div className="tryon-step">
                                <div className="tryon-step-number">3</div>
                                <h3>Отримайте результат</h3>
                                <p>Наш AI згенерує реалістичне зображення вас у новому образі.</p>
                            </div>
                        </div>
                    </div>
                )}
            </div>
        </div>
    );
}

/** Page wrapper with Suspense for `useSearchParams`. */
export default function TryOnPage() {
    return (
        <Suspense fallback={
            <div className="tryon-loading">
                <div className="tryon-loading-spinner"></div>
            </div>
        }>
            <TryOnContent />
        </Suspense>
    );
}
