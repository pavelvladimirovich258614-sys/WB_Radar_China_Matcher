# WB Radar & China Matcher

Десктоп-приложение для поставщиков и селлеров Wildberries:

- **Матчер China** — поиск 1:1 товара WB на китайских площадках (Alibaba, 1688, Taobao) и извлечение полочного видео.
- **Разведка WB** — поиск вирусных товаров по нише, сбор отзывов, VoC-анализ (боли/желания/страхи), генерация хуков и скачивание видео из отзывов.
- **Настройки** — выбор LLM-провайдера, proxy, папок output/sessions, статус сессий.

## Установка

```bash
# Windows (PowerShell)
.\init.sh

# Или вручную
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
playwright install chromium
```

Скопируйте `.env.example` в `.env` и заполните ключи:

```env
OPENROUTER_API_KEY=sk-...
ZAI_API_KEY=...
GROQ_API_KEY=...
OLLAMA_BASE_URL=http://localhost:11434
```

## Запуск

```bash
.venv\Scripts\python.exe run.py
```

## Тесты

### Обычные тесты

Запускаются без сети, без реального браузера и без реального LLM. Используют
сохранённые фикстуры и fake-сервисы.

```bash
.venv\Scripts\python.exe -m pytest -m "not live" -q
```

### Live smoke tests

Live-тесты помечены `@pytest.mark.live` и требуют явного ENV-флага. Они могут
обращаться к реальным публичным эндпоинтам WB и китайским площадкам. WB/China
могут возвращать 403 или показывать капчу — это **известное ограничение**,
обход защит не производится.

```bash
# PowerShell
$env:WB_RADAR_RUN_LIVE = "1"
.venv\Scripts\python.exe -m pytest -m live -q

# CMD
set WB_RADAR_RUN_LIVE=1
.venv\Scripts\python.exe -m pytest -m live -q
```

Live-тесты:

- `tests/test_e2e.py::test_live_wb_to_discovery_smoke` — базовая проверка
  реального WB discovery;
- `tests/test_e2e.py::test_live_matcher_one_product_smoke` — placeholder для
  ручного сквозного прогона матчера (требует сессий и ключей).

### Первый ручной прогон (опционально)

1. Заполните `.env`.
2. При необходимости создайте сессии через `core.browser.BrowserManager.manual_login()`.
3. Запустите live-тесты и проверьте, что сеть не блокирует запросы.
4. Если видите капчу/403 — см. AGENTS.md, стоп-правила.

## Структура проекта

```
core/      — конфиг, модели, WB-клиент, браузер, LLM, storage
matcher/   — поиск по фото на китайских площадках, ранкер, извлечение видео
harvest/   — разведка WB: вирусные товары, отзывы, VoC, хуки, видео, скачивание
gui/       — Flet-интерфейс, 3 вкладки
tests/     — unit, integration, e2e и live smoke tests
fixtures/  — сохранённые фикстуры ответов
```

## Сборка Windows .exe

Для сборки desktop `.exe` используется PyInstaller. В `.exe` не включаются
секреты и временные данные — приложение читает `.env` / `.env.local` и
создаёт `sessions/` / `output/` рядом с собранным файлом.

### Требования

- Windows 10/11
- Python 3.11+
- Git-репозиторий с настроенным `.venv`

### Команда сборки

```powershell
# PowerShell (из корня репозитория)
powershell -ExecutionPolicy Bypass -File scripts\build_windows.ps1

# Без запуска тестов перед сборкой
powershell -ExecutionPolicy Bypass -File scripts\build_windows.ps1 -SkipTests

# Одним файлом
powershell -ExecutionPolicy Bypass -File scripts\build_windows.ps1 -OneFile
```

Скрипт:

1. Проверяет `.venv`.
2. Устанавливает `pyinstaller`.
3. Запускает `pytest -m "not live" -q` (если не передан `-SkipTests`).
4. Собирает `.exe` в `dist/WB_Radar_China_Matcher/`.
5. Копирует `.env.example` рядом с `.exe`.

### Результат

- По умолчанию: `dist/WB_Radar_China_Matcher/WB_Radar_China_Matcher.exe`
- С `-OneFile`: `dist/WB_Radar_China_Matcher.exe`

После первого запуска приложение создаст рядом с `.exe` папки `sessions/`
и `output/` (если их нет), а ключи и сессии пользователь заполняет сам.

### Известные ограничения

- Сборка на Linux/Mac требует Wine/CrossOver и не покрывается этим скриптом.
- Первый запуск может потребовать `playwright install chromium` или наличия
  Chromium в `sessions/` / в системе.
- WB/China могут давать 403/капчу — защиту не обходить, см. AGENTS.md.

## Безопасность и границы

- Не обходим капчи/антибот/WAF.
- Публичные эндпоинты WB используются с rate-limit и ретраями.
- Чужие видеоотзывы не перезаливаются 1:1 — используются как референс/материал.
- API-ключи и сессии хранятся только в `.env` / `.env.local` / `sessions/` и
  не коммитятся.
