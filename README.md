# OmniOS — Автоматизация бронирования отелей и продаж с использованием ИИ

OmniOS — это мультиарендная (Multi-tenant) CRM-система, разработанная для отельного бизнеса с целью автоматизации общения с гостями, управления лидами и обработки бронирований с помощью специализированных ИИ-агентов на базе LLM в таких каналах связи, как WhatsApp, Telegram и Instagram.

---

## 🏗️ Архитектура

```mermaid
graph TD
    Client["Панель управления (React / Vite)"] <-->|HTTP / WebSockets| API["Backend API (Django REST Framework)"]
    Mobile["Мобильное приложение (React Native / Expo)"] <-->|HTTP / WebSockets| API
    API <-->|Чтение / Запись| DB[("PostgreSQL")]
    API <-->|Очередь задач / Кэш| Redis[("Redis")]
    CeleryWorker["Celery-воркер"] <-->|Обработка задач| Redis
    CeleryBeat["Celery Beat (Планировщик)"] -->|Запуск задач| Redis
    CeleryWorker <-->|Чтение / Запись| DB
    CeleryWorker <-->|Запросы API| AIProviders["ИИ-провайдеры (Gemini / OpenAI / Groq / DeepSeek)"]
    API <-->|Запросы API| AIProviders
```

---

## 🛠️ Стек технологий

| Компонент | Технология | Версия |
| :--- | :--- | :--- |
| **Backend API** | Django REST Framework | Django ^5.2 (LTS), DRF ^3.16.1 |
| **Очередь задач / Кэш** | Redis | Redis ^7.0 |
| **База данных** | PostgreSQL | PostgreSQL ^17.0 |
| **Асинхронные задачи** | Celery | Celery ^5.4 |
| **Frontend Web** | React + TypeScript + Vite | React ^19.0, Vite ^6.0, TypeScript ~5.7.2 |
| **Мобильное приложение** | React Native (Expo) | React Native ^0.81.5, Expo ^54.0.31 |
| **Стилизация** | Tailwind CSS | Tailwind ^4.1.18 |
| **Интеграция ИИ** | LangGraph & SDKs | LangGraph ^0.2.70, OpenAI ^1.58, Google GenAI ^1.0 |

---

## 🚀 Быстрый старт

Запустите весь стек локально с помощью Docker Compose всего за несколько команд:

```bash
git clone <repository-url>
cp .env.example .env
# Откройте .env и заполните AI_PROVIDER и соответствующие API-ключи
docker compose up --build
```

---

## ⚙️ Переменные окружения

Система использует переменные, загружаемые из файла `.env` в корне проекта. Актуальный шаблон со значениями по умолчанию — в [.env.example](.env.example). В таблице ниже описаны ключевые переменные конфигурации, определенные в [settings.py](backend/config/settings.py):

| Имя переменной | Описание | Пример значения | Обязательная? |
| :--- | :--- | :--- | :--- |
| `DJANGO_SECRET_KEY` | Секретный ключ Django, используемый для обеспечения безопасности и шифрования. | `django-insecure-xxx...` | Да (для продакшена) |
| `DJANGO_DEBUG` | Флаг для запуска Django в режиме отладки. | `False` | Нет (по умолчанию: `False`) |
| `DJANGO_ALLOWED_HOSTS` | Список разрешенных хостов/доменов через запятую. | `localhost,127.0.0.1,backend` | Нет |
| `CORS_ALLOWED_ORIGINS` | Список разрешенных адресов для CORS-запросов через запятую. | `http://localhost:5173,http://localhost:8081` | Нет |
| `ENVIRONMENT` | Тип окружения запуска. | `production` или `development` | Нет (по умолчанию: `development`) |
| `ENABLE_PRODUCTION_SECURITY` | Включение настроек безопасности HTTPS для продакшена. | `True` | Нет (по умолчанию: `False`, если environment не production) |
| `DB_NAME` | Имя базы данных PostgreSQL (используется в Docker Compose). | `axon_prod` | Нет (по умолчанию: `axon_prod`) |
| `DB_USER` | Пользователь PostgreSQL (используется в Docker Compose). | `postgres` | Нет (по умолчанию: `postgres`) |
| `DB_PASSWORD` | Пароль от базы данных PostgreSQL. | `secure_password` | Да |
| `DATABASE_URL` | Строка подключения к PostgreSQL (имеет приоритет над отдельными переменными БД). | `postgresql://postgres:postgres@localhost:5433/app_dev` | Да (если запуск без Docker) |
| `CELERY_BROKER_URL` | Строка подключения к брокеру Redis для Celery. | `redis://localhost:6379/0` | Нет |
| `CELERY_RESULT_BACKEND` | Строка подключения к бэкенду результатов Redis для Celery. | `redis://localhost:6379/0` | Нет |
| `APP_DOMAIN` | Публичный домен HTTPS (критически важен для Telegram Webhook). | `https://my-tunnel.trycloudflare.com` | Да (для работы Telegram Webhook) |
| `AI_AGENT_BEAT_SECONDS` | Интервал (сек), с которым Celery Beat проверяет короткие ИИ-напоминания; общая частота follow-up настраивается в CRM (Настройки ИИ). | `60` | Нет (по умолчанию: `60`) |
| `AI_PROVIDER` | Выбранный провайдер ИИ (`gemini`, `openai`, `groq`, `deepseek`). | `gemini` | Да |
| `GEMINI_API_KEY` | API-ключ Google Gemini. | `AIzaSy...` | Да (если `AI_PROVIDER=gemini`) |
| `GEMINI_MODEL` | Имя модели Google Gemini. | `gemini-2.5-flash` | Нет (по умолчанию: `gemini-2.5-flash`) |
| `OPENAI_API_KEY` | API-ключ OpenAI (или совместимый). | `sk-...` | Да (если `AI_PROVIDER=openai`) |
| `OPENAI_API_BASE` | Кастомный базовый URL для OpenAI-совместимых сервисов. | `https://generativelanguage.googleapis.com/v1beta/openai/` | Нет |
| `DEEPSEEK_API_KEY` | API-ключ DeepSeek. | `sk-...` | Да (если `AI_PROVIDER=deepseek`) |
| `GROQ_API_KEY` | API-ключ Groq. | `gsk-...` | Да (если `AI_PROVIDER=groq`) |
| `GROQ_MODEL` | Имя модели Groq. | `llama-3.3-70b-versatile` | Нет (по умолчанию: `llama-3.3-70b-versatile`) |
| `SECURE_SSL_REDIRECT` | Перенаправление всех HTTP-запросов на HTTPS. | `True` | Нет (по умолчанию: `False`) |

---

## 🤖 ИИ-агенты

OmniOS использует мультиагентную архитектуру для обработки сообщений гостей:

* **Router Agent (`router`)** — Входная точка. Анализирует сообщения гостей, определяет их намерение (intent) и перенаправляет диалог соответствующему агенту.
* **Booking Agent (`booking`)** — Собирает параметры бронирования (даты, количество человек, тип номера), проверяет доступность номеров и рассчитывает итоговую стоимость проживания по тарифам.
* **Consultant Agent (`consultant`)** — Отвечает на часто задаваемые вопросы (FAQ) об отеле, правилах отмены, услугах, питании и локации, используя плейбуки базы знаний.
* **Customer Service Agent (`cs`)** — Обрабатывает жалобы, отзывы и решает послепродажные вопросы клиентов.

---

## 🔗 Интеграции

Подключение внешних каналов коммуникации осуществляется через панель настроек CRM:

* **Telegram**: Создайте бота через `@BotFather` и скопируйте токен. Укажите ваш публичный HTTPS-адрес туннеля в переменной `APP_DOMAIN` в `.env`. Перейдите в раздел **Настройки -> Интеграции -> Telegram**, вставьте токен и нажмите кнопку регистрации вебхука.
* **WhatsApp и Instagram**: Интегрируются через Meta Business API. Введите необходимые учетные данные в разделе **Настройки -> Интеграции -> WhatsApp / Instagram**. Дополнительную информацию по получению токенов Meta см. во внутренних руководствах.

---

## ⚙️ Разработка без Docker

Инструкция для локального запуска сервисов напрямую на хост-компьютере:

### Требования
- Python 3.12+
- Node.js 20+
- PostgreSQL 16+
- Redis 7+

### 1. Подготовка базы данных
Убедитесь, что сервер PostgreSQL запущен, создайте пустую базу данных `app_dev` и импортируйте предустановленные плейбуки и структуру данных:
```bash
psql -h localhost -p 5432 -U postgres -d app_dev -f backend/import_data.sql
```

### 2. Настройка Backend-части
Создайте виртуальное окружение Python, установите зависимости, примените миграции и запустите сервер разработки Django:
```bash
cd backend
python -m venv .venv
source .venv/bin/activate  # На Windows: .venv\Scripts\Activate.ps1
pip install -r requirements.txt
python manage.py migrate
python manage.py runserver
```

### 3. Запуск Celery-воркеров и планировщика
Запустите обработчик задач в отдельном терминале с активированным виртуальным окружением.
* **Windows** (требуется библиотека `eventlet`):
  ```bash
  pip install eventlet
  celery -A config worker --loglevel=info -P eventlet
  celery -A config beat --loglevel=info
  ```
* **Linux / macOS**:
  ```bash
  celery -A config worker --loglevel=info
  celery -A config beat --loglevel=info
  ```

### 4. Настройка Frontend-части
Установите npm-зависимости и запустите Vite-сервер разработки:
```bash
cd web
npm install
npm run dev
```

---

## 📂 Структура проекта

```text
├── backend/            # Django API: apps/ (users, organizations, leads, flows, hotel_info, hotel_media, audit),
│                       # config/ (settings, Celery), фикстуры и медиа
├── web/                # Панель управления: React + TypeScript на Vite, Tailwind CSS, shadcn/ui
├── mobile/             # Мобильное приложение React Native (Expo) для менеджеров отеля
├── shared/             # Общие ресурсы и конфигурационные схемы между приложениями проекта
├── docs/               # Документация: деплой, безопасность, тестирование, гайды по интеграциям и агентам
├── scratch/            # Временные скрипты автоматизации разработчиков, дампы БД и логи проверок
├── nginx.conf          # Конфигурация Nginx для маршрутизации фронтенда и проксирования API
└── docker-compose.yml  # Файл конфигурации Docker Compose для быстрого локального развертывания
```

---

## 📄 Лицензия

Этот проект распространяется под лицензией [MIT](https://opensource.org/licenses/MIT).
