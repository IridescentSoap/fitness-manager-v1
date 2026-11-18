from typing import Any, Generic, TypeVar

from pydantic import BaseModel, Field

T = TypeVar("T")


class ApiSuccess(BaseModel, Generic[T]):
    data: T


class ErrorBody(BaseModel):
    code: str
    message: str
    details: dict[str, Any] = Field(default_factory=dict)


class ApiError(BaseModel):
    error: ErrorBody


class HealthData(BaseModel):
    status: str
    version: str
    timezone: str
    database: dict[str, str]
