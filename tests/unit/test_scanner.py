import pytest
from pathlib import Path
from ai_context_studio.core.scanner import FastFileScanner
from ai_context_studio.core.models import ScanResult
from ai_context_studio.config.settings import DEFAULT_IGNORED_DIRS, SUPPORTED_EXTENSIONS

class TestFastFileScanner:
    @pytest.fixture
    def scanner(self):
        return FastFileScanner()

    def test_initialization(self, scanner):
        assert scanner._progress_callback is None
        assert not scanner._cancel_flag.is_set()

    def test_scan_includes_supported_extensions(self, scanner, tmp_path):
        # Create a file with a supported extension (e.g., .py)
        (tmp_path / "test.py").touch()
        # Create a file with an unsupported extension (e.g., .xyz)
        (tmp_path / "test.xyz").touch()

        result = scanner.scan(tmp_path)

        assert isinstance(result, ScanResult)
        # Should find only test.py
        assert len(result.files) == 1
        assert result.files[0].extension == ".py"
        assert result.files[0].relative_path == "test.py"

    def test_scan_excludes_ignored_dirs(self, scanner, tmp_path):
        # Create a supported file in root
        (tmp_path / "root.py").touch()

        # Create an ignored directory
        ignored_dir = tmp_path / "node_modules"
        ignored_dir.mkdir()
        (ignored_dir / "ignored.js").touch()

        # Create a normal directory
        normal_dir = tmp_path / "src"
        normal_dir.mkdir()
        (normal_dir / "included.js").touch()

        result = scanner.scan(tmp_path)

        # Should find root.py and src/included.js, but NOT node_modules/ignored.js
        filenames = {f.relative_path for f in result.files}
        expected_filenames = {"root.py", str(Path("src/included.js"))}

        assert filenames == expected_filenames
        assert len(result.files) == 2

    def test_scan_excludes_hidden_files(self, scanner, tmp_path):
        # Create a hidden file
        (tmp_path / ".hidden.py").touch()
        # Create a normal file
        (tmp_path / "normal.py").touch()

        result = scanner.scan(tmp_path)

        assert len(result.files) == 1
        assert result.files[0].relative_path == "normal.py"

    def test_scan_skips_large_files(self, scanner, tmp_path):
        # Create a large file (> 1MB)
        large_file = tmp_path / "large.py"
        # Write 1MB + 1 byte
        with open(large_file, "wb") as f:
            f.seek(1_000_000)
            f.write(b"0")

        # Create a small file
        (tmp_path / "small.py").touch()

        result = scanner.scan(tmp_path)

        assert len(result.files) == 1
        assert result.files[0].relative_path == "small.py"
