class SolarPumpBaseError(Exception):
    """Root exception for all application errors."""


class DataNotFoundError(SolarPumpBaseError):
    """Raised when a requested record does not exist in the dataset."""


class DataLoadError(SolarPumpBaseError):
    """Raised when a dataset fails to load from disk."""


class CalculationError(SolarPumpBaseError):
    """Raised when an engineering calculation produces an invalid result."""


class InsufficientDataError(SolarPumpBaseError):
    """Raised when input data is insufficient to complete a calculation."""
