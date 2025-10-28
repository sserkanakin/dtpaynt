import csv
import os
import threading
from typing import Dict, Iterable, Optional


class CsvProgressLogger:
	"""Append-only CSV writer for synthesis progress rows."""

	def __init__(self, file_path: str, fieldnames: Iterable[str]):
		self._file_path = file_path
		self._fieldnames = list(fieldnames)
		self._lock = threading.Lock()
		self._ensure_header()

	def _ensure_header(self) -> None:
		directory = os.path.dirname(self._file_path)
		if directory:
			os.makedirs(directory, exist_ok=True)
		if not os.path.exists(self._file_path):
			with open(self._file_path, "w", newline="", encoding="utf-8") as stream:
				writer = csv.DictWriter(stream, fieldnames=self._fieldnames)
				writer.writeheader()

	def write_row(self, row: Dict[str, Optional[object]]) -> None:
		filtered = {key: row.get(key) for key in self._fieldnames}
		with self._lock:
			with open(self._file_path, "a", newline="", encoding="utf-8") as stream:
				writer = csv.DictWriter(stream, fieldnames=self._fieldnames)
				writer.writerow(filtered)
