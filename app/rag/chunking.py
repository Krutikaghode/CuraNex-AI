"""Split extracted report text into overlapping, page-aware chunks."""

import re
from dataclasses import dataclass

_PAGE_MARKER = re.compile(r"^--- Page (\d+) ---$", re.M)


@dataclass(frozen=True)
class Chunk:
    index: int
    page: int | None
    text: str


def _pages(text: str) -> list[tuple[int | None, str]]:
    markers = list(_PAGE_MARKER.finditer(text))
    if not markers:
        return [(None, text)]
    pages = []
    for position, marker in enumerate(markers):
        end = markers[position + 1].start() if position + 1 < len(markers) else len(text)
        pages.append((int(marker.group(1)), text[marker.end() : end]))
    return pages


def _split(text: str, size: int, overlap: int) -> list[str]:
    """Greedy split on line boundaries; a single over-long line is hard-wrapped."""
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    pieces: list[str] = []
    current = ""
    for line in lines:
        while len(line) > size:
            head, line = line[:size], line[size - overlap :]
            if current:
                pieces.append(current)
                current = ""
            pieces.append(head)
        candidate = f"{current}\n{line}" if current else line
        if len(candidate) <= size:
            current = candidate
            continue
        pieces.append(current)
        tail = current[-overlap:] if overlap else ""
        tail = tail.split("\n", 1)[-1] if "\n" in tail else tail
        current = f"{tail}\n{line}".strip() if tail else line
    if current:
        pieces.append(current)
    return pieces


def chunk_text(text: str, size: int = 900, overlap: int = 150) -> list[Chunk]:
    if overlap >= size:
        raise ValueError("overlap must be smaller than size")
    chunks: list[Chunk] = []
    for page, page_text in _pages(text):
        for piece in _split(page_text, size, overlap):
            chunks.append(Chunk(index=len(chunks), page=page, text=piece))
    return chunks
