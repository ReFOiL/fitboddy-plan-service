from fastapi import HTTPException, status

from application.errors import ConflictError, IntegrationError, PlanError, PlanNotFoundError, TrainerExerciseNotFoundError, ValidationError


class ErrorTranslator:
    @staticmethod
    def raise_http_error(exc: PlanError) -> None:
        if isinstance(exc, PlanNotFoundError):
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
        if isinstance(exc, TrainerExerciseNotFoundError):
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
        if isinstance(exc, ConflictError):
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
        if isinstance(exc, ValidationError):
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc
        if isinstance(exc, IntegrationError):
            raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)) from exc
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
