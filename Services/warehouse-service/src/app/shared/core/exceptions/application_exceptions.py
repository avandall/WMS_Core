"""Core application and infrastructure exceptions.

This module contains all exceptions related to application orchestration,
infrastructure concerns, API handling, and configuration.
"""

from __future__ import annotations

from typing import Any, Optional


# Base Application Exception
class ApplicationException(Exception):
    """Base class for application layer exceptions."""
    
    def __init__(self, message: str, details: Optional[dict] = None):
        super().__init__(message)
        self.message = message
        self.details = details or {}


class ApplicationError(ApplicationException):
    """General application error for unexpected conditions."""


class UseCaseError(ApplicationException):
    """Raised when a use case cannot be executed."""


class InvalidOperationError(ApplicationException):
    """Raised when an operation is invalid in the current context."""


# Report and Analytics Exceptions
class ReportGenerationError(ApplicationError):
    """Raised when there is an error generating a report."""


class InvalidReportParametersError(ApplicationException):
    """Raised when invalid parameters are provided for report generation."""


class AnalyticsError(ApplicationError):
    """Raised when analytics operations fail."""


# Infrastructure Exceptions
class InfrastructureException(ApplicationException):
    """Base class for infrastructure layer exceptions."""


class RepositoryError(InfrastructureException):
    """Raised when repository operations fail."""


class DataAccessError(InfrastructureException):
    """Raised when data access operations fail."""


class ExternalServiceError(InfrastructureException):
    """Raised when external service calls fail."""


# API and Interface Exceptions
class APIException(ApplicationException):
    """Base class for API-related exceptions."""


class AuthenticationError(APIException):
    """Raised when authentication fails."""


class AuthorizationError(APIException):
    """Raised when authorization fails."""


class RateLimitError(APIException):
    """Raised when rate limit is exceeded."""


class InputValidationError(APIException):
    """Raised when API input validation fails."""


# Configuration and Setup Exceptions
class ConfigurationError(ApplicationException):
    """Raised when there are configuration issues."""


class InitializationError(ApplicationException):
    """Raised when system initialization fails."""


# Factory Functions
def create_repository_error(operation: str, details: Optional[dict] = None) -> RepositoryError:
    """Factory function for creating repository errors."""
    return RepositoryError(
        f"Repository operation '{operation}' failed", details=details or {}
    )


def create_external_service_error(service: str, details: Optional[dict] = None) -> ExternalServiceError:
    """Factory function for creating external service errors."""
    return ExternalServiceError(
        f"External service '{service}' call failed", details=details or {}
    )


__all__ = [
    # Base application classes
    "ApplicationException",
    "ApplicationError", 
    "UseCaseError",
    "InvalidOperationError",
    # Report and analytics
    "ReportGenerationError",
    "InvalidReportParametersError",
    "AnalyticsError",
    # Infrastructure
    "InfrastructureException",
    "RepositoryError",
    "DataAccessError", 
    "ExternalServiceError",
    # API and interface
    "APIException",
    "AuthenticationError",
    "AuthorizationError",
    "RateLimitError",
    "InputValidationError",
    # Configuration
    "ConfigurationError",
    "InitializationError",
    # Factory functions
    "create_repository_error",
    "create_external_service_error",
]
