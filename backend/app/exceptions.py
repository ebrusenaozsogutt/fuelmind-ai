"""Domain exceptions raised by the service layer."""


class FuelMindError(Exception):
    """Base class for expected domain failures."""


class NotFoundError(FuelMindError):
    """Raised when a requested resource does not exist."""


class ConflictError(FuelMindError):
    """Raised when a uniqueness rule is violated."""


class BusinessRuleError(FuelMindError):
    """Raised when a domain invariant is violated."""


class AuthenticationError(FuelMindError):
    """Raised when authentication fails."""


class AuthorizationError(FuelMindError):
    """Raised when an authenticated user lacks permission."""
