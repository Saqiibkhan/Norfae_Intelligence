from collections.abc import Mapping
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.agents.errors import AgentExecutionError, AgentPermissionError


class AgentContext(BaseModel):
    """Per-execution identity, authorization claims, tracing, and approved services.

    Values must be populated by a trusted caller after authentication and
    authorization. This model does not authenticate users or verify permissions.
    """

    user_id: str | None = None
    business_id: str | None = None
    permissions: frozenset[str] = Field(default_factory=frozenset)
    request_id: str | None = None
    dependencies: Mapping[str, Any] = Field(
        default_factory=dict,
        repr=False,
        exclude=True,
    )

    model_config = ConfigDict(frozen=True, arbitrary_types_allowed=True)

    def require_business_scope(self, permission: str) -> str:
        """Return the scoped business ID or fail closed when authorization is absent."""
        if not self.business_id or not permission or permission not in self.permissions:
            raise AgentPermissionError(
                "Authorized business scope and required permission are missing."
            )
        return self.business_id

    def get_business_dependency(self, name: str, permission: str) -> Any:
        """Expose a business-data service only after scope and permission checks."""
        self.require_business_scope(permission)
        return self.get_dependency(name)

    def get_dependency(self, name: str) -> Any:
        """Get a caller-approved service dependency without exposing it in serialization."""
        try:
            return self.dependencies[name]
        except KeyError:
            raise AgentExecutionError(
                f"Required agent dependency '{name}' is not available."
            ) from None
