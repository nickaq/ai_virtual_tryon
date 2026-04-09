# API Documentation

## Base URL
```
http://localhost:3000/api
```

## Endpoints

### Products

#### GET /api/products
Отримати список товарів з фільтрацією та пагінацією.

**Query Parameters:**
- `page` (number, optional) - Номер сторінки (за замовчуванням: 1)
- `limit` (number, optional) - Кількість товарів на сторінку (за замовчуванням: 20)
- `category` (string, optional) - Фільтр по категорії: `jackets`, `pants`, `shirts`, `shoes`, `accessories`
- `search` (string, optional) - Пошук по назві і опису
- `minPrice` (number, optional) - Мінімальна ціна
- `maxPrice` (number, optional) - Максимальна ціна
- `season` (string, optional) - Сезон: `spring`, `summer`, `fall`, `winter`, `all-season`

**Response:**
```json
{
  "products": [
    {
      "id": "cm65yw7fh0000144hfpnqbuvp",
      "name": "Premium Wool Coat",
      "description": "...",
      "price": 299.99,
      "category": "jackets",
      "sizes": ["S", "M", "L", "XL"],
      "colors": ["Чорний", "Темно-сірий"],
      "season": "winter",
      "composition": "90% вовна, 10% кашемір",
      "inStock": true,
      "imageUrl": null
    }
  ],
  "pagination": {
    "page": 1,
    "limit": 20,
    "total": 10,
    "totalPages": 1
  }
}
```

#### GET /api/products/:id
Отримати деталі конкретного товару.

**Response:**
```json
{
  "id": "...",
  "name": "...",
  "description": "...",
  "price": 299.99,
  "sizes": ["S", "M", "L"],
  "colors": ["..."],
  ...
}
```

---

### Orders

#### POST /api/orders
Створити нове замовлення.

**Request Body:**
```json
{
  "items": [
    {
      "productId": "cm65yw7fh0000144hfpnqbuvp",
      "quantity": 2,
      "selectedSize": "M",
      "selectedColor": "Чорний"
    }
  ],
  "contactName": "Іван Петренко",
  "email": "ivan@example.com",
  "phone": "+380123456789",
  "address": "вул. Хрещатик 1",
  "city": "Київ",
  "postalCode": "01001",
  "country": "Україна"
}
```

**Response:**
```json
{
  "orderId": "...",
  "status": "PENDING",
  "total": 599.98
}
```

#### GET /api/orders
Отримати список замовлень користувача.

**Response:**
```json
{
  "orders": [
    {
      "id": "...",
      "status": "PENDING",
      "total": 599.98,
      "createdAt": "2024-...",
      "items": [...]
    }
  ]
}
```

---

### AI Try-On

#### POST /api/try-on/upload
Завантажити фото для примірювання.

**Rate Limit:** 5 запитів на годину на IP

**Form Data:**
- `productId` (string) - ID товару
- `photo` (File) - Фото користувача (макс 10MB, image/*)

**Response:**
```json
{
  "jobId": "...",
  "status": "PENDING",
  "message": "Фото завантажено. Обробка почалася."
}
```

**Error (429):**
```json
{
  "error": "Перевищено ліміт запитів. Спробуйте пізніше.",
  "resetAt": 1707408000000
}
```

#### GET /api/try-on/:jobId
Отримати статус примірювання.

**Response:**
```json
{
  "id": "...",
  "status": "COMPLETED", // PENDING | PROCESSING | COMPLETED | FAILED
  "productId": "...",
  "userPhotoUrl": "/uploads/try-on/user-photos/...",
  "resultPhotoUrl": "/uploads/try-on/results/...", // null якщо не готово
  "errorMessage": null, // текст помилки якщо FAILED
  "createdAt": "...",
  "updatedAt": "..."
}
```

---

## Error Responses

Всі endpoints повертають помилки у форматі:

```json
{
  "error": "Опис помилки"
}
```

**HTTP Status Codes:**
- `400` - Bad Request (некоректні дані)
- `401` - Unauthorized (потрібна авторизація)
- `404` - Not Found (ресурс не знайдено)
- `429` - Too Many Requests (rate limit)
- `500` - Internal Server Error

---

## Security

### API Keys
Всі чутливі ключі зберігаються в `.env.local` і **не включені в git**.

### Rate Limiting
- Try-on upload: 5 запитів/годину на IP
- Інші endpoints: без обмежень (можна додати при потребі)

### File Upload
- Максимальний розмір: 10MB
- Дозволені типи: image/*
- Автоматичне видалення фото через 7 днів

### Data Privacy
- Персональні дані не логуються
- Фото користувачів захищені і доступні лише власникам
- Автоматичне видалення після використання

---

## Development

### Testing API

```bash
# Get products
curl http://localhost:3000/api/products

# Get product by ID
curl http://localhost:3000/api/products/cm65yw7fh0000144hfpnqbuvp

# Create order
curl -X POST http://localhost:3000/api/orders \
  -H "Content-Type: application/json" \
  -d '{"items":[...],"contactName":"...",...}'

# Upload try-on photo
curl -X POST http://localhost:3000/api/try-on/upload \
  -F "productId=..." \
  -F "photo=@/path/to/photo.jpg"
```

### Logs

Логи зберігаються в директорії `logs/`:
- `error.log` - тільки помилки
- `combined.log` - всі логи

Персональні дані автоматично фільтруються.
