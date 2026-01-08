# Prime Parser - PDF Hydropower Report Parser

Микросервис для парсинга PDF отчетов гидроэлектростанций Узбекистана и отправки данных на внешний сервис.

## Описание

Prime Parser принимает POST запрос с PDF файлом, извлекает данные (дата отчета и суммарная выработка энергии), и отправляет обработанные данные на внешний API с X-API-Key аутентификацией.

### Основные возможности

- ✅ HTTP API для приема PDF файлов (FastAPI)
- ✅ Парсинг таблиц из PDF (pdfplumber)
- ✅ Извлечение даты из формата "8.01.2026 й."
- ✅ Извлечение суммарной выработки энергии
- ✅ Аутентификация через X-API-Key (входящие запросы)
- ✅ Отправка данных POST запросом с X-API-Key (исходящие запросы)
- ✅ Retry с exponential backoff
- ✅ Структурное логирование (structlog)
- ✅ Два конфига (dev/prod)
- ✅ Docker контейнеризация

## Архитектура

```
Клиент → POST /api/v1/parse-pdf (PDF + X-API-Key) →
→ FastAPI → PDF Parser (pdfplumber) →
→ HTTP Client (retry + X-API-Key) → Внешний API →
→ Response
```

## Требования

- Python 3.14+
- Docker (для контейнеризации)

## Установка

### Локальная установка

1. Клонировать репозиторий:
```bash
git clone <repository-url>
cd prime-parser
```

2. Создать виртуальное окружение:
```bash
python -m venv .venv
# Windows
.venv\Scripts\activate
# Linux/Mac
source .venv/bin/activate
```

3. Установить зависимости:
```bash
make install
# или
pip install -e ".[dev]"
```

4. Настроить environment variables:
```bash
cp .env .env
# Отредактировать .env файл с вашими ключами
```

### Docker установка

```bash
# Собрать образ
make docker-build

# Или вручную
docker build -f docker/Dockerfile -t prime-parser:latest .
```

## Конфигурация

Сервис использует YAML конфигурационные файлы с поддержкой environment variables.

### config/dev.yaml
```yaml
environment: development
api:
  port: 19779
  incoming_api_key: "${DEV_API_KEY:-dev-secret-key}"
logging:
  level: DEBUG
forwarding:
  endpoint: "${DEV_ENDPOINT:-http://localhost:8080/api/data}"
  api_key: "${DEV_OUTGOING_API_KEY:-outgoing-key}"
  timeout: 30
  retry:
    max_attempts: 3
    backoff_factor: 2
    max_delay: 60
```

### config/prod.yaml
```yaml
environment: production
api:
  port: 19779
  incoming_api_key: "${PROD_API_KEY}"
logging:
  level: INFO
forwarding:
  endpoint: "${PROD_ENDPOINT}"
  api_key: "${PROD_OUTGOING_API_KEY}"
  timeout: 60
  retry:
    max_attempts: 5
    backoff_factor: 2
    max_delay: 120
```

### Environment Variables

Создайте `.env` файл на основе `.env.example`:

```bash
# Выбор окружения
ENVIRONMENT=dev

# Development
DEV_API_KEY=your-dev-incoming-api-key
DEV_ENDPOINT=http://localhost:8080/api/data
DEV_OUTGOING_API_KEY=your-dev-outgoing-key

# Production
PROD_API_KEY=your-prod-incoming-api-key
PROD_ENDPOINT=https://prod-api.example.com/api/data
PROD_OUTGOING_API_KEY=your-prod-outgoing-key
```

## Использование

### Локальный запуск

#### Development mode
```bash
make run-dev
# или
set ENVIRONMENT=dev && uvicorn src.prime_parser.main:app --reload --port 19779
```

#### Production mode
```bash
make run-prod
# или
set ENVIRONMENT=prod && uvicorn src.prime_parser.main:app --host 0.0.0.0 --port 19779
```

### Docker запуск

#### Development
```bash
make docker-run-dev
# или
docker run -p 19779:19779 -e ENVIRONMENT=dev prime-parser:latest
```

#### Production
```bash
make docker-run-prod
# или
docker run -p 19779:19779 \
  -e ENVIRONMENT=prod \
  -e PROD_API_KEY=your-key \
  -e PROD_ENDPOINT=https://api.example.com \
  -e PROD_OUTGOING_API_KEY=your-outgoing-key \
  prime-parser:latest
```

## API Endpoints

### POST /api/v1/parse-pdf

Парсит PDF файл и отправляет данные на внешний сервис.

**Request:**
- Headers: `X-API-Key: <incoming-api-key>`
- Body: `multipart/form-data` с PDF файлом
- Max file size: 10MB

**Example (curl):**
```bash
curl -X POST http://localhost:19779/api/v1/parse-pdf \
  -H "X-API-Key: dev-secret-key" \
  -F "file=@template/ges-svod.pdf"
```

**Response (success):**
```json
{
  "status": "success",
  "message": "PDF parsed and data forwarded successfully",
  "data": {
    "date": "2026-01-08",
    "total_energy_production": 81.03
  },
  "forward_response": {
    "status": "ok"
  }
}
```

**Response (error):**
```json
{
  "detail": "PDF parsing failed: Date not found in PDF"
}
```

### GET /api/v1/health

Health check endpoint.

**Example:**
```bash
curl http://localhost:19779/api/v1/health
```

**Response:**
```json
{
  "status": "healthy",
  "service": "prime-parser",
  "version": "1.0.0"
}
```

### GET /

Root endpoint (service info).

**Response:**
```json
{
  "service": "prime-parser",
  "status": "running",
  "version": "1.0.0"
}
```

## Разработка

### Makefile команды

```bash
make help          # Показать все доступные команды
make install       # Установить зависимости
make test          # Запустить тесты с coverage
make lint          # Проверить код (ruff + mypy)
make format        # Отформатировать код (black + ruff)
make run-dev       # Запустить dev server
make run-prod      # Запустить prod server
make docker-build  # Собрать Docker образ
make clean         # Очистить временные файлы
```

### Тестирование

```bash
# Запустить все тесты
make test

# Запустить конкретный тест
pytest tests/test_core/test_pdf_parser.py -v

# Запустить с coverage отчетом
pytest tests/ --cov=src/prime_parser --cov-report=html
```

### Линтинг и форматирование

```bash
# Проверить код
make lint

# Отформатировать код
make format
```

## Структура проекта

```
prime-parser/
├── src/prime_parser/          # Исходный код
│   ├── api/                   # API слой (routes, dependencies)
│   ├── core/                  # Бизнес-логика (PDF parser)
│   ├── clients/               # HTTP client для отправки данных
│   ├── models/                # Data models (Pydantic)
│   ├── config/                # Configuration management
│   ├── utils/                 # Утилиты (retry, exceptions)
│   └── main.py                # FastAPI application
├── config/                    # Конфигурационные файлы
│   ├── dev.yaml
│   └── prod.yaml
├── docker/                    # Docker files
│   ├── Dockerfile
│   └── .dockerignore
├── tests/                     # Тесты
│   ├── test_api/
│   ├── test_core/
│   └── test_clients/
├── template/                  # Пример PDF файла
│   └── ges-svod.pdf
├── pyproject.toml            # Зависимости и настройки
├── Makefile                  # Команды для разработки
├── .env.example              # Пример environment variables
└── README.md                 # Эта документация
```

## Особенности парсинга

### Извлечение даты

Дата извлекается из формата `"8.01.2026 й."` с помощью regex:
```python
DATE_PATTERN = r'(\d{1,2})\.(\d{2})\.(\d{4})\s*й\.'
```

### Извлечение суммарной энергии

Ищется строка таблицы с идентификатором `"Ўзбекгидроэнерго" АЖ бўйича` и из нее извлекается значение суммарной выработки энергии в млн. кВт⋅ч.

### Обработка PDF

- Используется `pdfplumber` для извлечения таблиц
- Поддержка многостраничных PDF
- Поддержка узбекского кириллического текста (UTF-8)
- Автоматическое удаление временных файлов после обработки

## Безопасность

- ✅ API Key аутентификация (входящие и исходящие запросы)
- ✅ Валидация типа файла (.pdf only)
- ✅ Ограничение размера файла (10MB)
- ✅ Немедленное удаление временных файлов
- ✅ Non-root user в Docker контейнере
- ✅ Secrets через environment variables
- ✅ Timeout для всех HTTP запросов
- ✅ Структурное логирование (без секретов)

## Мониторинг и логирование

Сервис использует **structlog** для структурного JSON логирования:

```json
{
  "event": "pdf_parsed_successfully",
  "timestamp": "2026-01-08T10:30:45.123Z",
  "level": "info",
  "request_id": "123456",
  "date": "2026-01-08",
  "total_energy": "81.03"
}
```

### Уровни логирования

- **DEV**: DEBUG (детальные логи)
- **PROD**: INFO (только важные события)

## Troubleshooting

### Проблема: "Configuration file not found"
**Решение:** Убедитесь, что файлы `config/dev.yaml` и `config/prod.yaml` существуют и переменная `ENVIRONMENT` установлена правильно.

### Проблема: "Invalid API key"
**Решение:** Проверьте, что X-API-Key в запросе совпадает с `incoming_api_key` в конфигурации.

### Проблема: "Date not found in PDF"
**Решение:** Убедитесь, что PDF содержит дату в формате "8.01.2026 й." Проверьте логи для деталей.

### Проблема: "Failed to forward data"
**Решение:** Проверьте:
- Доступность внешнего API endpoint
- Правильность `OUTGOING_API_KEY`
- Настройки timeout и retry в конфигурации

## Лицензия

[Укажите вашу лицензию]

## Контакты

[Укажите контактную информацию]
