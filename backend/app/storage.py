"""Filesystem storage for the single-worker deployment."""
import json
import os
from pathlib import Path
from tempfile import NamedTemporaryFile
from uuid import UUID

from app.models import InvoiceData


def write_json(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with NamedTemporaryFile(mode="w", encoding="utf-8", dir=path.parent, delete=False) as file:
        temporary = Path(file.name)
        try:
            json.dump(value, file, ensure_ascii=False)
            file.flush()
            os.fsync(file.fileno())
            file.close()
            os.replace(temporary, path)
        finally:
            temporary.unlink(missing_ok=True)


class BatchStore:
    def __init__(self, directory: Path):
        self.directory = directory

    def _path(self, key: str) -> Path:
        try:
            if str(UUID(key)) != key:
                raise ValueError(key)
        except ValueError as error:
            raise KeyError(key) from error
        return self.directory / f"{key}.json"

    def __contains__(self, key: str) -> bool:
        try:
            return self._path(key).is_file()
        except KeyError:
            return False

    def __getitem__(self, key: str) -> list[InvoiceData]:
        try:
            data = json.loads(self._path(key).read_text(encoding="utf-8"))
        except FileNotFoundError as error:
            raise KeyError(key) from error
        return [InvoiceData.model_validate(invoice) for invoice in data]

    def __setitem__(self, key: str, invoices: list[InvoiceData]) -> None:
        write_json(self._path(key), [invoice.model_dump(mode="json") for invoice in invoices])

    def items(self):
        paths = sorted(self.directory.glob("*.json"), key=lambda path: path.stat().st_mtime, reverse=True)
        for path in paths:
            yield path.stem, self[path.stem]
