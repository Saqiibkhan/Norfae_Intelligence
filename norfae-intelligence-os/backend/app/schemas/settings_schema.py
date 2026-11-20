from pydantic import BaseModel, ConfigDict, Field, SecretStr, model_validator
from app.utils.shopify_url import normalize_shopify_store_url


class SettingsRead(BaseModel):
    gst_percentage: float
    fuel_surcharge_percentage: float
    income_tax_percentage: float
    packaging_cost: float
    warehouse_city: str
    warehouse_province: str
    shopify_store_url: str | None
    meta_account_id: str | None
    shopify_connected: bool
    meta_connected: bool
    same_city_half_kg: float
    same_city_one_kg: float
    same_city_additional_half_kg: float
    same_province_half_kg: float
    same_province_one_kg: float
    same_province_additional_half_kg: float
    other_province_half_kg: float
    other_province_one_kg: float
    other_province_additional_half_kg: float


class SettingsUpdateResponse(BaseModel):
    message: str
    settings: SettingsRead


class SettingsUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    gst_percentage: float | None = Field(default=None, ge=0)
    fuel_surcharge_percentage: float | None = Field(default=None, ge=0)
    income_tax_percentage: float | None = Field(default=None, ge=0)
    packaging_cost: float | None = Field(default=None, ge=0)
    warehouse_city: str | None = Field(default=None, min_length=1, max_length=120)
    warehouse_province: str | None = Field(default=None, min_length=1, max_length=120)
    same_city_half_kg: float | None = Field(default=None, ge=0)
    same_city_one_kg: float | None = Field(default=None, ge=0)
    same_city_additional_half_kg: float | None = Field(default=None, ge=0)
    same_province_half_kg: float | None = Field(default=None, ge=0)
    same_province_one_kg: float | None = Field(default=None, ge=0)
    same_province_additional_half_kg: float | None = Field(default=None, ge=0)
    other_province_half_kg: float | None = Field(default=None, ge=0)
    other_province_one_kg: float | None = Field(default=None, ge=0)
    other_province_additional_half_kg: float | None = Field(default=None, ge=0)

    @model_validator(mode="after")
    def require_non_null_updates(self):
        if not self.model_fields_set:
            raise ValueError("At least one settings field must be provided.")
        if any(getattr(self, key) is None for key in self.model_fields_set):
            raise ValueError("Settings values cannot be null.")
        return self


class SettingsIntegrationUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    shopify_store_url: str | None = Field(default=None, max_length=500)
    meta_account_id: str | None = Field(default=None, max_length=200)
    shopify_access_token: SecretStr | None = None
    meta_access_token: SecretStr | None = None
    clear_shopify_access_token: bool = False
    clear_meta_access_token: bool = False

    @model_validator(mode="before")
    @classmethod
    def normalize_shopify_url(cls, values):
        if isinstance(values, dict) and values.get("shopify_store_url") is not None:
            values = dict(values)
            values["shopify_store_url"] = normalize_shopify_store_url(
                values["shopify_store_url"]
            )
        return values

    @model_validator(mode="after")
    def require_explicit_operations(self):
        fields = self.model_fields_set
        operations = fields - {"clear_shopify_access_token", "clear_meta_access_token"}
        has_clear = self.clear_shopify_access_token or self.clear_meta_access_token
        if not operations and not has_clear:
            raise ValueError("Specify a replacement or an explicit clear operation.")
        for secret_field, clear_field in (
            ("shopify_access_token", "clear_shopify_access_token"),
            ("meta_access_token", "clear_meta_access_token"),
        ):
            if secret_field in fields and getattr(self, secret_field) is None:
                raise ValueError(
                    f"Use {clear_field}=true to clear this credential."
                )
            secret = getattr(self, secret_field)
            if secret is not None and not secret.get_secret_value():
                raise ValueError("Credential values cannot be empty.")
            if secret is not None and getattr(self, clear_field):
                raise ValueError("Replace or clear a credential, not both.")
        return self
