"""Database exceptions exposed by SmartSpend."""


class SmartSpendDatabaseError(RuntimeError):
    """Base exception for database failures."""


class DatabaseConnectionError(SmartSpendDatabaseError):
    """Raised when a database connection cannot be opened or configured."""


class DatabaseIntegrityError(SmartSpendDatabaseError):
    """Raised when a database constraint rejects an operation."""


class DatabaseOperationError(SmartSpendDatabaseError):
    """Raised when SQLite cannot complete a database operation."""


class DatabaseVersionError(SmartSpendDatabaseError):
    """Raised when a database schema is newer than this application supports."""


class RecordNotFoundError(SmartSpendDatabaseError):
    """Raised when an update or deletion targets a missing record."""
