from __future__ import annotations

from typing import Optional

from regulaforge.modules.regulations.domain.models import Assessment, ComplianceRequirement, Regulation


class RegulationRepository:
    async def find_by_id(self, regulation_id: str) -> Optional[Regulation]:
        raise NotImplementedError

    async def find_by_name(self, name: str) -> Optional[Regulation]:
        raise NotImplementedError

    async def find_all(
        self, skip: int = 0, limit: int = 100, tenant_id: Optional[str] = None,
    ) -> list[Regulation]:
        raise NotImplementedError

    async def count(self, tenant_id: Optional[str] = None) -> int:
        raise NotImplementedError

    async def save(self, regulation: Regulation) -> Regulation:
        raise NotImplementedError

    async def delete(self, regulation_id: str) -> None:
        raise NotImplementedError


class ComplianceRequirementRepository:
    async def find_by_regulation(self, regulation_id: str) -> list[ComplianceRequirement]:
        raise NotImplementedError

    async def save(self, requirement: ComplianceRequirement) -> ComplianceRequirement:
        raise NotImplementedError

    async def delete(self, requirement_id: str) -> None:
        raise NotImplementedError


class AssessmentRepository:
    async def find_by_id(self, assessment_id: str) -> Optional[Assessment]:
        raise NotImplementedError

    async def find_by_entity(self, entity_id: str, entity_type: str) -> list[Assessment]:
        raise NotImplementedError

    async def find_all(
        self, skip: int = 0, limit: int = 100,
    ) -> list[Assessment]:
        raise NotImplementedError

    async def save(self, assessment: Assessment) -> Assessment:
        raise NotImplementedError
