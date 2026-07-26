"""Stateless home-page conversational setup drafts."""
from __future__ import annotations

from typing import Literal

from fastapi import APIRouter
from pydantic import BaseModel, Field, field_validator

from app.task_drafts import generate_task_setup_draft

router = APIRouter(tags=["task-drafts"])


class EditableDraft(BaseModel):
    model_config = {"extra": "forbid"}

    schema_version: Literal[1] = 1
    title: str = Field(min_length=1, max_length=200)
    goal: str = Field(min_length=3, max_length=10_000)
    acceptance_criteria: str = Field(min_length=1, max_length=20_000)
    shared_context: str = Field(default="", max_length=30_000)
    preset_id: str = Field(min_length=1, max_length=100)
    preset_version: int = Field(ge=1)


class CreateTaskDraftRequest(BaseModel):
    model_config = {"extra": "forbid"}

    message: str = Field(min_length=3, max_length=10_000)
    previous_draft: EditableDraft | None = None

    @field_validator("message")
    @classmethod
    def meaningful_message(cls, value: str) -> str:
        normalized = value.strip()
        if len(normalized) < 3:
            raise ValueError("message must contain at least 3 meaningful characters")
        return normalized


@router.post("/task-drafts")
def create_task_draft(body: CreateTaskDraftRequest) -> dict:
    previous = body.previous_draft.model_dump() if body.previous_draft else None
    return generate_task_setup_draft(body.message, previous_draft=previous)
