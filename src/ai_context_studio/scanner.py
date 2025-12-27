# -*- coding: utf-8 -*-
"""
Fast file scanner for AI Context Studio.

This module provides efficient directory scanning functionality
with support for progress callbacks and cancellation.
"""

from __future__ import annotations

import logging
import os
import threading
from pathlib import Path
from typing import Callable, Optional

from .constants import (
    DEFAULT_IGNORED_DIRS,
    MAX_FILE_SIZE,
    MAX_SCAN_DEPTH,
    SUPPORTED_EXTENSIONS,
    TOKEN_FACTOR,
)
from .models import ExistingDoc, FileInfo, GenerationType, ScanResult

logger = logging.getLogger(__name__)

# Type alias for progress callbacks
ProgressCallback = Callable[[str, int], None]

# Documentation file patterns to detect
DOC_FILENAMES = {gt.filename for gt in GenerationType}
COMMON_DOC_FILES = {
    'README.md', 'CHANGELOG.md', 'CONTRIBUTING.md', 'LICENSE.md',
    'ARCHITECTURE.md', 'DOCS.md', 'DOCUMENTATION.md', 'API.md',
    'SECURITY.md', 'TESTING.md', 'DEPLOYMENT.md', 'INSTALL.md',
}
DOC_FOLDERS = {'docs', 'doc', 'documentation', 'wiki'}


class FastFileScanner:
    """
    Optimized file scanner for code projects.

    Scans directories recursively to find source code files,
    with support for:
    - Progress callbacks for UI updates
    - Cancellation support
    - Configurable ignored directories
    - File size limits

    Attributes:
        _cancel_flag: Threading event for cancellation
        _progress_callback: Optional callback for progress updates
    """

    def __init__(self) -> None:
        """Initialize the scanner."""
        self._cancel_flag = threading.Event()
        self._progress_callback: Optional[ProgressCallback] = None

    def set_progress_callback(self, callback: ProgressCallback) -> None:
        """
        Set the progress callback function.

        Args:
            callback: Function taking (message: str, percent: int)
        """
        self._progress_callback = callback

    def cancel(self) -> None:
        """Request cancellation of the current scan."""
        self._cancel_flag.set()
        logger.debug("Scan cancellation requested")

    def scan(self, root_path: Path) -> ScanResult:
        """
        Scan a directory for source code files.

        Args:
            root_path: Root directory to scan.

        Returns:
            ScanResult containing found files and statistics.
        """
        self._cancel_flag.clear()
        result = ScanResult(root_path=root_path)

        logger.info("Starting scan of: %s", root_path)
        self._report_progress("\U0001F50D Scansione in corso...", 0)

        files_found: list[FileInfo] = []
        self._scan_dir(root_path, root_path, files_found)

        if self._cancel_flag.is_set():
            logger.info("Scan cancelled, found %d files", len(files_found))
            return result

        result.files = files_found
        result.total_size = sum(f.size for f in files_found if f.included)
        result.estimated_tokens = result.total_size // TOKEN_FACTOR

        logger.info(
            "Scan complete: %d files, %d bytes, ~%d tokens",
            len(files_found),
            result.total_size,
            result.estimated_tokens
        )
        self._report_progress(f"\u2705 {len(files_found)} file trovati", 100)

        return result

    def _scan_dir(
        self,
        current: Path,
        root: Path,
        files: list[FileInfo],
        depth: int = 0
    ) -> None:
        """
        Recursively scan a directory.

        Args:
            current: Current directory being scanned.
            root: Original root directory (for relative paths).
            files: List to append found files to.
            depth: Current recursion depth.
        """
        if self._cancel_flag.is_set():
            return

        if depth > MAX_SCAN_DEPTH:
            logger.warning("Max depth reached at: %s", current)
            return

        try:
            with os.scandir(current) as entries:
                for entry in entries:
                    if self._cancel_flag.is_set():
                        return

                    self._process_entry(entry, root, files, depth)

        except PermissionError:
            logger.debug("Permission denied: %s", current)
        except OSError as e:
            logger.warning("Error scanning %s: %s", current, e)

    def _process_entry(
        self,
        entry: os.DirEntry,
        root: Path,
        files: list[FileInfo],
        depth: int
    ) -> None:
        """
        Process a single directory entry.

        Args:
            entry: Directory entry to process.
            root: Root directory for relative paths.
            files: List to append found files to.
            depth: Current recursion depth.
        """
        name = entry.name

        # Skip hidden files (except specific ones)
        if name.startswith('.') and name not in {'.env.example'}:
            return

        try:
            if entry.is_dir(follow_symlinks=False):
                if name not in DEFAULT_IGNORED_DIRS:
                    self._scan_dir(Path(entry.path), root, files, depth + 1)

            elif entry.is_file(follow_symlinks=False):
                self._process_file(entry, root, files)

        except OSError as e:
            logger.debug("Error processing %s: %s", entry.path, e)

    def _process_file(
        self,
        entry: os.DirEntry,
        root: Path,
        files: list[FileInfo]
    ) -> None:
        """
        Process a file entry if it matches criteria.

        Args:
            entry: File entry to process.
            root: Root directory for relative paths.
            files: List to append file info to.
        """
        ext = Path(entry.name).suffix.lower()

        if ext not in SUPPORTED_EXTENSIONS:
            return

        try:
            stat = entry.stat()

            # Skip files that are too large
            if stat.st_size > MAX_FILE_SIZE:
                logger.debug("Skipping large file: %s", entry.path)
                return

            rel_path = str(Path(entry.path).relative_to(root))

            files.append(FileInfo(
                path=Path(entry.path),
                relative_path=rel_path,
                size=stat.st_size,
                extension=ext,
                included=True
            ))

        except OSError as e:
            logger.debug("Error getting file stats for %s: %s", entry.path, e)

    def read_files(
        self,
        result: ScanResult,
        progress_callback: Optional[ProgressCallback] = None
    ) -> None:
        """
        Read contents of included files into the result.

        Args:
            result: ScanResult to populate with file contents.
            progress_callback: Optional callback for progress updates.
        """
        included = [f for f in result.files if f.included]
        total = len(included)

        logger.info("Reading %d files", total)

        for idx, file_info in enumerate(included):
            if self._cancel_flag.is_set():
                logger.info("File reading cancelled")
                break

            content = self._read_file_safe(file_info.path)
            if content:
                result.content_map[file_info.relative_path] = content

            if progress_callback and idx % 5 == 0:
                pct = int((idx / total) * 100) if total > 0 else 100
                progress_callback(
                    f"\U0001F4D6 Lettura {idx + 1}/{total}...",
                    pct
                )

        if progress_callback:
            progress_callback("\u2705 Lettura completata", 100)

        logger.info("Read %d files", len(result.content_map))

    def _read_file_safe(self, path: Path) -> Optional[str]:
        """
        Safely read a file with multiple encoding attempts.

        Args:
            path: Path to the file to read.

        Returns:
            File contents as string, or None if reading failed.
        """
        encodings = ['utf-8', 'latin-1', 'cp1252']

        for encoding in encodings:
            try:
                return path.read_text(encoding=encoding)
            except UnicodeDecodeError:
                continue
            except OSError as e:
                logger.debug("Error reading %s: %s", path, e)
                return None

        logger.warning("Could not decode file: %s", path)
        return None

    def _report_progress(self, message: str, percent: int) -> None:
        """
        Report progress if callback is set.

        Args:
            message: Progress message.
            percent: Completion percentage (0-100).
        """
        if self._progress_callback:
            self._progress_callback(message, percent)

    def detect_existing_docs(self, result: ScanResult) -> None:
        """
        Detect existing documentation files in the project.

        Scans for:
        - Files matching GenerationType filenames
        - Common documentation files (README, CHANGELOG, etc.)
        - Documentation in common doc folders

        Args:
            result: ScanResult to populate with existing docs.
        """
        root = result.root_path
        logger.info("Detecting existing documentation in: %s", root)

        # Locations to search for docs
        search_paths = [root]
        for folder in DOC_FOLDERS:
            doc_path = root / folder
            if doc_path.exists() and doc_path.is_dir():
                search_paths.append(doc_path)

        found_docs: dict[str, ExistingDoc] = {}

        for search_path in search_paths:
            self._scan_for_docs(search_path, root, found_docs)

        result.existing_docs = found_docs
        logger.info("Found %d existing documentation files", len(found_docs))

    def _scan_for_docs(
        self,
        search_path: Path,
        root: Path,
        found_docs: dict[str, ExistingDoc]
    ) -> None:
        """
        Scan a directory for documentation files.

        Args:
            search_path: Directory to scan.
            root: Project root for relative paths.
            found_docs: Dictionary to populate with found docs.
        """
        try:
            for entry in os.scandir(search_path):
                if not entry.is_file():
                    continue

                name = entry.name
                if not name.lower().endswith('.md'):
                    continue

                # Check if it's a known doc file
                is_known = (
                    name in DOC_FILENAMES or
                    name in COMMON_DOC_FILES or
                    name.upper() in DOC_FILENAMES or
                    name.upper() in COMMON_DOC_FILES
                )

                if is_known or search_path != root:
                    # Include all .md in doc folders, only known ones in root
                    self._add_existing_doc(entry, root, found_docs)

        except OSError as e:
            logger.debug("Error scanning for docs in %s: %s", search_path, e)

    def _add_existing_doc(
        self,
        entry: os.DirEntry,
        root: Path,
        found_docs: dict[str, ExistingDoc]
    ) -> None:
        """
        Add a documentation file to the found docs.

        Args:
            entry: File entry to add.
            root: Project root for relative paths.
            found_docs: Dictionary to add the doc to.
        """
        try:
            path = Path(entry.path)
            rel_path = str(path.relative_to(root))
            filename = entry.name

            # Read content
            content = self._read_file_safe(path) or ""

            # Check if potentially outdated (simple heuristics)
            is_outdated = self._check_if_outdated(content, filename)

            doc = ExistingDoc(
                path=path,
                relative_path=rel_path,
                filename=filename,
                content=content,
                is_outdated=is_outdated
            )

            # Use filename as key for easy lookup
            found_docs[filename] = doc
            logger.debug("Found existing doc: %s (outdated: %s)", rel_path, is_outdated)

        except OSError as e:
            logger.debug("Error adding doc %s: %s", entry.path, e)

    def _check_if_outdated(self, content: str, filename: str) -> bool:
        """
        Check if a documentation file appears outdated.

        Uses heuristics like:
        - Very short content
        - Placeholder text
        - Old date references

        Args:
            content: File content to check.
            filename: Name of the file.

        Returns:
            True if the file appears outdated.
        """
        if not content:
            return True

        # Very short docs are likely outdated/incomplete
        if len(content) < 200:
            return True

        content_lower = content.lower()

        # Check for placeholder indicators
        placeholders = [
            'todo:', 'fixme:', 'coming soon', 'work in progress',
            'wip', 'placeholder', 'to be documented', 'tbd',
            '[inserisci', '[aggiungi', '[da completare'
        ]
        for placeholder in placeholders:
            if placeholder in content_lower:
                return True

        return False
