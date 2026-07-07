from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Optional

from regulaforge.common.exceptions import ConflictError, NotFoundError, ValidationError
from regulaforge.modules.contracts.domain.models import (
    Clause,
    Contract,
    ContractStatus,
    ContractVersion,
    Template,
)
from regulaforge.modules.contracts.domain.repository import (
    ClauseRepository,
    ContractRepository,
    ContractVersionRepository,
    TemplateRepository,
)

logger = logging.getLogger(__name__)


class ContractService:
    def __init__(
        self,
        contract_repo: ContractRepository,
        version_repo: ContractVersionRepository,
        template_repo: TemplateRepository,
        clause_repo: ClauseRepository,
    ) -> None:
        self._contract_repo = contract_repo
        self._version_repo = version_repo
        self._template_repo = template_repo
        self._clause_repo = clause_repo

    async def get_contract(self, contract_id: str) -> Contract:
        contract = await self._contract_repo.find_by_id(contract_id)
        if not contract:
            raise NotFoundError(f"Contract {contract_id} not found")
        return contract

    async def list_contracts(
        self, skip: int = 0, limit: int = 100, tenant_id: Optional[str] = None,
    ) -> tuple[list[Contract], int]:
        contracts = await self._contract_repo.find_all(skip, limit, tenant_id)
        total = await self._contract_repo.count(tenant_id)
        return contracts, total

    async def create_contract(
        self, contract: Contract, created_by: str = "",
    ) -> Contract:
        contract.created_by = created_by
        contract.current_version = 1
        version = ContractVersion(
            contract_id=contract.id,
            version_number=1,
            content=contract.content,
            clauses=list(contract.clauses),
            created_by=created_by,
        )
        saved = await self._contract_repo.save(contract)
        await self._version_repo.save(version)
        saved.versions = [version]
        return saved

    async def update_contract(self, contract_id: str, updates: dict[str, Any], updated_by: str = "") -> Contract:
        contract = await self.get_contract(contract_id)
        changed = False
        for key, value in updates.items():
            if hasattr(contract, key) and key not in ("id", "created_at", "created_by", "versions"):
                setattr(contract, key, value)
                changed = True
        if changed:
            contract.updated_at = datetime.utcnow()
            contract.current_version += 1
            version = ContractVersion(
                contract_id=contract.id,
                version_number=contract.current_version,
                content=contract.content,
                clauses=list(contract.clauses),
                changes_summary=f"Updated fields: {', '.join(updates.keys())}",
                created_by=updated_by,
            )
            await self._version_repo.save(version)
            contract.versions.append(version)
        return await self._contract_repo.save(contract)

    async def change_status(self, contract_id: str, new_status: ContractStatus, changed_by: str = "") -> Contract:
        contract = await self.get_contract(contract_id)
        contract.status = new_status
        contract.updated_at = datetime.utcnow()
        if new_status == ContractStatus.EXECUTED:
            contract.signed_date = datetime.utcnow()
        return await self._contract_repo.save(contract)

    async def delete_contract(self, contract_id: str) -> None:
        contract = await self.get_contract(contract_id)
        await self._contract_repo.delete(contract_id)

    async def get_version(self, version_id: str) -> ContractVersion:
        version = await self._version_repo.find_by_id(version_id)
        if not version:
            raise NotFoundError(f"Version {version_id} not found")
        return version

    async def list_versions(self, contract_id: str) -> list[ContractVersion]:
        return await self._version_repo.find_by_contract(contract_id)

    async def get_template(self, template_id: str) -> Template:
        template = await self._template_repo.find_by_id(template_id)
        if not template:
            raise NotFoundError(f"Template {template_id} not found")
        return template

    async def list_templates(self, skip: int = 0, limit: int = 100) -> tuple[list[Template], int]:
        templates = await self._template_repo.find_all(skip, limit)
        total = len(templates)
        return templates, total

    async def create_template(self, template: Template) -> Template:
        return await self._template_repo.save(template)

    async def update_template(self, template_id: str, updates: dict[str, Any]) -> Template:
        template = await self.get_template(template_id)
        for key, value in updates.items():
            if hasattr(template, key) and key not in ("id", "created_at"):
                setattr(template, key, value)
        template.updated_at = datetime.utcnow()
        return await self._template_repo.save(template)

    async def delete_template(self, template_id: str) -> None:
        template = await self.get_template(template_id)
        await self._template_repo.delete(template_id)

    async def create_clause(self, clause: Clause) -> Clause:
        return await self._clause_repo.save(clause)

    async def list_clauses(self, category: Optional[str] = None) -> list[Clause]:
        return await self._clause_repo.find_all(category)

    async def get_clause(self, clause_id: str) -> Clause:
        clause = await self._clause_repo.find_by_id(clause_id)
        if not clause:
            raise NotFoundError(f"Clause {clause_id} not found")
        return clause
