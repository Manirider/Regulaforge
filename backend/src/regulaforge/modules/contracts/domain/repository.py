from __future__ import annotations

from typing import Optional

from regulaforge.modules.contracts.domain.models import Clause, Contract, ContractVersion, Template


class ContractRepository:
    async def find_by_id(self, contract_id: str) -> Optional[Contract]:
        raise NotImplementedError

    async def find_all(
        self, skip: int = 0, limit: int = 100, tenant_id: Optional[str] = None,
    ) -> list[Contract]:
        raise NotImplementedError

    async def count(self, tenant_id: Optional[str] = None) -> int:
        raise NotImplementedError

    async def save(self, contract: Contract) -> Contract:
        raise NotImplementedError

    async def delete(self, contract_id: str) -> None:
        raise NotImplementedError


class ContractVersionRepository:
    async def find_by_id(self, version_id: str) -> Optional[ContractVersion]:
        raise NotImplementedError

    async def find_by_contract(
        self, contract_id: str, version_number: Optional[int] = None,
    ) -> list[ContractVersion]:
        raise NotImplementedError

    async def save(self, version: ContractVersion) -> ContractVersion:
        raise NotImplementedError


class TemplateRepository:
    async def find_by_id(self, template_id: str) -> Optional[Template]:
        raise NotImplementedError

    async def find_all(self, skip: int = 0, limit: int = 100) -> list[Template]:
        raise NotImplementedError

    async def save(self, template: Template) -> Template:
        raise NotImplementedError

    async def delete(self, template_id: str) -> None:
        raise NotImplementedError


class ClauseRepository:
    async def find_by_id(self, clause_id: str) -> Optional[Clause]:
        raise NotImplementedError

    async def find_all(self, category: Optional[str] = None) -> list[Clause]:
        raise NotImplementedError

    async def save(self, clause: Clause) -> Clause:
        raise NotImplementedError
