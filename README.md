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

Менять план может только активный тренер клиента (`role=trainer`). Клиент эти же URL читает (`GET`), мутации получают 403. Пустой день и план без упражнений допустимы.

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

`day_count` от 1 до 28 создаёт пустые дни подряд от `start_date` (или от сегодня). Если активный план уже есть, ответ 409: чтобы заменить его черновиком из каталога, нужен `POST /api/v1/plans/generate`.

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
