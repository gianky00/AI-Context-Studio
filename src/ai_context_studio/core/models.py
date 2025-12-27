from enum import Enum, auto
from dataclasses import dataclass, field
from pathlib import Path

class GenerationType(Enum):
    """Tipi di generazione documenti supportati."""
    ARCHITECTURE = auto()
    RULES = auto()
    CONTEXT = auto()
    BUNDLE = auto()


@dataclass
class FileInfo:
    """Informazioni su un singolo file."""
    path: Path
    relative_path: str
    size: int
    extension: str
    included: bool = True


@dataclass
class ScanResult:
    """Risultato della scansione del repository."""
    root_path: Path
    files: list[FileInfo] = field(default_factory=list)
    total_size: int = 0
    estimated_tokens: int = 0
    content_map: dict[str, str] = field(default_factory=dict)


@dataclass
class GenerationResult:
    """Risultato di una generazione documento."""
    success: bool
    doc_type: GenerationType
    content: str = ""
    filename: str = ""
    error_message: str = ""
    tokens_used: int = 0
    generation_time: float = 0.0
