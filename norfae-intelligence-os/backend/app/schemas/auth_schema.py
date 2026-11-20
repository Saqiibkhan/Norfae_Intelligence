from datetime import datetime
import re
from typing import Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    SecretStr,
    field_validator,
    model_validator,
)

from app.core.security import SecurityManager
from app.models.business_membership_model import MembershipRole


_EMAIL_PATTERN = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")


class RegistrationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    full_name: str | None = Field(default=None, max_length=200)
    email: str = Field(max_length=320)
    password: SecretStr
    business_name: str = Field(min_length=1, max_length=200)

    @field_validator("email", mode="before")
    @classmethod
    def normalize_and_validate_email(cls, value):
        if not isinstance(value, str):
            raise ValueError("A valid email address is required.")
        normalized = value.strip().lower()
        if len(normalized) > 320 or not _EMAIL_PATTERN.fullmatch(normalized):
            raise ValueError("A valid email address is required.")
        return normalized

    @field_validator("password")
    @classmethod
    def validate_new_password(cls, value: SecretStr) -> SecretStr:
        SecurityManager.validate_password(value.get_secret_value())
        return value

    @field_validator("full_name", "business_name")
    @classmethod
    def normalize_names(cls, value):
        if value is None:
            return None
        normalized = value.strip()
        if not normalized:
            raise ValueError("Name must not be empty.")
        return normalized


class LoginRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    email: str = Field(max_length=320)
    password: SecretStr

    @field_validator("email", mode="before")
    @classmethod
    def normalize_email(cls, value):
        if not isinstance(value, str):
            raise ValueError("Invalid credentials.")
        normalized = value.strip().lower()
        if len(normalized) > 320 or not _EMAIL_PATTERN.fullmatch(normalized):
            raise ValueError("Invalid credentials.")
        return normalized


class TokenResponse(BaseModel):
    access_token: str
    token_type: Literal["bearer"] = "bearer"
    expires_in: int


class AuthenticatedUserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    email: str
    full_name: str | None
    is_active: bool
    created_at: datetime
    updated_at: datetime


class BusinessResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    owner_id: int
    is_active: bool
    created_at: datetime
    updated_at: datetime


class AuthenticationResponse(TokenResponse):
    user: AuthenticatedUserResponse
    business: BusinessResponse | None = None


class BusinessCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=200)

    @field_validator("name")
    @classmethod
    def normalize_name(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("Business name must not be empty.")
        return normalized


class BusinessUpdate(BusinessCreate):
    pass


class AccessibleBusinessResponse(BusinessResponse):
    role: MembershipRole


class MembershipCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    email: str = Field(max_length=320)
    role: MembershipRole

    @field_validator("email", mode="before")
    @classmethod
    def normalize_email(cls, value):
        if not isinstance(value, str):
            raise ValueError("A valid email address is required.")
        normalized = value.strip().lower()
        if len(normalized) > 320 or not _EMAIL_PATTERN.fullmatch(normalized):
            raise ValueError("A valid email address is required.")
        return normalized


class MembershipUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    role: MembershipRole | None = None
    is_active: bool | None = None

    @field_validator("role", "is_active")
    @classmethod
    def disallow_null_updates(cls, value):
        if value is None:
            raise ValueError("Update values cannot be null.")
        return value

    @model_validator(mode="after")
    def require_update_field(self):
        if not self.model_fields_set:
            raise ValueError("At least one membership field must be updated.")
        return self


class BusinessMembershipResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    user_id: int
    email: str
    full_name: str | None
    role: MembershipRole
    is_active: bool
    created_at: datetime
