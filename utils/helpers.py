"""
Shared utility functions used across the system.

Provides JSON I/O, filename sanitization, and formatting helpers.
"""

import json
import re
import hashlib
from pathlib import Path
from typing import Any, Dict, Optional


def load_json(filepath: Path) -> Any:
    """
    Load and parse a JSON file.

    Args:
        filepath: Path to the JSON file.

    Returns:
        Parsed JSON content (dict, list, etc.).

    Raises:
        FileNotFoundError: If the file does not exist.
        json.JSONDecodeError: If the file contains invalid JSON.
    """
    filepath = Path(filepath)
    if not filepath.exists():
        raise FileNotFoundError(f"JSON file not found: {filepath}")
    with open(filepath, "r", encoding="utf-8") as f:
        return json.load(f)


def save_json(data: Any, filepath: Path, indent: int = 2) -> None:
    """
    Save data as a formatted JSON file.

    Args:
        data: Data to serialize (must be JSON-serializable).
        filepath: Destination path.
        indent: Number of spaces for indentation.
    """
    filepath = Path(filepath)
    filepath.parent.mkdir(parents=True, exist_ok=True)
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=indent, ensure_ascii=False)


def get_paper_id(filename: str) -> str:
    """
    Generate a stable, unique identifier for a paper based on its filename.

    Uses the filename stem (without extension) — simple and deterministic.

    Args:
        filename: Original filename of the PDF.

    Returns:
        Sanitized identifier string.
    """
    stem = Path(filename).stem
    return safe_filename(stem)


def safe_filename(name: str) -> str:
    """
    Sanitize a string for use as a filename.

    Replaces all non-alphanumeric characters (except hyphens and underscores)
    with underscores, collapses runs of underscores, and strips leading/trailing
    underscores.

    Args:
        name: Input string.

    Returns:
        Sanitized filename string.
    """
    sanitized = re.sub(r"[^\w\-]", "_", name)
    sanitized = re.sub(r"_+", "_", sanitized)
    return sanitized.strip("_")


def format_file_size(size_bytes: int) -> str:
    """
    Format a file size in bytes into a human-readable string.

    Args:
        size_bytes: Size in bytes.

    Returns:
        Formatted string (e.g., "1.5 MB").
    """
    if size_bytes < 1024:
        return f"{size_bytes} B"
    elif size_bytes < 1024 ** 2:
        return f"{size_bytes / 1024:.1f} KB"
    elif size_bytes < 1024 ** 3:
        return f"{size_bytes / (1024 ** 2):.1f} MB"
    else:
        return f"{size_bytes / (1024 ** 3):.2f} GB"


def compute_file_hash(filepath: Path, algorithm: str = "md5") -> str:
    """
    Compute a hash digest of a file for change detection / caching.

    Args:
        filepath: Path to the file.
        algorithm: Hash algorithm name (default 'md5').

    Returns:
        Hex digest string.
    """
    h = hashlib.new(algorithm)
    with open(filepath, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()
