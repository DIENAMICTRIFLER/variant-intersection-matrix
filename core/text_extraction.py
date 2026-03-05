"""
Text Extraction Module
======================

Extracts raw text content from PDF files using pdfplumber.

Key design decisions:
    • Batch processing to limit memory usage with large paper sets.
    • Per-page extraction with optional page limit.
    • Caching of extracted text to avoid re-reading PDFs.
    • Structured return format: {paper_id: full_text}.
"""

import logging
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import pdfplumber

from config.settings import (
    PAPERS_DIR,
    CACHE_DIR,
    PDF_BATCH_SIZE,
    MAX_PAGES_PER_PAPER,
)
from utils.helpers import get_paper_id, save_json, load_json, compute_file_hash

logger = logging.getLogger(__name__)


class TextExtractor:
    """
    Handles PDF-to-text extraction with caching and batch support.

    Attributes:
        papers_dir: Directory containing PDF files.
        cache_dir:  Directory for caching extracted text.
        batch_size: Number of PDFs to process in each batch.
        max_pages:  Maximum pages to extract per paper (None = all).
    """

    def __init__(
        self,
        papers_dir: Path = PAPERS_DIR,
        cache_dir: Path = CACHE_DIR,
        batch_size: int = PDF_BATCH_SIZE,
        max_pages: Optional[int] = MAX_PAGES_PER_PAPER,
    ):
        self.papers_dir = Path(papers_dir)
        self.cache_dir = Path(cache_dir)
        self.batch_size = batch_size
        self.max_pages = max_pages
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    # ── Public API ───────────────────────────────────────────────────────

    def extract_all(
        self,
        progress_callback=None,
    ) -> Dict[str, str]:
        """
        Extract text from every PDF in papers_dir.

        Uses cached results when the file hash has not changed.

        Args:
            progress_callback: Optional callable(current, total) for UI progress.

        Returns:
            Dictionary mapping paper_id → full extracted text.
        """
        pdf_files = self._list_pdfs()
        total = len(pdf_files)
        if total == 0:
            logger.warning("No PDF files found in %s", self.papers_dir)
            return {}

        logger.info("Extracting text from %d papers (batch_size=%d)", total, self.batch_size)

        results: Dict[str, str] = {}
        for batch_idx in range(0, total, self.batch_size):
            batch = pdf_files[batch_idx : batch_idx + self.batch_size]
            for i, pdf_path in enumerate(batch):
                global_idx = batch_idx + i
                paper_id = get_paper_id(pdf_path.name)
                text = self._extract_with_cache(pdf_path, paper_id)
                results[paper_id] = text

                if progress_callback:
                    progress_callback(global_idx + 1, total)

        logger.info("Extraction complete: %d papers processed", len(results))
        return results

    def extract_single(self, pdf_path: Path) -> Tuple[str, str]:
        """
        Extract text from a single PDF file.

        Args:
            pdf_path: Path to the PDF.

        Returns:
            Tuple of (paper_id, extracted_text).
        """
        paper_id = get_paper_id(pdf_path.name)
        text = self._extract_pdf(pdf_path)
        return paper_id, text

    # ── Internal Methods ─────────────────────────────────────────────────

    def _list_pdfs(self) -> List[Path]:
        """Return sorted list of PDF files in papers_dir."""
        return sorted(self.papers_dir.glob("*.pdf"))

    def _extract_with_cache(self, pdf_path: Path, paper_id: str) -> str:
        """
        Return extracted text, using cached version if the file hasn't changed.
        """
        cache_file = self.cache_dir / f"{paper_id}.json"
        file_hash = compute_file_hash(pdf_path)

        # Check cache validity
        if cache_file.exists():
            try:
                cached = load_json(cache_file)
                if cached.get("hash") == file_hash:
                    logger.debug("Cache hit for %s", paper_id)
                    return cached["text"]
            except Exception:
                pass  # Cache corrupt — re-extract

        # Extract fresh
        text = self._extract_pdf(pdf_path)

        # Save to cache
        save_json({"hash": file_hash, "text": text}, cache_file)
        logger.debug("Cached extraction for %s", paper_id)

        return text

    def _extract_pdf(self, pdf_path: Path) -> str:
        """
        Extract text from a PDF file using pdfplumber.

        Args:
            pdf_path: Path to the PDF file.

        Returns:
            Concatenated text from all (or limited) pages.
        """
        pages_text: List[str] = []
        try:
            with pdfplumber.open(pdf_path) as pdf:
                page_limit = self.max_pages or len(pdf.pages)
                for page in pdf.pages[:page_limit]:
                    text = page.extract_text()
                    if text:
                        pages_text.append(text)
        except Exception as e:
            logger.error("Failed to extract %s: %s", pdf_path.name, e)
            return ""

        return "\n".join(pages_text)
