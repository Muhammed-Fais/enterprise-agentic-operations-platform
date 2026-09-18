from dataclasses import dataclass
from pathlib import Path

from pypdf import PdfReader


@dataclass(frozen=True)
class LoadedDocument:
    external_id: str
    title: str
    source: str
    content: str


def load_file(path: str | Path) -> LoadedDocument:
    file_path = Path(path)
    suffix = file_path.suffix.lower()

    if suffix in {".md", ".markdown", ".txt"}:
        content = file_path.read_text(encoding="utf-8")
    elif suffix == ".pdf":
        reader = PdfReader(str(file_path))
        content = "\n\n".join(page.extract_text() or "" for page in reader.pages)
    else:
        raise ValueError(f"unsupported document type: {suffix or '<none>'}")

    content = content.strip()
    if not content:
        raise ValueError(f"document is empty: {file_path}")
    return LoadedDocument(
        external_id=str(file_path.resolve()),
        title=file_path.stem,
        source=str(file_path),
        content=content,
    )
