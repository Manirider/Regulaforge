from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Optional
from uuid import uuid4


class ReportFormat(str, Enum):
    PDF = "pdf"
    CSV = "csv"
    JSON = "json"
    XLSX = "xlsx"
    HTML = "html"
    DOCX = "docx"


@dataclass
class ReportTemplate:
    id: str = field(default_factory=lambda: str(uuid4()))
    name: str = ""
    description: str = ""
    category: str = ""
    config: dict[str, Any] = field(default_factory=dict)
    output_format: ReportFormat = ReportFormat.PDF
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)


@dataclass
class ReportSchedule:
    id: str = field(default_factory=lambda: str(uuid4()))
    report_template_id: str = ""
    cron_expression: str = "0 0 * * *"
    parameters: dict[str, Any] = field(default_factory=dict)
    recipients: list[str] = field(default_factory=list)
    enabled: bool = True
    last_run_at: Optional[datetime] = None
    next_run_at: Optional[datetime] = None
    created_at: datetime = field(default_factory=datetime.utcnow)


@dataclass
class Report:
    id: str = field(default_factory=lambda: str(uuid4()))
    title: str = ""
    description: str = ""
    report_type: str = "compliance"
    format: ReportFormat = ReportFormat.JSON
    data: dict[str, Any] = field(default_factory=dict)
    filters: dict[str, Any] = field(default_factory=dict)
    template_id: str = ""
    file_url: str = ""
    file_size: int = 0
    status: str = "pending"
    generated_by: str = ""
    tenant_id: str = ""
    created_at: datetime = field(default_factory=datetime.utcnow)
    generated_at: Optional[datetime] = None
