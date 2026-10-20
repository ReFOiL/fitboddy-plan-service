# plan-service

Сервис генерации и хранения персональных тренировочных планов для marketplace-модели тренер-клиент.

## Stack

- FastAPI + Pydantic
- SQLAlchemy + Alembic
- Poetry
- Postgres (prod) / SQLite (tests)

## API

- `GET /health`
- `GET /ready`
- `POST /api/v1/plans/generate` - сгенерировать и сохранить активный 4-недельный план. Предыдущий активный план клиента архивируется вместе с ручными правками слотов
- `GET /api/v1/plans/users/{user_id}/active` - получить активный план пользователя
- `GET /api/v1/plans/clients/{client_user_id}/trainers/{trainer_user_id}/active` - активный план клиента у этого тренера (клиент и его тренер, только чтение для клиента)
- `POST /api/v1/plans/clients/{client_user_id}/trainers/{trainer_user_id}/active` - пустой план тренера, если активного ещё нет (`day_count: 0` — план без дней)
- `PUT /api/v1/plans/clients/{client_user_id}/trainers/{trainer_user_id}/days/{day_index}` - заменить слоты дня упорядоченным списком (пустой список очищает день)
- `POST /api/v1/plans/clients/{client_user_id}/trainers/{trainer_user_id}/days/{day_index}/exercises` - добавить слот в конец дня
- `PATCH /api/v1/plans/clients/{client_user_id}/trainers/{trainer_user_id}/days/{day_index}/exercises/{line_id}` - обновить дозировку слота
- `DELETE /api/v1/plans/clients/{client_user_id}/trainers/{trainer_user_id}/days/{day_index}/exercises/{line_id}` - удалить слот
- `PUT /api/v1/plans/clients/{client_user_id}/trainers/{trainer_user_id}/days/{day_index}/exercises/order` - переставить слоты дня
- `POST /api/v1/plans/clients/{client_user_id}/trainers/{trainer_user_id}/days` - добавить день в активный план (`week` + `day_of_week`, понедельник = 0)
- `DELETE /api/v1/plans/clients/{client_user_id}/trainers/{trainer_user_id}/days/{day_index}` - удалить день
- `PATCH /api/v1/plans/clients/{client_user_id}/trainers/{trainer_user_id}/days/{day_index}` - плановое время дня (`scheduled_time`, `HH:MM` или `null`)
- `POST /api/v1/plans/clients/{client_user_id}/trainers/{trainer_user_id}/days/{day_index}/copy` - скопировать день на неделю и день недели, создав цель если её нет
- `POST /api/v1/plans/clients/{client_user_id}/trainers/{trainer_user_id}/weeks/{week}/copy` - скопировать неделю на `target_week`
- `GET /api/v1/plans/{plan_id}/days/{day_index}` - получить конкретный день плана
- `GET /api/v1/trainers/{trainer_user_id}/exercises` - список упражнений тренера (`include_archived=true` для полного списка)
- `POST /api/v1/trainers/{trainer_user_id}/exercises` - добавить упражнение в каталог тренера (id генерируется на бэке)
- `GET /api/v1/trainers/{trainer_user_id}/exercises/{row_id}` - получить упражнение тренера (для клиента — просмотр деталей)
- `PUT /api/v1/trainers/{trainer_user_id}/exercises/{row_id}` - обновить упражнение тренера
- `POST /api/v1/trainers/{trainer_user_id}/exercises/{row_id}/archive` - архивировать упражнение (soft archive)
- `POST /api/v1/trainers/{trainer_user_id}/exercises/{row_id}/video` - загрузить видео упражнения (multipart `file`, `.mp4`/`.mov`, до 200MB). Роль `trainer`, упражнение принадлежит этому тренеру
- `DELETE /api/v1/trainers/{trainer_user_id}/exercises/{row_id}/video` - удалить видео упражнения
- `POST /api/v1/trainers/{trainer_user_id}/exercises/{row_id}/photos/{position}` - загрузить фото исходного (`start`) или конечного (`end`) положения (multipart `file`, `.jpg`/`.jpeg`/`.png`/`.webp`, до 15MB). Тип проверяется по сигнатуре файла, не только по расширению
- `DELETE /api/v1/trainers/{trainer_user_id}/exercises/{row_id}/photos/{position}` - удалить фото упражнения
- `GET /api/v1/platform-exercises` - активный каталог платформы (в том числе подписанные URL фото и видео)
- `POST /api/v1/admin/platform-exercises/{row_id}/video` - загрузить видео упражнения платформы (роль `platform_admin`, multipart `file`, `.mp4`/`.mov`, до 200MB)
- `DELETE /api/v1/admin/platform-exercises/{row_id}/video` - удалить видео упражнения платформы
- `POST /api/v1/admin/platform-exercises/{row_id}/photos/{position}` - загрузить фото `start` или `end` упражнения платформы (те же форматы и лимит 15MB)
- `DELETE /api/v1/admin/platform-exercises/{row_id}/photos/{position}` - удалить фото упражнения платформы
- `GET /api/v1/trainers/media/{object_key}?expires={unix}&signature={hex}` - отдача объекта из MinIO. Без валидной подписи ответ 403

## Медиа: контракт URL

В ответах API поля `start_image_url`, `end_image_url`, `video_url` и поле загрузки `image_url` / `video_url` — готовая строка для `<img src>` или `<video src>`. Заголовок `Authorization` на этот GET не нужен: фронтенд хранит значение как непрозрачный URL.

Форма:

```text
/api/v1/trainers/media/{object_key}?expires={unix_seconds}&signature={hmac_sha256_hex}
```

Подпись — HMAC-SHA256 от `"{expires}\n{object_key}"` ключом `MEDIA_URL_SIGNING_SECRET`. Просроченные, без подписи и с неверной подписью запросы отклоняются (403). В БД лежит ключ объекта (`photos/...` или `videos/...`), а не подписанный URL; подпись собирается в момент ответа.

Клон каталога копирует объекты в префикс тренера (`photos/{trainer_user_id}/...`, `videos/{trainer_user_id}/...`). Удаление возможно только из своего префикса и только если на ключ больше никто не ссылается, поэтому уже склонированные строки со старым общим ключом не теряют файл, если платформа или другой тренер меняет своё фото.

Ключ MinIO сервиса рассчитан только на `get`/`put`/`delete` внутри `photos/*` и `videos/*`. Сервис не создаёт бакет и не листит его: бакет готовит инфраструктура.

Ответ медиа содержит `X-Content-Type-Options: nosniff`, `ETag` и `Cache-Control: private, max-age=<остаток TTL>`.

Переменные окружения, которые должна выставить инфраструктура:

| Переменная | Назначение |
| --- | --- |
| `MEDIA_URL_SIGNING_SECRET` | Обязательный секрет HMAC. Пустое значение запрещает выдачу и скачивание медиа |
| `MEDIA_URL_TTL_SECONDS` | Время жизни подписи в секундах. В инфраструктуре пример — `300`; если переменная не задана, сервис берёт 300 |
| `S3_MEDIA_ENABLED` | `true`, чтобы включить MinIO |
| `S3_ENDPOINT`, `S3_ACCESS_KEY`, `S3_SECRET_KEY`, `S3_BUCKET`, `S3_SECURE` | Подключение к бакету. Ключ — только `photos/*` и `videos/*` |
| `S3_MAX_PHOTO_BYTES` | Лимит фото, по умолчанию 15MB (шлюз может отсечь тело раньше, около 16MB) |
| `S3_MAX_VIDEO_BYTES` | Лимит видео, по умолчанию 200MB |

## Ручное редактирование

Генерация — необязательное заполнение черновика из каталога и правил. Тренер правит уже активный план сам: слот ссылается на `trainer_exercises.row_id` (в плане это поле `exercise_id`). Название и дозировка копируются в слот в момент добавления. Позже изменение каталога план не пересобирает.

`POST /api/v1/plans/generate` архивирует текущий активный план и пишет новый. Ручные правки сохраняются до следующей генерации и в новый план не переносятся.

Менять план может активный тренер клиента (`role=trainer`) и `platform_admin`. Клиент эти же URL читает (`GET`), мутации получают 403. Пустой день и план без упражнений допустимы.

`day_index` уже созданных дней при добавлении и удалении не перенумеровывается. Новый день получает следующий свободный номер. Календарный порядок — по `scheduled_for`. Неделя 1 — это семь дней от `start_date`, не календарный понедельник: внутри окна каждый `day_of_week` (понедельник = 0) встречается один раз.

Заменить день:

```json
PUT /api/v1/plans/clients/{client_user_id}/trainers/{trainer_user_id}/days/1
{
  "slots": [
    {
      "exercise_id": "trainer-exercise-row-id",
      "sets": 4,
      "reps": 8,
      "rest_seconds": 90,
      "weight_kg": 40
    }
  ]
}
```

Пустой день: `{ "slots": [] }`.

Добавить слот:

```json
POST .../days/1/exercises
{ "exercise_id": "trainer-exercise-row-id", "sets": 3, "reps": 10, "weight_kg": 12.5 }
```

Обновить дозировку (непереданные поля не меняются; `weight_kg: null` сбрасывает вес):

```json
PATCH .../days/1/exercises/{line_id}
{ "sets": 5, "reps": 6, "rest_seconds": 120, "weight_kg": 50 }
```

Порядок — полный список `line_id` дня:

```json
PUT .../days/1/exercises/order
{ "line_ids": ["line-b", "line-a"] }
```

Пустой план:

```json
POST /api/v1/plans/clients/{client_user_id}/trainers/{trainer_user_id}/active
{ "goal": "maintenance", "level": "intermediate", "workouts_per_week": 3, "day_count": 0 }
```

`day_count` от 1 до 28 создаёт пустые дни подряд от `start_date` (или от сегодня) и только в момент создания пустого плана. Если активный план уже есть, ответ 409: чтобы заменить его черновиком из каталога, нужен `POST /api/v1/plans/generate`. День в уже существующий план добавляется отдельным запросом.

Добавить день (201, тело — весь план):

```json
POST /api/v1/plans/clients/{client_user_id}/trainers/{trainer_user_id}/days
{ "week": 1, "day_of_week": 3, "scheduled_time": "18:00" }
```

`scheduled_time` необязателен. Повтор того же `week` + `day_of_week` — 409. Больше 28 дней в плане — 422.

Удалить день (200, тело — весь план; слоты дня удаляются вместе с ним):

```text
DELETE /api/v1/plans/clients/{client_user_id}/trainers/{trainer_user_id}/days/{day_index}
```

`start_date` при этом не сдвигается: это якорь недель. `end_date` становится максимальной оставшейся датой или `start_date`, если дней не осталось.

Плановое время (200, тело — день). Поле в теле обязательно; `null` сбрасывает:

```json
PATCH /api/v1/plans/clients/{client_user_id}/trainers/{trainer_user_id}/days/1
{ "scheduled_time": "18:00" }
```

В ответах дня и тренировки на сегодня `scheduled_time` — строка `HH:MM` или `null`.

Заметка слота (`note`, до 500 символов, пустая строка хранится как `null`). Её можно передать при создании слота и при замене дня. В `PATCH` пропущенное поле не меняется, `null` стирает. Заметка возвращается в слоте плана.

```json
POST .../days/1/exercises
{ "exercise_id": "trainer-exercise-row-id", "sets": 3, "reps": 10, "note": "медленно вниз" }

PATCH .../days/1/exercises/{line_id}
{ "note": null }
```

Копирование дня (200, тело — весь план). Цель — `week` + `day_of_week`. Если такого дня нет, он создаётся. `mode`: `overwrite` (по умолчанию) заменяет слоты, `append` дописывает в конец. У нового дня `scheduled_time` и `volume_multiplier` берутся из источника. Уже существующий день своё `scheduled_time` сохраняет. Отметки выполнения не копируются. Копия слота получает новый `line_id` и ту же заметку.

```json
POST .../days/1/copy
{ "week": 2, "day_of_week": 0, "mode": "append" }
```

Копирование недели копирует каждый день источника на тот же `day_of_week` целевой недели и тоже создаёт недостающие дни. Лишние дни цели, которых нет в источнике, не удаляются.

```json
POST .../weeks/1/copy
{ "target_week": 3, "mode": "overwrite" }
```

Та же неделя, копирование дня на себя, больше 24 слотов после `append` и больше 28 дней — 422.

Завершение тренировки по-прежнему `POST /api/v1/plans/me/days/{day_index}/complete`. Тело необязательно. `completed_at` и `finished_at` ставятся сервером в момент вызова и совпадают. `started_at` записывается, только если клиент его прислал, и не может быть позже финиша или раньше него больше чем на 7 суток. Повторное завершение — 409.

```json
POST /api/v1/plans/me/days/1/complete
{ "started_at": "2026-10-20T18:02:00Z" }
```

## Уведомления

Три события, короткие сообщения на русском, доставка в Telegram:

- клиенту в день тренировки: за `NOTIFICATIONS_REMINDER_LEAD_MINUTES` (по умолчанию 2 часа) до `scheduled_time`, а если времени нет — в `NOTIFICATIONS_MORNING_REMINDER` (по умолчанию 09:00) местного пояса;
- тренеру, если день прошёл без `is_completed`. С `scheduled_time` дедлайн — это местное время, без него — полночь следующего дня. Смотрим назад не дальше `NOTIFICATIONS_MISSED_LOOKBACK_DAYS`;
- клиенту, когда тренер создал или изменил план. Правки слотов не шлют сообщение каждая: они сдвигают одну отложенную запись на `NOTIFICATIONS_PLAN_DEBOUNCE_SECONDS` (по умолчанию 15 минут). Завершение тренировки клиентом сюда не входит.

`scheduled_time` — колонка из PR #5 (`0021_plan_notes_times`). Эта ветка собрана поверх неё.

Пояс клиента: `notification_preferences.timezone`, иначе `NOTIFICATIONS_DEFAULT_TIMEZONE` (`Asia/Vladivostok`). Отключение — `notifications_enabled: false` на пользователя, на все три события. Повторная отправка того же события не проходит: ключ доставки уникален. Нет чата или токена — событие остаётся до конца окна (для плана — до `NOTIFICATIONS_PLAN_NOTICE_TTL_SECONDS`), затем помечается как пропущенное.

В платформе Telegram ни к кому не привязан. `fitboddy_tgbot` — отдельный контур, там `users.telegram_id` и есть сам пользователь, кода привязки нет. Здесь привязка такая:

1. `POST /api/v1/plans/me/notifications/telegram/link-code` — код для вошедшего пользователя.
2. Бот (его ещё нет в `fitboddy_tgbot`) вызывает `POST /api/v1/plans/internal/notifications/telegram` с заголовком `X-Service-Token: $INTERNAL_SERVICE_TOKEN` и телом `{ "code": "...", "chat_id": 123 }`.
3. `DELETE /api/v1/plans/me/notifications/telegram` снимает чат.
4. `GET` и `PUT /api/v1/plans/me/notifications/settings` — пояс и `notifications_enabled`. `timezone: null` возвращает пояс по умолчанию. `chat_id` в ответе нет, только `telegram_linked`.

Пути под `/api/v1/plans`, их уже проксирует шлюз. Внутренний confirm тоже попадает под этот префикс, пока в `api_locations.inc` нет более длинного запрета:

```nginx
location ^~ /api/v1/plans/internal {
    default_type application/json;
    return 403 '{"detail":"internal endpoint is not exposed"}';
}
```

Его нужно поставить рядом с остальными internal-запретами. До этого ручку закрывает только `INTERNAL_SERVICE_TOKEN` (пустое значение отклоняет вызов).

Планировщик — APScheduler. В процессе API он выключен (`NOTIFICATIONS_SCHEDULER_ENABLED=false`), чтобы не дублировать воркер. Отдельный контейнер того же образа:

```yaml
plan-notifications:
  build:
    context: ../fitboddy-plan-service
  command: ["python", "-m", "presentation.notifications.worker"]
  environment:
    PYTHONPATH: /app/lib
    DATABASE_URL: postgresql+psycopg://${POSTGRES_USER:-fitboddy}:${POSTGRES_PASSWORD:-fitboddy_local_dev}@postgres:5432/fitboddy_plan
    AUTH_SERVICE_URL: http://auth-service:8000
    TELEGRAM_BOT_TOKEN: ${TELEGRAM_BOT_TOKEN:-}
    NOTIFICATIONS_DEFAULT_TIMEZONE: ${NOTIFICATIONS_DEFAULT_TIMEZONE:-Asia/Vladivostok}
    NOTIFICATIONS_MORNING_REMINDER: ${NOTIFICATIONS_MORNING_REMINDER:-09:00}
    NOTIFICATIONS_REMINDER_LEAD_MINUTES: ${NOTIFICATIONS_REMINDER_LEAD_MINUTES:-120}
    NOTIFICATIONS_PLAN_DEBOUNCE_SECONDS: ${NOTIFICATIONS_PLAN_DEBOUNCE_SECONDS:-900}
    NOTIFICATIONS_MISSED_LOOKBACK_DAYS: ${NOTIFICATIONS_MISSED_LOOKBACK_DAYS:-2}
    NOTIFICATIONS_POLL_SECONDS: ${NOTIFICATIONS_POLL_SECONDS:-60}
    INTERNAL_SERVICE_TOKEN: ${INTERNAL_SERVICE_TOKEN:-fitboddy_internal_dev}
  depends_on:
    postgres:
      condition: service_healthy
  restart: unless-stopped
```

Образ `ghcr` подставляется так же, как у `plan-service` в `docker-compose.ghcr.yml`. Репозиторий `fitboddy-infra-docker` этим агентом не пишется: сервис нужно добавить там. Пока контейнера нет, на самом `plan-service` можно выставить `NOTIFICATIONS_SCHEDULER_ENABLED=true` — идемпотентность не даст второму процессу послать то же событие ещё раз.

Без `TELEGRAM_BOT_TOKEN` воркер жив, но ничего не отправляет.

| Переменная | Назначение |
| --- | --- |
| `TELEGRAM_BOT_TOKEN` | Токен Bot API. Пустой — доставка выключена |
| `TELEGRAM_API_BASE` | По умолчанию `https://api.telegram.org` |
| `NOTIFICATIONS_SCHEDULER_ENABLED` | `true` только у процесса, который тикает. У API оставьте `false`, если есть воркер |
| `NOTIFICATIONS_POLL_SECONDS` | Период тика, по умолчанию 60 |
| `NOTIFICATIONS_DEFAULT_TIMEZONE` | IANA-пояс, если у пользователя свой не записан. По умолчанию `Asia/Vladivostok` |
| `NOTIFICATIONS_MORNING_REMINDER` | `HH:MM` местного времени, если у дня нет `scheduled_time` |
| `NOTIFICATIONS_REMINDER_LEAD_MINUTES` | За сколько минут до `scheduled_time` писать клиенту |
| `NOTIFICATIONS_PLAN_DEBOUNCE_SECONDS` | Пауза после последней правки плана |
| `NOTIFICATIONS_PLAN_NOTICE_TTL_SECONDS` | Сколько ждать чат для сообщения о плане |
| `NOTIFICATIONS_MISSED_LOOKBACK_DAYS` | Сколько дней после дедлайна ещё сообщать о пропуске |
| `NOTIFICATIONS_LINK_CODE_TTL_SECONDS` | Срок кода привязки Telegram |
| `INTERNAL_SERVICE_TOKEN` | Уже есть у сервисов. Им бот подтверждает код |
| `AUTH_SERVICE_URL` | Необязательный логин клиента в тексте о пропуске (`POST /api/v1/auth/internal/summaries`) |

## Поиск клиента по логину

Логины хранит `fitboddy-auth-service` (`auth_users.login`), не plan-service. Уже есть внутренний `POST /api/v1/auth/internal/summaries` (id → login) и админский `GET /api/v1/admin/users?q=` (только `platform_admin`, в ответе есть email). Тренеру этого мало: приглашение в `fitboddy-tenant-service` принимает `client_user_id`.

Нужный эндпоинт в auth-service, на том же префиксе, который шлюз уже отдаёт фронту:

`GET /api/v1/auth/clients/by-login?login={login}`

- `Authorization: Bearer`, роль `trainer` или `platform_admin`. Иначе 403.
- `login` — точное совпадение после `trim` и lower-case, формат `^[a-z0-9_.-]{3,32}$`. Не подстрока и не список пользователей.
- 200: `{ "user_id": "...", "login": "client.login", "role": "client" }`. Email не возвращать.
- 404 с одним и тем же текстом, если логина нет, пользователь неактивен или роль не `client`.
- Дальше фронт как и раньше вызывает `POST /api/v1/marketplace/relations` с этим `user_id`, `trainer_user_id` и `mode: "invite"`.

Куда вставить вызов в PR фронта: поле в `src/components/trainer/InviteClientSheet.tsx` (сейчас это id из профиля), функция в `src/api/auth.ts` рядом с `/api/v1/auth/me`. `onInvite` по-прежнему получает `user_id`. Эндпоинт принадлежит auth-service; из plan-service PR туда не открывается.

## Алгоритм

Сервис использует адаптированную логику из `tg_bot`:
- каталоговый матчинг упражнений по профилю (goal/level/location/equipment); сложность каталога — шкала 1–5 с потолком beginner ≤ 2, intermediate ≤ 4, advanced ≤ 5,
- диверсификацию по категориям и novelty penalty,
- построение 4-недельного расписания с weekly pattern и объемом по неделям.

Каталог упражнений привязан к тренеру:
- в `POST /api/v1/plans/generate` передаётся `trainer_user_id`;
- для нового тренера автоматически создаётся базовый набор упражнений;
- дальше генерация клиента использует каталог именно этого тренера.

План — снимок каталога на момент `POST /api/v1/plans/generate`. Упражнения, добавленные или изменённые позже, попадают клиенту только после повторной генерации. Сервис сам активные планы не пересобирает.

Структура алгоритмической части:
- `lib/application/generation/contracts.py` — абстракции (provider/matching/scheduling);
- `lib/application/generation/providers/*` — источники каталога;
- `lib/application/generation/calculators/*` — отдельные калькуляторы.
- `lib/application/generation/orchestrator.py` — orchestration pipeline и единая точка сборки генерации.
- `lib/application/generation/factory.py` — сборка default pipeline для runtime/DI.

## Local run

```bash
poetry install
poetry run alembic upgrade head
poetry run uvicorn --app-dir lib presentation.http.main:app --reload --port 8000
```

## Tests

```bash
poetry run pytest tests/unit -q
```
