"""Integration tests for SqlAlchemyAssessmentRepository using SQLite in-memory."""

from datetime import date
from uuid import uuid4

from regulaforge.config.constants import (
    AssessmentStatus,
    RegulationCategory,
    RegulationJurisdiction,
    RiskLevel,
)
from regulaforge.domain.entities.compliance_assessment import (
    ComplianceAssessment,
    ComplianceFinding,
)
from regulaforge.domain.entities.regulation import Regulation
from regulaforge.infrastructure.persistence.models.assessment_model import (
    ComplianceFindingModel,
)
from sqlalchemy import select


class TestAssessmentRepository:
    """Suite of integration tests for the assessment repository."""

    async def _seed_regulation(self, regulation_repo, db_session):
        reg = Regulation(
            title="GDPR",
            code="GDPR-TEST",
            description="EU data protection regulation",
            category=RegulationCategory.DATA_PROTECTION,
            jurisdiction=RegulationJurisdiction.EU,
            issuing_body="European Parliament",
            effective_date=date(2018, 5, 25),
        )
        await regulation_repo.save(reg)
        db_session.expire_all()
        return reg

    async def test_create_assessment(self, assessment_repo, regulation_repo, db_session):
        reg = await self._seed_regulation(regulation_repo, db_session)
        entity_id = uuid4()
        assessor_id = uuid4()

        assessment = ComplianceAssessment(
            title="GDPR Assessment 2024",
            entity_id=entity_id,
            entity_type="organization",
            regulation_ids=[reg.id],
            assessor_id=assessor_id,
            due_date=date(2024, 12, 31),
            status=AssessmentStatus.SCHEDULED,
        )
        saved = await assessment_repo.save(assessment)
        assert saved.id == assessment.id

        db_session.expire_all()
        fetched = await assessment_repo.get_by_id(assessment.id)
        assert fetched is not None
        assert fetched.title == "GDPR Assessment 2024"
        assert fetched.status == AssessmentStatus.SCHEDULED

    async def test_get_by_id(self, assessment_repo, regulation_repo, db_session):
        reg = await self._seed_regulation(regulation_repo, db_session)
        assessment = ComplianceAssessment(
            title="Find Me",
            entity_id=uuid4(),
            entity_type="organization",
            regulation_ids=[reg.id],
            assessor_id=uuid4(),
            due_date=date(2024, 12, 31),
        )
        await assessment_repo.save(assessment)
        db_session.expire_all()

        fetched = await assessment_repo.get_by_id(assessment.id)
        assert fetched is not None
        assert fetched.id == assessment.id

    async def test_get_by_entity_id(self, assessment_repo, regulation_repo, db_session):
        reg = await self._seed_regulation(regulation_repo, db_session)
        entity_id = uuid4()
        other_entity_id = uuid4()

        a1 = ComplianceAssessment(
            title="Assessment A",
            entity_id=entity_id,
            entity_type="organization",
            regulation_ids=[reg.id],
            assessor_id=uuid4(),
            due_date=date(2024, 12, 31),
        )
        a2 = ComplianceAssessment(
            title="Assessment B",
            entity_id=entity_id,
            entity_type="organization",
            regulation_ids=[reg.id],
            assessor_id=uuid4(),
            due_date=date(2024, 12, 31),
        )
        a3 = ComplianceAssessment(
            title="Assessment C",
            entity_id=other_entity_id,
            entity_type="organization",
            regulation_ids=[reg.id],
            assessor_id=uuid4(),
            due_date=date(2024, 12, 31),
        )
        for a in (a1, a2, a3):
            await assessment_repo.save(a)
        db_session.expire_all()

        results, total = await assessment_repo.get_by_entity(entity_id)
        assert total == 2
        titles = {r.title for r in results}
        assert titles == {"Assessment A", "Assessment B"}

    async def test_get_by_status(self, assessment_repo, regulation_repo, db_session):
        reg = await self._seed_regulation(regulation_repo, db_session)

        a1 = ComplianceAssessment(
            title="Scheduled One",
            entity_id=uuid4(),
            entity_type="organization",
            regulation_ids=[reg.id],
            assessor_id=uuid4(),
            due_date=date(2024, 12, 31),
            status=AssessmentStatus.SCHEDULED,
        )
        a2 = ComplianceAssessment(
            title="In Progress One",
            entity_id=uuid4(),
            entity_type="organization",
            regulation_ids=[reg.id],
            assessor_id=uuid4(),
            due_date=date(2024, 12, 31),
            status=AssessmentStatus.IN_PROGRESS,
        )
        a3 = ComplianceAssessment(
            title="Scheduled Two",
            entity_id=uuid4(),
            entity_type="organization",
            regulation_ids=[reg.id],
            assessor_id=uuid4(),
            due_date=date(2024, 12, 31),
            status=AssessmentStatus.SCHEDULED,
        )
        for a in (a1, a2, a3):
            await assessment_repo.save(a)
        db_session.expire_all()

        results, total = await assessment_repo.get_by_status(
            AssessmentStatus.SCHEDULED.value
        )
        assert total == 2

        results_in_progress, total_ip = await assessment_repo.get_by_status(
            AssessmentStatus.IN_PROGRESS.value
        )
        assert total_ip == 1

    async def test_list_assessments(self, assessment_repo, regulation_repo, db_session):
        reg = await self._seed_regulation(regulation_repo, db_session)

        for i in range(1, 4):
            a = ComplianceAssessment(
                title=f"Assessment {i}",
                entity_id=uuid4(),
                entity_type="organization",
                regulation_ids=[reg.id],
                assessor_id=uuid4(),
                due_date=date(2024, 12, 31),
            )
            await assessment_repo.save(a)
        db_session.expire_all()

        results, total = await assessment_repo.search(page=1, page_size=100)
        assert total >= 3

    async def test_update_assessment_status(self, assessment_repo, regulation_repo, db_session):
        reg = await self._seed_regulation(regulation_repo, db_session)
        assessment = ComplianceAssessment(
            title="Status Update Test",
            entity_id=uuid4(),
            entity_type="organization",
            regulation_ids=[reg.id],
            assessor_id=uuid4(),
            due_date=date(2024, 12, 31),
            status=AssessmentStatus.SCHEDULED,
        )
        await assessment_repo.save(assessment)
        db_session.expire_all()

        fetched = await assessment_repo.get_by_id(assessment.id)
        fetched._status = AssessmentStatus.IN_PROGRESS
        await assessment_repo.save(fetched)
        db_session.expire_all()

        updated = await assessment_repo.get_by_id(assessment.id)
        assert updated is not None
        assert updated.status == AssessmentStatus.IN_PROGRESS

    async def test_add_finding(self, assessment_repo, regulation_repo, db_session):
        reg = await self._seed_regulation(regulation_repo, db_session)
        assessment = ComplianceAssessment(
            title="Finding Test",
            entity_id=uuid4(),
            entity_type="organization",
            regulation_ids=[reg.id],
            assessor_id=uuid4(),
            due_date=date(2024, 12, 31),
            status=AssessmentStatus.IN_PROGRESS,
        )
        await assessment_repo.save(assessment)
        db_session.expire_all()

        finding = ComplianceFinding(
            requirement_code="ART-5",
            title="Missing consent",
            description="No consent mechanism found",
            risk_level=RiskLevel.HIGH,
            impact_score=8.0,
            likelihood_score=7.0,
            remediation_recommendation="Implement consent management",
        )
        assessment.add_finding(finding)

        # Persist the finding at the model level
        finding_model = ComplianceFindingModel(
            id=finding.id,
            assessment_id=assessment.id,
            requirement_code=finding.requirement_code,
            title=finding.title,
            description=finding.description,
            risk_level=finding.risk_level.value,
            status="open",
            impact_score=finding.impact_score,
            likelihood_score=finding.likelihood_score,
            remediation_recommendation=finding.remediation_recommendation,
        )
        db_session.add(finding_model)
        await db_session.flush()
        db_session.expire_all()

        # Verify finding persisted at model level
        stmt = select(ComplianceFindingModel).where(
            ComplianceFindingModel.assessment_id == assessment.id
        )
        result = await db_session.execute(stmt)
        models = result.scalars().all()
        assert len(models) == 1
        assert models[0].title == "Missing consent"

    async def test_get_findings_for_assessment(
        self, assessment_repo, regulation_repo, db_session
    ):
        reg = await self._seed_regulation(regulation_repo, db_session)
        assessment = ComplianceAssessment(
            title="Findings List Test",
            entity_id=uuid4(),
            entity_type="organization",
            regulation_ids=[reg.id],
            assessor_id=uuid4(),
            due_date=date(2024, 12, 31),
            status=AssessmentStatus.IN_PROGRESS,
        )
        await assessment_repo.save(assessment)
        db_session.expire_all()

        for i in range(1, 4):
            fm = ComplianceFindingModel(
                assessment_id=assessment.id,
                requirement_code=f"REQ-{i}",
                title=f"Finding {i}",
                description=f"Description {i}",
                risk_level=RiskLevel.MEDIUM.value,
                status="open",
            )
            db_session.add(fm)
        await db_session.flush()
        db_session.expire_all()

        from regulaforge.infrastructure.persistence.models.assessment_model import (
            ComplianceAssessmentModel,
        )
        from sqlalchemy.orm import selectinload
        stmt = (
            select(ComplianceAssessmentModel)
            .where(ComplianceAssessmentModel.id == assessment.id)
            .options(selectinload(ComplianceAssessmentModel.findings))
        )
        result = await db_session.execute(stmt)
        model = result.unique().scalar_one_or_none()
        assert model is not None
        assert len(model.findings) == 3
        titles = {f.title for f in model.findings}
        assert titles == {"Finding 1", "Finding 2", "Finding 3"}
