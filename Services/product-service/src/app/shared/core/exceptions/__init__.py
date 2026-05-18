"""Core exceptions module.

This module contains all exceptions related to application orchestration,
infrastructure concerns, API handling, and configuration.
"""

from .application_exceptions import (
    ApplicationException,
    ApplicationError,
    UseCaseError,
    InvalidOperationError,
    ReportGenerationError,
    InvalidReportParametersError,
    AnalyticsError,
    InfrastructureException,
    RepositoryError,
    DataAccessError,
    ExternalServiceError,
    APIException,
    AuthenticationError,
    AuthorizationError,
    RateLimitError,
    InputValidationError,
    ConfigurationError,
    InitializationError,
    create_repository_error,
    create_external_service_error,
)

__all__ = [
    "ApplicationException",
    "ApplicationError",
    "UseCaseError", 
    "InvalidOperationError",
    "ReportGenerationError",
    "InvalidReportParametersError",
    "AnalyticsError",
    "InfrastructureException",
    "RepositoryError",
    "DataAccessError",
    "ExternalServiceError",
    "APIException",
    "AuthenticationError",
    "AuthorizationError",
    "RateLimitError",
    "InputValidationError",
    "ConfigurationError",
    "InitializationError",
    "create_repository_error",
    "create_external_service_error",
]
