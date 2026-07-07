from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Optional

from regulaforge.common.exceptions import ConflictError, NotFoundError
from regulaforge.modules.regulations.domain.models import (
    Assessment,
    ComplianceRequirement,
    Regulation,
    RegulationStatus,
)
from regulaforge.modules.regulations.domain.repository import (
    AssessmentRepository,
    ComplianceRequirementRepository,
    RegulationRepository,
)

logger = logging.getLogger(__name__)


class RegulationService:
    def __init__(
        self,
        regulation_repo: RegulationRepository,
        requirement_repo: ComplianceRequirementRepository,
        assessment_repo: AssessmentRepository,
    ) -> None:
        self._regulation_repo = regulation_repo
        self._requirement_repo = requirement_repo
        self._assessment_repo = assessment_repo

    async def get_regulation(self, regulation_id: str) -> Regulation:
        regulation = await self._regulation_repo.find_by_id(regulation_id)
        if not regulation:
            raise NotFoundError(f"Regulation {regulation_id} not found")
        return regulation

    async def list_regulations(
        self, skip: int = 0, limit: int = 100, tenant_id: Optional[str] = None,
    ) -> tuple[list[Regulation], int]:
        regulations = await self._regulation_repo.find_all(skip, limit, tenant_id)
        total = await self._regulation_repo.count(tenant_id)
        return regulations, total

    async def create_regulation(self, regulation: Regulation, created_by: str = "") -> Regulation:
        if regulation.name:
            existing = await self._regulation_repo.find_by_name(regulation.name)
            if existing:
                raise ConflictError(f"Regulation '{regulation.name}' already exists")
        regulation.created_by = created_by
        return await self._regulation_repo.save(regulation)

    async def update_regulation(self, regulation_id: str, updates: dict[str, Any]) -> Regulation:
        regulation = await self.get_regulation(regulation_id)
        for key, value in updates.items():
            if hasattr(regulation, key) and key not in ("id", "created_at", "created_by"):
                setattr(regulation, key, value)
        regulation.updated_at = datetime.utcnow()
        return await self._regulation_repo.save(regulation)

    async def change_status(self, regulation_id: str, new_status: RegulationStatus) -> Regulation:
        regulation = await self.get_regulation(regulation_id)
        regulation.status = new_status
        regulation.updated_at = datetime.utcnow()
        return await self._regulation_repo.save(regulation)

    async def delete_regulation(self, regulation_id: str) -> None:
        regulation = await self.get_regulation(regulation_id)
        await self._regulation_repo.delete(regulation_id)

    async def add_requirement(self, regulation_id: str, requirement: ComplianceRequirement) -> ComplianceRequirement:
        regulation = await self.get_regulation(regulation_id)
        requirement.regulation_id = regulation_id
        saved = await self._requirement_repo.save(requirement)
        regulation.requirements.append(saved)
        await self._regulation_repo.save(regulation)
        return saved

    async def list_requirements(self, regulation_id: str) -> list[ComplianceRequirement]:
        return await self._requirement_repo.find_by_regulation(regulation_id)

    async def create_assessment(self, assessment: Assessment) -> Assessment:
        return await self._assessment_repo.save(assessment)

    async def get_assessment(self, assessment_id: str) -> Assessment:
        assessment = await self._assessment_repo.find_by_id(assessment_id)
        if not assessment:
            raise NotFoundError(f"Assessment {assessment_id} not found")
        return assessment

    async def list_assessments(
        self, skip: int = 0, limit: int = 100,
    ) -> tuple[list[Assessment], int]:
        assessments = await self._assessment_repo.find_all(skip, limit)
        total = len(assessments)
        return assessments, total

    async def list_entity_assessments(self, entity_id: str, entity_type: str) -> list[Assessment]:
        return await self._assessment_repo.find_by_entity(entity_id, entity_type)
