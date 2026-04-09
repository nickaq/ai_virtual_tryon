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
            <div className="tryon-container">
                {/* Header */}
                <div className="tryon-header">
                    <h1>Virtual Try-On</h1>
                    <p>See how clothes look on you with AI-powered virtual try-on</p>
                </div>

                {/* Error banner */}
                {error && (
                    <div className="tryon-error">
                        <p className="error-title">Error</p>
                        <p className="error-text">{error}</p>
                    </div>
                )}

                {/* Upload form */}
                {showForm ? (
                    <div className="tryon-form-card">
                        {/* Image upload grid */}
                        <div className="tryon-upload-grid">
                            <TryOnUploader label="Your Photo" onImageSelect={handleUserImageSelect} currentImage={userImage} />
                            <TryOnUploader label="Product Image" onImageSelect={(f) => setProductImage(f)} currentImage={productImage} />
                        </div>

                        {/* Processing options */}
                        <div className="tryon-options-grid">
                            <div>
                                <label className="tryon-option-label">Garment Type (Optional)</label>
                                <select value={garmentType} onChange={(e) => setGarmentType(e.target.value)} className="tryon-select">
                                    <option value="">Auto-detect</option>
                                    <option value="tshirt">T-Shirt</option>
                                    <option value="shirt">Shirt</option>
                                    <option value="jacket">Jacket</option>
                                    <option value="hoodie">Hoodie</option>
                                    <option value="dress">Dress</option>
                                    <option value="pants">Pants</option>
                                </select>
                            </div>

                            <div>
                                <label className="tryon-option-label">Processing Mode</label>
                                <select value={mode} onChange={(e) => setMode(e.target.value as 'draft' | 'final')} className="tryon-select">
                                    <option value="final">Final (Photorealistic)</option>
                                    <option value="draft">Draft (Fast Preview)</option>
                                </select>
                            </div>

                            <div>
                                <label className="tryon-option-label">Realism Level: {realismLevel}</label>
                                <div className="tryon-range-wrapper">
                                    <input
                                        type="range" min="1" max="5"
                                        value={realismLevel}
                                        onChange={(e) => setRealismLevel(Number(e.target.value) as 1 | 2 | 3 | 4 | 5)}
                                        disabled={mode === 'draft'}
                                    />
                                    <div className="tryon-range-labels">
                                        <span>Fast</span>
                                        <span>Detailed</span>
                                    </div>
                                </div>
                            </div>
                        </div>

                        {/* Submit */}
                        <div className="tryon-submit-wrapper">
                            <button
                                onClick={handleSubmit}
                                disabled={!userImage || !productImage || isSubmitting}
                                className="tryon-submit-btn"
                            >
                                {isSubmitting ? (
                                    <span className="tryon-submit-content">
                                        <div className="tryon-submit-spinner"></div>
                                        Processing...
                                    </span>
                                ) : 'Try On Now'}
                            </button>
                        </div>

                        <p className="tryon-info-text">Processing typically takes 10-30 seconds</p>
                    </div>
                ) : null}

                {/* Job result display */}
                {jobStatus && (
                    <TryOnResult status={jobStatus} userImagePreview={userImagePreview || undefined} />
                )}

                {/* "How it works" explainer (shown only before a job is submitted) */}
                {!jobStatus && (
                    <div className="tryon-how-it-works">
                        <h2>How It Works</h2>
                        <div className="tryon-steps-grid">
                            <div className="tryon-step">
                                <div className="tryon-step-number">1</div>
                                <h3>Upload Your Photo</h3>
                                <p>Take a selfie or upload a full-body photo with good lighting</p>
                            </div>
                            <div className="tryon-step">
                                <div className="tryon-step-number">2</div>
                                <h3>Select Product</h3>
                                <p>Choose the clothing item you want to try on</p>
                            </div>
                            <div className="tryon-step">
                                <div className="tryon-step-number">3</div>
                                <h3>See the Result</h3>
                                <p>AI generates a photorealistic image with you wearing the product</p>
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
