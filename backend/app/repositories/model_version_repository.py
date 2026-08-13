"""Persistence primitives for model-registry versions."""

from __future__ import annotations

import re

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.models.model_version import ModelVersion

_VERSION_PATTERN = re.compile(r"^v(?P<number>\d+)$")


class ModelVersionRepository:
    """Query model metadata while leaving transaction boundaries to services."""

    def __init__(self, db: Session) -> None:
        self.db = db

    def get(self, version_id: int) -> ModelVersion | None:
        return self.db.get(ModelVersion, version_id)

    def list(
        self,
        *,
        model_type: str | None = None,
        model_family: str | None = None,
    ) -> list[ModelVersion]:
        statement = select(ModelVersion)
        if model_type is not None:
            statement = statement.where(ModelVersion.model_type == model_type)
        if model_family is not None:
            statement = statement.where(ModelVersion.model_family == model_family)
        return list(
            self.db.scalars(
                statement.order_by(ModelVersion.trained_at.desc(), ModelVersion.id.desc())
            )
        )

    def next_version(self, model_type: str) -> str:
        """Return the next simple version while locking this type's rows on PostgreSQL."""

        versions = self.db.scalars(
            select(ModelVersion.version)
            .where(ModelVersion.model_type == model_type)
            .with_for_update()
        )
        numbers = [
            int(match.group("number"))
            for value in versions
            if (match := _VERSION_PATTERN.fullmatch(value)) is not None
        ]
        return f"v{max(numbers, default=0) + 1:04d}"

    def get_active(self, model_type: str, model_family: str) -> ModelVersion | None:
        return self.db.scalar(
            select(ModelVersion).where(
                ModelVersion.model_type == model_type,
                ModelVersion.model_family == model_family,
                ModelVersion.is_active.is_(True),
            )
        )

    def create(self, values: dict[str, object]) -> ModelVersion:
        entity = ModelVersion(**values)
        self.db.add(entity)
        self.db.flush()
        return entity

    def activate(self, entity: ModelVersion) -> ModelVersion:
        self.db.execute(
            update(ModelVersion)
            .where(
                ModelVersion.model_type == entity.model_type,
                ModelVersion.model_family == entity.model_family,
                ModelVersion.id != entity.id,
            )
            .values(is_active=False)
        )
        entity.is_active = True
        self.db.flush()
        return entity
