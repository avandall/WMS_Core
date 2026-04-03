"""Application layer (use-cases / services).

Keep this package import-light: `app.application` should not eagerly import
runtime dependencies (DB/config) as a side effect.
"""

__all__: list[str] = []
