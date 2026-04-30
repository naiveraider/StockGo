from __future__ import annotations

from typing import Any

from pydantic import BaseModel, EmailStr, Field


class UserCreate(BaseModel):
    email: EmailStr
    password: str = Field(min_length=6, max_length=128)
    full_name: str | None = Field(default=None, max_length=255)


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class UserOut(BaseModel):
    id: int
    email: EmailStr
    full_name: str | None = None
    role: str = "member"


class AdminUserOut(BaseModel):
    id: int
    email: str
    full_name: str | None = None
    role: str
    created_at: str | None = None


class AdminUserUpdate(BaseModel):
    role: str


class AdminLoginRequest(BaseModel):
    username: str
    password: str


class AdminLlmPolicyOut(BaseModel):
    key: str
    title: str
    description: str
    placeholders: list[str] = Field(default_factory=list)
    system_prompt: str
    user_prompt: str
    updated_at: str | None = None


class AdminLlmPolicyUpdate(BaseModel):
    system_prompt: str = Field(min_length=1)
    user_prompt: str = Field(min_length=1)


class AdminSyncResponse(BaseModel):
    job: str
    tickers: list[str]
    requested: int
    succeeded: int
    failed: int
    details: list[dict[str, Any]] = Field(default_factory=list)


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserOut

