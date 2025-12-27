import os
import threading
from pathlib import Path
from typing import Optional, Callable

from ..config.settings import DEFAULT_IGNORED_DIRS, SUPPORTED_EXTENSIONS, TOKEN_FACTOR
from .models import ScanResult, FileInfo

class FastFileScanner:
    """
    Scanner ottimizzato per performance.
    Usa os.scandir() invece di os.walk() per maggiore velocità.
    """

    def __init__(self):
        self._cancel_flag = threading.Event()
        self._progress_callback: Optional[Callable[[str], None]] = None

    def set_progress_callback(self, callback: Callable[[str], None]) -> None:
        self._progress_callback = callback

    def cancel(self) -> None:
        self._cancel_flag.set()

    def scan(self, root_path: Path) -> ScanResult:
        """Scansione veloce del repository."""
        self._cancel_flag.clear()
        result = ScanResult(root_path=root_path)

        self._report_progress("Scansione file in corso...")

        # Scansione veloce con os.scandir
        files_found = []
        self._scan_dir(root_path, root_path, files_found)

        if self._cancel_flag.is_set():
            return result

        result.files = files_found

        # Calcola statistiche
        result.total_size = sum(f.size for f in files_found if f.included)
        result.estimated_tokens = result.total_size // TOKEN_FACTOR

        self._report_progress(f"Trovati {len(files_found)} file analizzabili")

        return result

    def _scan_dir(self, current: Path, root: Path, files: list[FileInfo], depth: int = 0) -> None:
        """Scansione ricorsiva ottimizzata."""
        if self._cancel_flag.is_set() or depth > 20:
            return

        try:
            with os.scandir(current) as entries:
                for entry in entries:
                    if self._cancel_flag.is_set():
                        return

                    name = entry.name

                    # Skip hidden files/dirs
                    if name.startswith('.') and name not in {'.env.example'}:
                        continue

                    if entry.is_dir(follow_symlinks=False):
                        # Skip ignored directories
                        if name in DEFAULT_IGNORED_DIRS:
                            continue
                        self._scan_dir(Path(entry.path), root, files, depth + 1)

                    elif entry.is_file(follow_symlinks=False):
                        ext = Path(name).suffix.lower()
                        if ext in SUPPORTED_EXTENSIONS:
                            try:
                                stat = entry.stat()
                                # Skip file troppo grandi (>1MB)
                                if stat.st_size > 1_000_000:
                                    continue

                                rel_path = str(Path(entry.path).relative_to(root))
                                files.append(FileInfo(
                                    path=Path(entry.path),
                                    relative_path=rel_path,
                                    size=stat.st_size,
                                    extension=ext,
                                    included=True
                                ))
                            except OSError:
                                pass
        except PermissionError:
            pass

    def read_files(self, result: ScanResult) -> None:
        """Legge il contenuto dei file inclusi."""
        self._report_progress("Lettura contenuto file...")

        included = [f for f in result.files if f.included]
        total = len(included)

        for idx, file_info in enumerate(included):
            if self._cancel_flag.is_set():
                break

            content = self._read_file_safe(file_info.path)
            if content:
                result.content_map[file_info.relative_path] = content

            if idx % 10 == 0:
                self._report_progress(f"Lettura file {idx+1}/{total}...")

        self._report_progress("Lettura completata!")

    def _read_file_safe(self, path: Path) -> Optional[str]:
        """Legge file con gestione errori encoding."""
        encodings = ['utf-8', 'latin-1', 'cp1252']

        for encoding in encodings:
            try:
                return path.read_text(encoding=encoding)
            except UnicodeDecodeError:
                continue
            except Exception:
                return None
        return None

    def _report_progress(self, message: str) -> None:
        if self._progress_callback:
            self._progress_callback(message)
