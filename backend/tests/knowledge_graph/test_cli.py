"""Tests for the Knowledge Graph CLI — argument parsing and adapter lifecycle."""

from __future__ import annotations

import contextlib
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from regulaforge.knowledge_graph.interfaces.cli import (
    _adapter_lifecycle,
    cmd_import,
    cmd_query,
    cmd_setup_schema,
    main,
)


@contextlib.asynccontextmanager
async def _mock_lifecycle(mock_adapter: Any):
    """Helper: mimic _adapter_lifecycle but yield the provided mock."""
    try:
        yield mock_adapter
    finally:
        pass


class TestMainFunction:
    @patch("regulaforge.knowledge_graph.interfaces.cli.configure_logging")
    def test_no_command_prints_help(self, mock_log: MagicMock, capsys: pytest.CaptureFixture[str]) -> None:
        with patch("sys.argv", ["cli"]):
            main()
        output = capsys.readouterr()
        assert "usage:" in output.out.lower() or "usage:" in output.err.lower()

    @patch("regulaforge.knowledge_graph.interfaces.cli.configure_logging")
    def test_setup_schema_routes(self, mock_log: MagicMock) -> None:
        with patch("sys.argv", ["cli", "setup-schema"]):
            with patch(
                "regulaforge.knowledge_graph.interfaces.cli.cmd_setup_schema",
                new_callable=AsyncMock,
            ) as mock_cmd:
                main()
                mock_cmd.assert_awaited_once()

    @patch("regulaforge.knowledge_graph.interfaces.cli.configure_logging")
    def test_import_routes(self, mock_log: MagicMock) -> None:
        with patch("sys.argv", ["cli", "import", "data.json"]):
            with patch(
                "regulaforge.knowledge_graph.interfaces.cli.cmd_import",
                new_callable=AsyncMock,
            ) as mock_cmd:
                main()
                mock_cmd.assert_awaited_once()

    @patch("regulaforge.knowledge_graph.interfaces.cli.configure_logging")
    def test_query_routes(self, mock_log: MagicMock) -> None:
        with patch("sys.argv", ["cli", "query", "MATCH (n) RETURN n LIMIT 5"]):
            with patch(
                "regulaforge.knowledge_graph.interfaces.cli.cmd_query",
                new_callable=AsyncMock,
            ) as mock_cmd:
                main()
                mock_cmd.assert_awaited_once()

    @patch("regulaforge.knowledge_graph.interfaces.cli.configure_logging")
    def test_diff_routes(self, mock_log: MagicMock) -> None:
        with patch("sys.argv", ["cli", "diff", "abc-123", "1", "2"]):
            with patch(
                "regulaforge.knowledge_graph.interfaces.cli.cmd_diff",
                new_callable=AsyncMock,
            ) as mock_cmd:
                main()
                mock_cmd.assert_awaited_once()

    @patch("regulaforge.knowledge_graph.interfaces.cli.configure_logging")
    def test_find_duplicates_routes(self, mock_log: MagicMock) -> None:
        with patch("sys.argv", ["cli", "find-duplicates"]):
            with patch(
                "regulaforge.knowledge_graph.interfaces.cli.cmd_find_duplicates",
                new_callable=AsyncMock,
            ) as mock_cmd:
                main()
                mock_cmd.assert_awaited_once()


class TestAdapterLifecycle:
    async def test_connects_and_disconnects(self) -> None:
        mock_adapter = MagicMock()
        mock_adapter.connect = AsyncMock()
        mock_adapter.disconnect = AsyncMock()

        with patch(
            "regulaforge.knowledge_graph.infrastructure.neo4j_adapter.Neo4jAdapter",
            return_value=mock_adapter,
        ):
            async with _adapter_lifecycle() as adapter:
                assert adapter is mock_adapter
                mock_adapter.connect.assert_awaited_once()
            mock_adapter.disconnect.assert_awaited_once()

    async def test_disconnects_on_error(self) -> None:
        mock_adapter = MagicMock()
        mock_adapter.connect = AsyncMock()
        mock_adapter.disconnect = AsyncMock()

        with patch(
            "regulaforge.knowledge_graph.infrastructure.neo4j_adapter.Neo4jAdapter",
            return_value=mock_adapter,
        ):
            with pytest.raises(RuntimeError, match="boom"):
                async with _adapter_lifecycle():
                    raise RuntimeError("boom")
            mock_adapter.disconnect.assert_awaited_once()


class TestCmdSetupSchema:
    async def test_calls_ensure_schema(self) -> None:
        mock_adapter = AsyncMock()
        mock_adapter.ensure_schema = AsyncMock(return_value={
            "success": True,
            "constraints_created": 4,
            "indexes_created": 6,
            "errors": [],
        })

        with patch(
            "regulaforge.knowledge_graph.interfaces.cli._adapter_lifecycle",
            lambda: _mock_lifecycle(mock_adapter),
        ):
            await cmd_setup_schema(MagicMock())
            mock_adapter.ensure_schema.assert_awaited_once()


class TestCmdQuery:
    async def test_calls_query_cypher(self) -> None:
        mock_adapter = AsyncMock()
        mock_adapter.query_cypher = AsyncMock(return_value=[{"n": {"id": "1"}}])

        with patch(
            "regulaforge.knowledge_graph.interfaces.cli._adapter_lifecycle",
            lambda: _mock_lifecycle(mock_adapter),
        ):
            args = MagicMock(cypher="MATCH (n) RETURN n")
            await cmd_query(args)
            mock_adapter.query_cypher.assert_awaited_once_with("MATCH (n) RETURN n")


class TestCmdImport:
    async def test_file_not_found_exits(self) -> None:
        args = MagicMock(file="nonexistent.json", source=None)
        with pytest.raises(SystemExit):
            await cmd_import(args)

    async def test_imports_data(self, tmp_path: pytest.TempPathFactory) -> None:
        data_file = tmp_path / "data.json"
        data_file.write_text('{"nodes": [{"id": "a", "node_type": "REGULATION", "labels": [], "properties": {"title": "T", "code": "C"}, "valid_from": "2024-01-01T00:00:00"}], "relationships": []}')
        args = MagicMock(file=str(data_file), source="test_cli")
        mock_adapter = AsyncMock()

        with patch(
            "regulaforge.knowledge_graph.interfaces.cli._adapter_lifecycle",
            lambda: _mock_lifecycle(mock_adapter),
        ):
            with patch(
                "regulaforge.knowledge_graph.application.graph_service.KnowledgeGraphService",
            ) as MockService:
                instance = MockService.return_value
                instance.merge_external_knowledge = AsyncMock(return_value={
                    "nodes_created": 1,
                    "relationships_created": 0,
                    "errors": [],
                    "error_count": 0,
                })
                await cmd_import(args)
                instance.merge_external_knowledge.assert_awaited_once()
