class OpenRouterError(Exception):
    """Base error for safe, application-level OpenRouter failures."""


class OpenRouterConfigurationError(OpenRouterError):
    """Required OpenRouter configuration is missing or invalid."""


class OpenRouterAuthenticationError(OpenRouterError):
    """OpenRouter rejected the configured API key."""


class OpenRouterRateLimitError(OpenRouterError):
    """OpenRouter rate limit remained after the configured retries."""


class OpenRouterTimeoutError(OpenRouterError):
    """The OpenRouter request timed out."""


class OpenRouterConnectionError(OpenRouterError):
    """The OpenRouter endpoint could not be reached."""


class OpenRouterProviderError(OpenRouterError):
    """OpenRouter returned an unsuccessful or unusable response."""
