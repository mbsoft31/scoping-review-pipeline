"""BibTeX export functionality for academic papers.

This module defines a `BibTeXExporter` class that converts a collection of
`Paper` instances into a properly formatted BibTeX file. It handles
generation of unique citation keys, formatting of author names, escaping of
special characters, and mapping of paper types to BibTeX entry types.

Example usage:

    exporter = BibTeXExporter()
    exporter.export(papers, Path("references.bib"), top_n=100)

"""

from __future__ import annotations

import re
from pathlib import Path
from typing import List, Optional
from datetime import datetime

from ..core.models import Paper, Author
from ..utils.logging import get_logger


logger = get_logger(__name__)


class BibTeXExporter:
    """
    Export a list of papers to BibTeX format.

    The exporter generates unique citation keys based on the first author,
    publication year, and first significant word of the title. It sanitizes
    strings for LaTeX compatibility and attempts to map paper types to
    appropriate BibTeX entry types.
    """

    # Mapping from paper type (Crossref/S2) to BibTeX entry type
    ENTRY_TYPES = {
        "journal-article": "article",
        "proceedings-article": "inproceedings",
        "book-chapter": "inbook",
        "book": "book",
        "dissertation": "phdthesis",
        "report": "techreport",
    }

    def __init__(self) -> None:
        self._used_keys: set[str] = set()

    def _sanitize_bibtex_string(self, text: str) -> str:
        """Escape special characters for BibTeX."""
        if not text:
            return ""
        replacements = {
            "&": r"\&",
            "%": r"\%",
            "$": r"\$",
            "#": r"\#",
            "_": r"\_",
            "{": r"\{",
            "}": r"\}",
            "~": r"\textasciitilde{}",
            "^": r"\^{}",
        }
        for char, replacement in replacements.items():
            text = text.replace(char, replacement)
        return text

    def _format_authors(self, authors: List[Author]) -> str:
        """Format authors as "Last, First and Last, First" for BibTeX."""
        if not authors:
            return ""
        formatted: List[str] = []
        for author in authors:
            name = author.name.strip()
            parts = name.split()
            if len(parts) >= 2:
                family = parts[-1]
                given = " ".join(parts[:-1])
                formatted.append(f"{family}, {given}")
            else:
                formatted.append(name)
        return " and ".join(formatted)

    def _generate_cite_key(self, paper: Paper) -> str:
        """Generate a unique citation key for a paper."""
        # First author last name
        author_part = "unknown"
        if paper.authors:
            name_parts = paper.authors[0].name.strip().split()
            if name_parts:
                author_part = name_parts[-1].lower()
        # Year
        year_part = str(paper.year) if paper.year else "n.d."
        # First significant word of title
        title_first_word = "untitled"
        if paper.title:
            # Remove non‑alphanumeric and split
            cleaned = re.sub(r"[^a-zA-Z0-9 ]", "", paper.title).strip().split()
            if cleaned:
                title_first_word = cleaned[0].lower()
        key = f"{author_part}_{year_part}_{title_first_word}"
        # Ensure uniqueness by appending letters if necessary
        suffix = ""
        base_key = key
        counter = ord("a")
        while key + suffix in self._used_keys:
            suffix = chr(counter)
            counter += 1
        unique_key = key + suffix
        self._used_keys.add(unique_key)
        return unique_key

    def _determine_entry_type(self, paper: Paper) -> str:
        """Map paper type to BibTeX entry type, defaulting to 'misc'."""
        # Use Crossref type if available in raw data
        raw_type = None
        if paper.raw_data and isinstance(paper.raw_data, dict):
            raw_type = paper.raw_data.get("type")
        if raw_type and raw_type in self.ENTRY_TYPES:
            return self.ENTRY_TYPES[raw_type]
        # Fallback: thesis if venue looks like "dissertation" or "phd"
        venue_lower = (paper.venue or "").lower()
        if "thesis" in venue_lower or "dissertation" in venue_lower:
            return "phdthesis"
        # Articles by default
        return "article"

    def _build_bibtex_entry(self, paper: Paper) -> str:
        """Construct a BibTeX entry for a single paper."""
        entry_type = self._determine_entry_type(paper)
        cite_key = self._generate_cite_key(paper)
        fields = {}
        # Common fields
        fields["title"] = self._sanitize_bibtex_string(paper.title)
        if paper.authors:
            fields["author"] = self._sanitize_bibtex_string(self._format_authors(paper.authors))
        if paper.year:
            fields["year"] = str(paper.year)
        if paper.venue:
            fields["journal" if entry_type == "article" else "booktitle"] = self._sanitize_bibtex_string(paper.venue)
        if paper.publisher:
            fields["publisher"] = self._sanitize_bibtex_string(paper.publisher)
        if paper.doi:
            fields["doi"] = paper.doi
        if paper.open_access_pdf:
            fields["url"] = paper.open_access_pdf
        # Assemble entry
        lines = [f"@{entry_type}{{{cite_key},"]
        for key, value in fields.items():
            lines.append(f"  {key} = {{{value}}},")
        # Remove trailing comma from last field
        if len(lines) > 1:
            lines[-1] = lines[-1].rstrip(",")
        lines.append("}")
        return "\n".join(lines)

    def export(self, papers: List[Paper], output_path: Path, top_n: Optional[int] = None) -> None:
        """Write a list of papers to a BibTeX file.

        Args:
            papers: List of Paper objects.
            output_path: Destination file path.
            top_n: If provided, export only the first N papers.
        """
        # Optionally truncate
        to_export = papers[:top_n] if top_n else papers
        logger.info(f"Exporting {len(to_export)} papers to BibTeX -> {output_path}")
        entries = []
        for paper in to_export:
            try:
                entry = self._build_bibtex_entry(paper)
                entries.append(entry)
            except Exception as e:
                logger.warning(f"Failed to create BibTeX entry: {e}")
                continue
        output_path.write_text("\n\n".join(entries), encoding="utf-8")