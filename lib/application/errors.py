class PlanError(Exception):
    pass


class ValidationError(PlanError):
    pass


class UnauthorizedError(PlanError):
    pass


class ForbiddenError(PlanError):
    pass


class PlanNotFoundError(PlanError):
    pass


class TrainerExerciseNotFoundError(PlanError):
    pass


class PlatformExerciseNotFoundError(PlanError):
    pass


class ConflictError(PlanError):
    pass


class IntegrationError(PlanError):
    pass
