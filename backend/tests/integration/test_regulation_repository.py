"""Integration tests for SqlAlchemyRegulationRepository using SQLite in-memory."""

from datetime import date

from regulaforge.config.constants import (
    RegulationCategory,
    RegulationJurisdiction,
    RegulationStatus,
)
from regulaforge.domain.entities.regulation import Regulation


class TestRegulationRepository:
    """Suite of integration tests for the regulation repository."""

    async def test_create_regulation(self, regulation_repo, db_session):
        reg = Regulation(
            title="General Data Protection Regulation",
            code="GDPR",
            description="EU regulation on data protection",
            category=RegulationCategory.DATA_PROTECTION,
            jurisdiction=RegulationJurisdiction.EU,
            issuing_body="European Parliament",
            effective_date=date(2018, 5, 25),
            status=RegulationStatus.ACTIVE,
        )
        saved = await regulation_repo.save(reg)
        assert saved.id == reg.id
        assert saved.code == "GDPR"

        db_session.expire_all()
        fetched = await regulation_repo.get_by_id(reg.id)
        assert fetched is not None
        assert fetched.title == "General Data Protection Regulation"
        assert fetched.category == RegulationCategory.DATA_PROTECTION
        assert fetched.jurisdiction == RegulationJurisdiction.EU

    async def test_get_by_id(self, regulation_repo, db_session):
        reg = Regulation(
            title="California Consumer Privacy Act",
            code="CCPA",
            description="California privacy law",
            category=RegulationCategory.PRIVACY,
            jurisdiction=RegulationJurisdiction.US_STATE,
            issuing_body="California Legislature",
            effective_date=date(2020, 1, 1),
        )
        await regulation_repo.save(reg)
        db_session.expire_all()

        fetched = await regulation_repo.get_by_id(reg.id)
        assert fetched is not None
        assert fetched.code == "CCPA"

    async def test_get_by_code(self, regulation_repo, db_session):
        reg = Regulation(
            title="Sarbanes-Oxley Act",
            code="SOX",
            description="US financial reporting law",
            category=RegulationCategory.FINANCIAL,
            jurisdiction=RegulationJurisdiction.US_FEDERAL,
            issuing_body="US Congress",
            effective_date=date(2002, 7, 30),
        )
        await regulation_repo.save(reg)
        db_session.expire_all()

        fetched = await regulation_repo.get_by_code("SOX")
        assert fetched is not None
        assert fetched.title == "Sarbanes-Oxley Act"

        not_found = await regulation_repo.get_by_code("NONEXISTENT")
        assert not_found is None

    async def test_get_by_category(self, regulation_repo, db_session):
        reg1 = Regulation(
            title="GDPR",
            code="GDPR",
            description="EU data protection",
            category=RegulationCategory.DATA_PROTECTION,
            jurisdiction=RegulationJurisdiction.EU,
            issuing_body="EU",
            effective_date=date(2018, 5, 25),
            status=RegulationStatus.ACTIVE,
        )
        reg2 = Regulation(
            title="HIPAA",
            code="HIPAA",
            description="US health privacy",
            category=RegulationCategory.HEALTH_SAFETY,
            jurisdiction=RegulationJurisdiction.US_FEDERAL,
            issuing_body="US Congress",
            effective_date=date(1996, 8, 21),
            status=RegulationStatus.ACTIVE,
        )
        await regulation_repo.save(reg1)
        await regulation_repo.save(reg2)
        db_session.expire_all()

        # get_active_by_category filters by status="active" AND category
        data_results, data_total = await regulation_repo.get_active_by_category(
            RegulationCategory.DATA_PROTECTION.value
        )
        assert data_total >= 1
        codes = {r.code for r in data_results}
        assert "GDPR" in codes
        assert "HIPAA" not in codes

    async def test_get_by_jurisdiction(self, regulation_repo, db_session):
        reg1 = Regulation(
            title="GDPR",
            code="GDPR",
            description="EU data protection",
            category=RegulationCategory.DATA_PROTECTION,
            jurisdiction=RegulationJurisdiction.EU,
            issuing_body="EU",
            effective_date=date(2018, 5, 25),
        )
        reg2 = Regulation(
            title="CCPA",
            code="CCPA",
            description="California privacy",
            category=RegulationCategory.PRIVACY,
            jurisdiction=RegulationJurisdiction.US_STATE,
            issuing_body="California",
            effective_date=date(2020, 1, 1),
        )
        await regulation_repo.save(reg1)
        await regulation_repo.save(reg2)
        db_session.expire_all()

        eu_results, eu_total = await regulation_repo.get_by_jurisdiction(
            RegulationJurisdiction.EU.value
        )
        assert eu_total >= 1
        codes = {r.code for r in eu_results}
        assert "GDPR" in codes
        assert "CCPA" not in codes

    async def test_list_regulations(self, regulation_repo, db_session):
        regs = [
            Regulation(
                title=f"Regulation {i}",
                code=f"REG-{i:03d}",
                description=f"Test regulation {i}",
                category=RegulationCategory.GENERAL,
                jurisdiction=RegulationJurisdiction.GLOBAL,
                issuing_body="Test Body",
                effective_date=date(2024, 1, 1),
            )
            for i in range(1, 4)
        ]
        for r in regs:
            await regulation_repo.save(r)
        db_session.expire_all()

        results, total = await regulation_repo.search(page=1, page_size=100)
        assert total >= 3
        codes = {r.code for r in results}
        assert codes == {"REG-001", "REG-002", "REG-003"}

    async def test_update_regulation(self, regulation_repo, db_session):
        reg = Regulation(
            title="Original Title",
            code="UPD",
            description="Original description",
            category=RegulationCategory.GENERAL,
            jurisdiction=RegulationJurisdiction.GLOBAL,
            issuing_body="Test Body",
            effective_date=date(2024, 1, 1),
        )
        await regulation_repo.save(reg)
        db_session.expire_all()

        fetched = await regulation_repo.get_by_id(reg.id)
        fetched._title = "Updated Title"
        fetched._description = "Updated description"
        await regulation_repo.save(fetched)
        db_session.expire_all()

        updated = await regulation_repo.get_by_id(reg.id)
        assert updated is not None
        assert updated.title == "Updated Title"
        assert updated.description == "Updated description"

    async def test_delete_regulation(self, regulation_repo, db_session):
        reg = Regulation(
            title="To Be Deleted",
            code="DEL",
            description="Will be deleted",
            category=RegulationCategory.GENERAL,
            jurisdiction=RegulationJurisdiction.GLOBAL,
            issuing_body="Test Body",
            effective_date=date(2024, 1, 1),
        )
        await regulation_repo.save(reg)
        db_session.expire_all()

        assert await regulation_repo.exists(reg.id) is True
        await regulation_repo.delete(reg.id)
        assert await regulation_repo.exists(reg.id) is False
        fetched = await regulation_repo.get_by_id(reg.id)
        assert fetched is None
