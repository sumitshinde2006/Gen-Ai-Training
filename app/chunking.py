"""Extract and chunk KandaGuide source documents with their provenance."""

import hashlib
import re
from pathlib import Path
from typing import TypedDict

from bs4 import BeautifulSoup
from pypdf import PdfReader

PROJECT_ROOT = Path(__file__).resolve().parents[1]
RAW_DIR = PROJECT_ROOT / "data" / "raw"
DEFAULT_CHUNK_SIZE = 500
DEFAULT_OVERLAP = 75

DOCUMENT_SOURCES = {
    "dogr_varieties.html": (
        "https://www.dogr.res.in/index.php/research/"
        "varieties-developed?layout=edit"
    ),
    "dogr_garlic.html": (
        "https://dogr.res.in/index.php/component/content/"
        "article/garlicagropedia?layout=edit"
    ),
    "manage_onion_garlic.pdf": (
        "https://www.manage.gov.in/publications/eBooks/"
        "Good%20Agricultural%20Practices%20in%20Onion%20and%20Garlic.pdf"
    ),
}

_SENTENCE_BOUNDARY = re.compile(r"(?<=[.!?])\s+(?=[A-Z0-9])")
_WHITESPACE = re.compile(r"\s+")


class DocumentChunk(TypedDict):
    chunk_id: str
    text: str
    source: str
    page: int | None
    title: str


def list_document_paths(raw_dir: Path = RAW_DIR) -> list[Path]:
    """Return supported source documents in stable path order."""
    if not raw_dir.exists():
        return []
    return sorted(
        (
            path
            for path in raw_dir.iterdir()
            if path.is_file() and path.suffix.lower() in {".html", ".pdf"}
        ),
        key=lambda path: path.name.casefold(),
    )


def _source_for(path: Path) -> str:
    source = DOCUMENT_SOURCES.get(path.name)
    if source:
        return source
    return path.resolve().as_uri()


def _html_document(path: Path) -> tuple[str, list[str]]:
    html = path.read_text(encoding="utf-8", errors="replace")
    soup = BeautifulSoup(html, "html.parser")
    title = ""
    if soup.title:
        title = soup.title.get_text(" ", strip=True)
    if not title:
        heading = soup.find(["h1", "h2"])
        if heading:
            title = heading.get_text(" ", strip=True)
    if not title:
        title = path.stem.replace("_", " ").strip()

    for element in soup(["script", "style", "noscript", "nav", "footer", "aside"]):
        element.decompose()

    content = soup.find("main") or soup.find("article") or soup.body or soup
    heading = content.find(["h1", "h2"])
    section_title = heading.get_text(" ", strip=True) if heading else ""
    cards = content.select(".variety-card")
    if cards:
        blocks = []
        for card in cards:
            card_text = card.get_text("\n", strip=True)
            if section_title:
                card_text = f"{section_title}\n{card_text}"
            blocks.append(card_text)
        return title, blocks

    return title, [content.get_text("\n", strip=True)]


def _pdf_title(reader: PdfReader, path: Path) -> str:
    metadata_title = getattr(reader.metadata, "title", None) if reader.metadata else None
    if metadata_title and metadata_title.strip():
        return metadata_title.strip()

    for page in reader.pages:
        lines = [
            line.strip()
            for line in (page.extract_text() or "").splitlines()
            if line.strip()
        ]
        if lines:
            if len(lines) > 1 and len(" ".join(lines[:2]).split()) <= 18:
                return " ".join(lines[:2])
            return lines[0]
    return path.stem.replace("_", " ").strip()


def _sentences(text: str) -> list[str]:
    normalized = _WHITESPACE.sub(" ", text).strip()
    if not normalized:
        return []
    return [
        sentence.strip()
        for sentence in _SENTENCE_BOUNDARY.split(normalized)
        if sentence.strip()
    ]


def _make_text_chunks(
    text: str, chunk_size: int, overlap: int
) -> list[str]:
    sentences = _sentences(text)
    chunks: list[str] = []
    start = 0

    while start < len(sentences):
        current: list[str] = []
        word_count = 0
        end = start

        while end < len(sentences):
            sentence = sentences[end]
            sentence_words = sentence.split()
            if len(sentence_words) > chunk_size:
                if current:
                    break
                step = chunk_size - overlap
                for offset in range(0, len(sentence_words), step):
                    piece = " ".join(sentence_words[offset:offset + chunk_size])
                    if piece:
                        chunks.append(piece)
                end += 1
                break

            if current and word_count + len(sentence_words) > chunk_size:
                break
            current.append(sentence)
            word_count += len(sentence_words)
            end += 1

        if current:
            chunks.append(" ".join(current))

        if end >= len(sentences):
            break
        if end == start:
            start += 1
            continue

        next_start = end
        overlap_words = 0
        while next_start > start and overlap_words < overlap:
            next_start -= 1
            overlap_words += len(sentences[next_start].split())
        start = next_start if next_start > start else end

    return chunks


def _chunk_id(source: str, page: int | None, position: int, text: str) -> str:
    identity = f"{source}\0{page}\0{position}\0{text}"
    return hashlib.sha256(identity.encode("utf-8")).hexdigest()


def chunk_document(
    path: Path,
    chunk_size: int = DEFAULT_CHUNK_SIZE,
    overlap: int = DEFAULT_OVERLAP,
) -> list[DocumentChunk]:
    """Extract one HTML or PDF document and return provenance-bearing chunks."""
    if chunk_size < 1:
        raise ValueError("chunk_size must be greater than zero.")
    if overlap < 0 or overlap >= chunk_size:
        raise ValueError("overlap must be between zero and chunk_size - 1.")
    if not path.is_file():
        raise FileNotFoundError(f"Source document does not exist: {path}")

    source = _source_for(path)
    page_texts: list[tuple[int | None, str]] = []

    if path.suffix.lower() == ".html":
        title, blocks = _html_document(path)
        page_texts.extend((None, text) for text in blocks)
    elif path.suffix.lower() == ".pdf":
        reader = PdfReader(str(path))
        title = _pdf_title(reader, path)
        for page_number, page in enumerate(reader.pages, start=1):
            text = page.extract_text() or ""
            if text.strip():
                page_texts.append((page_number, text))
    else:
        raise ValueError(f"Unsupported source document type: {path.suffix}")

    chunks: list[DocumentChunk] = []
    positions: dict[int | None, int] = {}
    for page_number, text in page_texts:
        for chunk_text in _make_text_chunks(text, chunk_size, overlap):
            position = positions.get(page_number, 0)
            positions[page_number] = position + 1
            chunks.append(
                {
                    "chunk_id": _chunk_id(source, page_number, position, chunk_text),
                    "text": chunk_text,
                    "source": source,
                    "page": page_number,
                    "title": title,
                }
            )
    return chunks


def chunk_documents(
    raw_dir: Path = RAW_DIR,
    chunk_size: int = DEFAULT_CHUNK_SIZE,
    overlap: int = DEFAULT_OVERLAP,
) -> list[DocumentChunk]:
    """Extract all supported HTML/PDF sources in ``raw_dir``."""
    chunks: list[DocumentChunk] = []
    for path in list_document_paths(raw_dir):
        chunks.extend(chunk_document(path, chunk_size, overlap))
    return chunks
