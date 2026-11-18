from __future__ import annotations

from pydantic import BaseModel, Field


class InitializeRequest(BaseModel):
    username: str = Field(min_length=3, max_length=64)
    display_name: str = Field(min_length=1, max_length=64)
    password: str = Field(min_length=1, max_length=128)


class LoginRequest(BaseModel):
    username: str
    password: str


class PasswordChangeRequest(BaseModel):
    old_password: str
    new_password: str = Field(min_length=1, max_length=128)


class AdminCreateUserRequest(BaseModel):
    username: str = Field(min_length=3, max_length=64)
    display_name: str = Field(min_length=1, max_length=64)
    password: str = Field(min_length=1, max_length=128)


class AdminUpdateUserRequest(BaseModel):
    display_name: str | None = Field(default=None, min_length=1, max_length=64)
    status: str | None = None


class AdminResetPasswordRequest(BaseModel):
    new_password: str = Field(min_length=1, max_length=128)


class ExerciseCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    category: str
    description: str | None = None


class ExerciseUpdateRequest(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=100)
    category: str | None = None
    description: str | None = None
    is_active: bool | None = None


class SharingUpdateRequest(BaseModel):
    share_training_stats: bool
    share_weight_change: bool
    share_weight_values: bool


class ProfileUpdateRequest(BaseModel):
    display_name: str | None = Field(default=None, min_length=1, max_length=64)
    target_weight_kg: float | None = None
