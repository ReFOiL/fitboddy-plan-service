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
- `POST /api/v1/plans/generate` - сгенерировать и сохранить активный 4-недельный план
- `GET /api/v1/plans/users/{user_id}/active` - получить активный план пользователя
- `GET /api/v1/plans/{plan_id}/days/{day_index}` - получить конкретный день плана
- `GET /api/v1/trainers/{trainer_user_id}/exercises` - список упражнений тренера (`include_archived=true` для полного списка)
- `POST /api/v1/trainers/{trainer_user_id}/exercises/{exercise_id}` - добавить упражнение в каталог тренера
- `PUT /api/v1/trainers/{trainer_user_id}/exercises/{exercise_id}` - обновить упражнение тренера
- `POST /api/v1/trainers/{trainer_user_id}/exercises/{exercise_id}/archive` - архивировать упражнение (soft archive)

## Алгоритм

Сервис использует адаптированную логику из `tg_bot`:
- каталоговый матчинг упражнений по профилю (goal/level/location/equipment),
- диверсификацию по категориям и novelty penalty,
- построение 4-недельного расписания с weekly pattern и объемом по неделям.

Каталог упражнений привязан к тренеру:
- в `POST /api/v1/plans/generate` передаётся `trainer_user_id`;
- для нового тренера автоматически создаётся базовый набор упражнений;
- дальше генерация клиента использует каталог именно этого тренера.

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
