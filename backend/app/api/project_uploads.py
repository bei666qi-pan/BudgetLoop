"""Authenticated browser project-folder snapshot API."""
from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, File, Form, HTTPException, UploadFile, status

from app.project_uploads import ProjectUploadError, store_project_upload

router = APIRouter(tags=["project-uploads"])


@router.post("/project-uploads", status_code=status.HTTP_201_CREATED)
async def upload_project_folder(
    files: Annotated[list[UploadFile], File()],
    paths: Annotated[list[str], Form()],
) -> dict[str, int | str]:
    try:
        return await store_project_upload(files, paths)
    except ProjectUploadError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
