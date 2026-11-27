"""Validation schemas shared by the patient API."""

import re
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator


class PatientFields(BaseModel):
    model_config = ConfigDict(extra="forbid")

    full_name: str = Field(min_length=2, max_length=120)
    age: int = Field(ge=0, le=130)
    gender: str = Field(min_length=1, max_length=50)
    email: str | None = Field(default=None, max_length=254)
    phone: str | None = Field(default=None, max_length=30)
    concern: str | None = Field(default=None, max_length=1000)

    @field_validator("full_name")
    @classmethod
    def clean_name(cls, value: str) -> str:
        value = " ".join(value.split())
        if len(value) < 2:
            raise ValueError("Full name must contain at least two characters.")
        return value

    @field_validator("gender")
    @classmethod
    def clean_gender(cls, value: str) -> str:
        value = " ".join(value.split()).lower()
        if not value:
            raise ValueError("Gender is required.")
        return value

    @field_validator("email")
    @classmethod
    def validate_email(cls, value: str | None) -> str | None:
        if value is None or not value.strip():
            return None
        value = value.strip().lower()
        if not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", value):
            raise ValueError("Enter a valid email address.")
        return value

    @field_validator("phone", "concern")
    @classmethod
    def clean_optional_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip()
        return value or None


class PatientCreate(PatientFields):
    """Fields required to register a patient."""


class PatientUpdate(BaseModel):
    """All fields are optional so a client can update only what changed."""

    model_config = ConfigDict(extra="forbid")

    full_name: str | None = Field(default=None, min_length=2, max_length=120)
    age: int | None = Field(default=None, ge=0, le=130)
    gender: str | None = Field(default=None, min_length=1, max_length=50)
    email: str | None = Field(default=None, max_length=254)
    phone: str | None = Field(default=None, max_length=30)
    concern: str | None = Field(default=None, max_length=1000)

    @field_validator("full_name")
    @classmethod
    def clean_name(cls, value: str | None) -> str | None:
        return PatientFields.clean_name(value) if value is not None else value

    @field_validator("gender")
    @classmethod
    def clean_gender(cls, value: str | None) -> str | None:
        return PatientFields.clean_gender(value) if value is not None else value

    @field_validator("email")
    @classmethod
    def validate_email(cls, value: str | None) -> str | None:
        return PatientFields.validate_email(value)

    @field_validator("phone", "concern")
    @classmethod
    def clean_optional_text(cls, value: str | None) -> str | None:
        return PatientFields.clean_optional_text(value)


class PatientResponse(PatientFields):
    """Patient record returned by the API."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    is_active: bool
    created_at: datetime
    updated_at: datetime | None = None


class PatientCountResponse(BaseModel):
    count: int
