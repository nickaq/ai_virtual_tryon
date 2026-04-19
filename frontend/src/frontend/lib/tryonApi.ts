/**
 * API client for the Virtual Try-On backend (FastAPI).
 * Handles job submission, status polling, and result retrieval.
 */

// ---------------------------------------------------------------------------
// Types (inlined from the removed backend/types/tryon.ts)
// ---------------------------------------------------------------------------

/** Parameters for submitting a try-on job. */
export interface TryOnJobRequest {
    userImage?: File;
    userImageUrl?: string;
    productImage?: File;
    productImageUrl?: string;
    productId?: string;
    garmentType?: string;
    mode?: 'draft' | 'final';
    preserveFace?: boolean;
    preserveBackground?: boolean;
    realismLevel?: number;
    maxRetries?: number;
}

/** Response received after successfully submitting a job. */
export interface TryOnJobResponse {
    job_id: string;
    status: string;
    message: string;
}

/** Detailed status of a try-on job (returned by the status endpoint). */
export interface TryOnStatusResponse {
    job_id: string;
    status: 'QUEUED' | 'PROCESSING' | 'DONE' | 'FAILED';
    result_image_url?: string;
    quality_score?: number;
    error_code?: string;
    error_message?: string;
    retry_count: number;
    created_at: string;
    updated_at: string;
    started_at?: string;
    completed_at?: string;
}

// ---------------------------------------------------------------------------
// Configuration
// ---------------------------------------------------------------------------

const API_BASE_URL = process.env.NEXT_PUBLIC_TRYON_API_URL || 'http://localhost:8000';

// ---------------------------------------------------------------------------
// Error class
// ---------------------------------------------------------------------------

/** Custom error class for try-on API failures. */
export class TryOnApiError extends Error {
    constructor(
        message: string,
        public code: string,
        public details?: unknown
    ) {
        super(message);
        this.name = 'TryOnApiError';
    }
}

// ---------------------------------------------------------------------------
// API functions
// ---------------------------------------------------------------------------

/** Submit a virtual try-on job to the backend. */
export async function submitTryOnJob(request: TryOnJobRequest): Promise<TryOnJobResponse> {
    const formData = new FormData();

    // Attach user image (file or URL, at least one required)
    if (request.userImage) {
        formData.append('user_image', request.userImage);
    } else if (request.userImageUrl) {
        formData.append('user_image_url', request.userImageUrl);
    } else {
        throw new TryOnApiError('User image is required', 'MISSING_USER_IMAGE');
    }

    // Attach product image (file or URL, at least one required)
    if (request.productImage) {
        formData.append('product_image', request.productImage);
    } else if (request.productImageUrl) {
        formData.append('product_image_url', request.productImageUrl);
    } else {
        throw new TryOnApiError('Product image is required', 'MISSING_PRODUCT_IMAGE');
    }

    // Optional processing parameters
    if (request.productId) formData.append('product_id', request.productId);
    if (request.garmentType) formData.append('cloth_category', request.garmentType);
    if (request.mode) {
        const generationMode = request.mode === 'draft' ? 'fast' : 'quality';
        formData.append('generation_mode', generationMode);
    }
    if (request.preserveFace !== undefined) formData.append('preserve_face', String(request.preserveFace));
    if (request.preserveBackground !== undefined) formData.append('preserve_background', String(request.preserveBackground));
    if (request.realismLevel) formData.append('realism_level', String(request.realismLevel));
    if (request.maxRetries !== undefined) formData.append('max_retries', String(request.maxRetries));

    try {
        const response = await fetch(`${API_BASE_URL}/ai/tryon/submit`, {
            method: 'POST',
            body: formData,
        });

        if (!response.ok) {
            const error = await response.json().catch(() => ({}));
            throw new TryOnApiError(
                error.detail || `HTTP ${response.status}: ${response.statusText}`,
                'SUBMIT_FAILED',
                error
            );
        }

        return await response.json();
    } catch (error) {
        if (error instanceof TryOnApiError) throw error;
        throw new TryOnApiError(
            `Failed to submit try-on job: ${error instanceof Error ? error.message : 'Unknown error'}`,
            'NETWORK_ERROR',
            error
        );
    }
}

/** Check the current status of a try-on job by its ID. */
export async function checkJobStatus(jobId: string): Promise<TryOnStatusResponse> {
    try {
        const response = await fetch(`${API_BASE_URL}/ai/tryon/status/${jobId}`);

        if (!response.ok) {
            const error = await response.json().catch(() => ({}));
            throw new TryOnApiError(
                error.detail || `HTTP ${response.status}: ${response.statusText}`,
                'STATUS_CHECK_FAILED',
                error
            );
        }

        return await response.json();
    } catch (error) {
        if (error instanceof TryOnApiError) throw error;
        throw new TryOnApiError(
            `Failed to check job status: ${error instanceof Error ? error.message : 'Unknown error'}`,
            'NETWORK_ERROR',
            error
        );
    }
}

/** Build the full URL for downloading a result image. */
export function getResultImageUrl(jobId: string): string {
    return `${API_BASE_URL}/ai/tryon/result/${jobId}`;
}

/**
 * Poll the status endpoint at regular intervals until the job
 * reaches a terminal state (DONE or FAILED) or times out.
 */
export async function pollJobUntilComplete(
    jobId: string,
    options: {
        onStatusUpdate?: (status: TryOnStatusResponse) => void;
        pollInterval?: number;
        maxAttempts?: number;
    } = {}
): Promise<TryOnStatusResponse> {
    const {
        onStatusUpdate,
        pollInterval = 2000,   // 2 seconds
        maxAttempts = 150      // 5 minutes max
    } = options;

    let attempts = 0;

    while (attempts < maxAttempts) {
        const status = await checkJobStatus(jobId);
        onStatusUpdate?.(status);

        if (status.status === 'DONE' || status.status === 'FAILED') {
            return status;
        }

        await new Promise(resolve => setTimeout(resolve, pollInterval));
        attempts++;
    }

    throw new TryOnApiError('Job polling timed out', 'TIMEOUT', { jobId, attempts });
}

/** Quick health-check for the backend API. Returns `true` if healthy. */
export async function checkApiHealth(): Promise<boolean> {
    try {
        const response = await fetch(`${API_BASE_URL}/health`);
        return response.ok;
    } catch {
        return false;
    }
}
