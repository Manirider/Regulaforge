from __future__ import annotations

from pathlib import Path

import pytest
from regulaforge.ingestion.storage.base import StorageIntegrityError, StorageNotFoundError
from regulaforge.ingestion.storage.local import LocalStorageBackend


class TestLocalStorageBackend:
    @pytest.fixture
    def backend(self, tmp_path: Path) -> LocalStorageBackend:
        return LocalStorageBackend(tmp_path / "store")

    @pytest.fixture
    def source_file(self, tmp_path: Path) -> Path:
        f = tmp_path / "source" / "doc.pdf"
        f.parent.mkdir(parents=True)
        f.write_bytes(b"pdf content here")
        return f

    @pytest.mark.asyncio
    async def test_store_new_file(self, backend: LocalStorageBackend, source_file: Path) -> None:
        result = await backend.store(source_file, "rbi/2024/doc.pdf")
        assert result.success
        assert result.path.exists()
        assert result.size_bytes > 0
        assert len(result.hash_value) == 64

    @pytest.mark.asyncio
    async def test_store_and_retrieve(self, backend: LocalStorageBackend, source_file: Path) -> None:
        await backend.store(source_file, "rbi/2024/doc.pdf")
        retrieved = await backend.retrieve("rbi/2024/doc.pdf")
        assert retrieved.exists()
        assert retrieved.read_bytes() == b"pdf content here"

    @pytest.mark.asyncio
    async def test_retrieve_nonexistent(self, backend: LocalStorageBackend) -> None:
        with pytest.raises(StorageNotFoundError):
            await backend.retrieve("nonexistent/file.pdf")

    @pytest.mark.asyncio
    async def test_exists(self, backend: LocalStorageBackend, source_file: Path) -> None:
        assert not await backend.exists("rbi/doc.pdf")
        await backend.store(source_file, "rbi/doc.pdf")
        assert await backend.exists("rbi/doc.pdf")

    @pytest.mark.asyncio
    async def test_delete(self, backend: LocalStorageBackend, source_file: Path) -> None:
        await backend.store(source_file, "rbi/doc.pdf")
        assert await backend.exists("rbi/doc.pdf")
        await backend.delete("rbi/doc.pdf")
        assert not await backend.exists("rbi/doc.pdf")

    @pytest.mark.asyncio
    async def test_store_with_hash_verification(self, backend: LocalStorageBackend, source_file: Path) -> None:
        result = await backend.store(source_file, "rbi/doc.pdf")
        verify_ok = await backend.verify("rbi/doc.pdf")
        assert verify_ok is True

    @pytest.mark.asyncio
    async def test_store_with_expected_hash(self, backend: LocalStorageBackend, source_file: Path) -> None:
        result = await backend.store(source_file, "rbi/doc.pdf")
        with pytest.raises(StorageIntegrityError):
            await backend.store(source_file, "rbi/doc2.pdf", expected_hash="badhash")

    @pytest.mark.asyncio
    async def test_store_overwrite_no_change(self, backend: LocalStorageBackend, source_file: Path) -> None:
        await backend.store(source_file, "rbi/doc.pdf")
        result = await backend.store(source_file, "rbi/doc.pdf", overwrite=True)
        assert result.success

    @pytest.mark.asyncio
    async def test_path_traversal_prevented(self, backend: LocalStorageBackend, source_file: Path) -> None:
        with pytest.raises(StorageNotFoundError):
            await backend.store(source_file, "../../etc/passwd")

    @pytest.mark.asyncio
    async def test_verify_nonexistent_file(self, backend: LocalStorageBackend) -> None:
        assert await backend.verify("nonexistent") is False

    @pytest.mark.asyncio
    async def test_delete_nonexistent(self, backend: LocalStorageBackend) -> None:
        await backend.delete("nonexistent")

    @pytest.mark.asyncio
    async def test_store_nested_directory_created(self, backend: LocalStorageBackend, source_file: Path) -> None:
        result = await backend.store(source_file, "a/b/c/d/doc.pdf")
        assert result.success
        assert result.path.exists()

    @pytest.mark.asyncio
    async def test_retrieve_returns_absolute_path(self, backend: LocalStorageBackend, source_file: Path) -> None:
        await backend.store(source_file, "rbi/doc.pdf")
        retrieved = await backend.retrieve("rbi/doc.pdf")
        assert retrieved.is_absolute()

    @pytest.mark.asyncio
    async def test_store_same_content_no_overwrite_no_error(self, backend: LocalStorageBackend, tmp_path: Path) -> None:
        f1 = tmp_path / "source1.pdf"
        f1.write_bytes(b"same content")
        f2 = tmp_path / "source2.pdf"
        f2.write_bytes(b"same content")
        await backend.store(f1, "rbi/doc.pdf")
        result = await backend.store(f2, "rbi/doc.pdf", overwrite=False)
        assert result.success
