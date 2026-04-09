/**
 * Display name maps for product categories and seasons.
 * Used across catalog, product pages, and filters.
 */

/** Human-readable Ukrainian names for product categories. */
const categoryNames: Record<string, string> = {
    jackets: 'Куртки',
    pants: 'Штани',
    shirts: 'Сорочки',
    shoes: 'Взуття',
    accessories: 'Аксесуари',
};

/** Human-readable Ukrainian names for seasons. */
const seasonNames: Record<string, string> = {
    spring: 'Весна',
    summer: 'Літо',
    fall: 'Осінь',
    winter: 'Зима',
    'all-season': 'Всесезонний',
};

/** Returns the localized display name for a product category. */
export function getCategoryName(category: string): string {
    return categoryNames[category] || category;
}

/** Returns the localized display name for a season. */
export function getSeasonName(season: string): string {
    return seasonNames[season] || season;
}
