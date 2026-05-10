# Полный гайд по деплою на Ubuntu (удалённый сервер с GPU)

Все команды выполнять **на Ubuntu сервере**, подключившись по SSH.

---

## 1. Подключение к серверу

С локальной машины:

```bash
ssh -p <PORT> root@<IP> -L 3000:localhost:3000 -L 8000:localhost:8000
```

Замени `<PORT>` и `<IP>` на свои. Туннель пробросит порты 3000 (frontend) и 8000 (backend) на твой локальный браузер.

---

## 2. Установка системных зависимостей

```bash
apt update
apt install -y git curl wget nano build-essential
```

---

## 3. Установка Docker (если не установлен)

```bash
curl -fsSL https://get.docker.com -o get-docker.sh
sh get-docker.sh
```

Проверка:
```bash
docker --version
docker compose version
```

Если используется старый `docker-compose` (с дефисом):
```bash
apt install -y docker-compose
```

---

## 4. Установка NVIDIA Container Toolkit (для GPU)

Только если контейнер поддерживает (на vast.ai обычно уже стоит).

```bash
distribution=$(. /etc/os-release;echo $ID$VERSION_ID)
curl -s -L https://nvidia.github.io/libnvidia-container/gpgkey | apt-key add -
curl -s -L https://nvidia.github.io/libnvidia-container/$distribution/libnvidia-container.list | tee /etc/apt/sources.list.d/nvidia-container-toolkit.list
apt update
apt install -y nvidia-container-toolkit
nvidia-ctk runtime configure --runtime=docker
```

Проверка GPU:
```bash
nvidia-smi
```

---

## 5. Клонирование проекта

```bash
cd /workspace   # или любая удобная директория
git clone <YOUR_REPO_URL> ai_virtual_tryon
cd ai_virtual_tryon
```

---

## 6. Создание .env файла

```bash
nano .env
```

Вставь следующее содержимое (Ctrl+Shift+V для вставки), затем сохрани (Ctrl+O, Enter) и выйди (Ctrl+X):

```ini
# ── Server ─────────────────────────────────────────────────────
HOST=0.0.0.0
PORT=8000
WORKERS=1
DEBUG=false

# ── Storage ────────────────────────────────────────────────────
STORAGE_PATH=/app/storage

# ── GPU ────────────────────────────────────────────────────────
DIFFUSION_DEVICE=cuda
NVIDIA_VISIBLE_DEVICES=all
NVIDIA_DRIVER_CAPABILITIES=compute,utility

# ── Image constraints ──────────────────────────────────────────
MAX_IMAGE_SIZE_MB=10
MAX_IMAGE_DIMENSION=2048
WORK_IMAGE_SIZE=1536

# ── Quality control ────────────────────────────────────────────
QUALITY_THRESHOLD=0.5
MAX_RETRIES=2
SAVE_DEBUG_ARTIFACTS=false

# ── IDM-VTON path (внутри контейнера) ──────────────────────────
IDM_VTON_PATH=/app/IDM-VTON

# ── VTON multi-sample & reranking ──────────────────────────────
VTON_NUM_SAMPLES=1
VTON_MIN_SCORE=0.55
VTON_SEAM_FEATHER_PX=11
VTON_SEAM_ERODE_PX=2
VTON_GARMENT_WEIGHT=0.5

# ── Preflight quality gates ────────────────────────────────────
PREFLIGHT_MIN_DIM=384
PREFLIGHT_BLUR_MIN=40.0
PREFLIGHT_MIN_FACE_AREA=0.003
PREFLIGHT_MIN_PERSON_AREA=0.10
PREFLIGHT_BORDER_CUTOFF_FRAC=0.35

# ── Garment-only super-resolution ──────────────────────────────
VTON_GARMENT_SR=0
VTON_GARMENT_SR_SCALE=2
VTON_GARMENT_SR_PAD=16
VTON_GARMENT_SR_FEATHER=5
REALESRGAN_WEIGHTS=/app/models/RealESRGAN_x2plus.pth
```

---

## 7. Сборка и запуск

```bash
# Сборка (первый раз ~10-20 минут — качаются модели)
docker compose build

# Запуск в фоне
docker compose up -d

# Просмотр логов
docker compose logs -f backend
```

Если используешь старый `docker-compose`:
```bash
docker-compose build
docker-compose up -d
docker-compose logs -f backend
```

---

## 8. Проверка работы

```bash
# Статус контейнеров
docker compose ps

# Backend health
curl http://localhost:8000/health

# Логи backend
docker compose logs backend | tail -50

# Логи frontend
docker compose logs frontend | tail -50
```

В браузере (после SSH-туннеля):
- Frontend: http://localhost:3000
- Backend API: http://localhost:8000
- Health: http://localhost:8000/health

---

## 9. Управление

```bash
# Остановить
docker compose down

# Перезапустить
docker compose restart

# Пересобрать после изменений в Dockerfile
docker compose build --no-cache backend
docker compose up -d

# Полная очистка (включая volumes)
docker compose down -v
docker system prune -af
```

---

## 10. Где искать результаты

Сгенерированные фото на хосте:

```bash
ls -la storage/results/
```

Загруженные фото:

```bash
ls -la storage/uploads/
```

Логи приложения:

```bash
ls -la logs/
```

---

## 11. Если что-то не работает

```bash
# Полные логи backend
docker compose logs backend

# Зайти внутрь контейнера
docker exec -it ai-tryon-backend bash

# Проверить GPU внутри контейнера
docker exec ai-tryon-backend nvidia-smi

# Проверить что модели скачались
docker exec ai-tryon-backend ls -la /app/IDM-VTON/ckpt/
```

---

## 12. Обновление кода

```bash
git pull
docker compose build backend
docker compose up -d
```

---

## Краткая шпаргалка (одной командой всё)

```bash
apt update && apt install -y git curl nano && \
curl -fsSL https://get.docker.com | sh && \
cd /workspace && \
git clone <YOUR_REPO_URL> ai_virtual_tryon && \
cd ai_virtual_tryon && \
nano .env && \
docker compose build && \
docker compose up -d && \
docker compose logs -f backend
```
