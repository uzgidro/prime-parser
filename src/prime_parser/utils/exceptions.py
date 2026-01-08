"""Custom exceptions for the PDF parser service."""


class PrimeParserException(Exception):
    """Base exception for all application errors."""

    pass


class PDFParsingError(PrimeParserException):
    """PDF parsing failed."""

    pass


class DataExtractionError(PrimeParserException):
    """Could not extract required data from PDF."""

    pass


class ForwardingError(PrimeParserException):
    """Failed to forward data to external service."""

    pass


class AuthenticationError(PrimeParserException):
    """API key validation failed."""

    pass


class ConfigurationError(PrimeParserException):
    """Configuration error."""

    pass
