"""PDF table extraction for CBC curriculum documents.

This module handles:
- PDF reading with pdfplumber
- Table detection and extraction
- Filtering curriculum tables from non-curriculum tables
- Page range optimization
"""

import logging
from pathlib import Path
from typing import Optional, Iterator
from dataclasses import dataclass

import pdfplumber

from .header_normalizer import is_curriculum_table, calculate_curriculum_score
from .cleaner import clean_text

logger = logging.getLogger(__name__)


@dataclass
class ExtractedTable:
    """Represents a table extracted from a PDF."""
    headers: list[str]
    rows: list[list]
    page_number: int
    curriculum_score: int
    
    @property
    def row_count(self) -> int:
        return len(self.rows)
    
    @property
    def column_count(self) -> int:
        return len(self.headers)


@dataclass
class PDFInfo:
    """Metadata about a parsed PDF."""
    filename: str
    total_pages: int
    tables_found: int
    curriculum_tables: int


class PDFTableExtractor:
    """Extracts curriculum tables from CBC PDF documents."""
    
    # Page range to scan for curriculum content
    # Most CBC PDFs have curriculum tables between pages 8-80
    DEFAULT_START_PAGE = 8
    DEFAULT_END_PAGE = 100
    
    # Minimum score for a table to be considered curriculum-related
    MIN_CURRICULUM_SCORE = 12
    
    def __init__(self, start_page: int = None, end_page: int = None):
        """Initialize extractor.
        
        Args:
            start_page: Page to start scanning (1-indexed)
            end_page: Page to stop scanning (1-indexed)
        """
        self.start_page = start_page or self.DEFAULT_START_PAGE
        self.end_page = end_page or self.DEFAULT_END_PAGE
    
    def extract_tables(self, pdf_path: Path) -> Iterator[ExtractedTable]:
        """Extract curriculum tables from a PDF file.
        
        Args:
            pdf_path: Path to PDF file
            
        Yields:
            ExtractedTable objects for each curriculum table found
        """
        logger.info(f"Extracting tables from: {pdf_path.name}")
        
        try:
            with pdfplumber.open(pdf_path) as pdf:
                total_pages = len(pdf.pages)
                
                # Determine page range
                start_idx = max(0, self.start_page - 1)
                end_idx = min(total_pages, self.end_page)
                
                logger.debug(f"Scanning pages {start_idx + 1} to {end_idx} of {total_pages}")
                
                for page_idx in range(start_idx, end_idx):
                    page = pdf.pages[page_idx]
                    page_num = page_idx + 1
                    
                    # Extract all tables from this page
                    tables = page.extract_tables()
                    
                    if not tables:
                        continue
                    
                    for table_idx, table in enumerate(tables):
                        # Skip empty or trivial tables
                        if not table or len(table) < 2:
                            continue
                        
                        # Get headers (first row)
                        headers = table[0]
                        
                        if not headers or all(not h for h in headers):
                            continue
                        
                        # Check if this is a curriculum table
                        score = calculate_curriculum_score(headers)
                        
                        if score < self.MIN_CURRICULUM_SCORE:
                            logger.debug(
                                f"Page {page_num}, Table {table_idx}: "
                                f"Skipped (score {score} < {self.MIN_CURRICULUM_SCORE})"
                            )
                            continue
                        
                        # Clean headers
                        clean_headers = [clean_text(h) if h else "" for h in headers]
                        
                        # Clean data rows
                        data_rows = []
                        for row in table[1:]:
                            if row and any(cell for cell in row):
                                clean_row = [
                                    clean_text(cell) if cell else "" 
                                    for cell in row
                                ]
                                data_rows.append(clean_row)
                        
                        if not data_rows:
                            continue
                        
                        extracted = ExtractedTable(
                            headers=clean_headers,
                            rows=data_rows,
                            page_number=page_num,
                            curriculum_score=score
                        )
                        
                        logger.debug(
                            f"Page {page_num}: Found curriculum table "
                            f"({extracted.row_count} rows, score {score})"
                        )
                        
                        yield extracted
                        
        except Exception as e:
            logger.error(f"Error extracting tables from {pdf_path.name}: {e}")
            raise
    
    def get_pdf_info(self, pdf_path: Path) -> PDFInfo:
        """Get information about a PDF without full extraction.
        
        Args:
            pdf_path: Path to PDF file
            
        Returns:
            PDFInfo with metadata
        """
        total_tables = 0
        curriculum_tables = 0
        total_pages = 0
        
        try:
            with pdfplumber.open(pdf_path) as pdf:
                total_pages = len(pdf.pages)
                
                # Quick scan counting tables
                start_idx = max(0, self.start_page - 1)
                end_idx = min(total_pages, self.end_page)
                
                for page_idx in range(start_idx, end_idx):
                    page = pdf.pages[page_idx]
                    tables = page.extract_tables()
                    
                    if not tables:
                        continue
                    
                    for table in tables:
                        if table and len(table) >= 2:
                            total_tables += 1
                            headers = table[0]
                            if headers and is_curriculum_table(headers):
                                curriculum_tables += 1
        
        except Exception as e:
            logger.error(f"Error reading PDF info: {e}")
        
        return PDFInfo(
            filename=pdf_path.name,
            total_pages=total_pages,
            tables_found=total_tables,
            curriculum_tables=curriculum_tables
        )


def find_pdf_files(directory: Path) -> list[Path]:
    """Find all PDF files in a directory.
    
    Args:
        directory: Directory to search
        
    Returns:
        Sorted list of PDF file paths
    """
    if not directory.exists():
        logger.error(f"Directory not found: {directory}")
        return []
    
    pdfs = list(directory.glob("*.pdf")) + list(directory.glob("*.PDF"))
    pdfs = sorted(set(pdfs))  # Remove duplicates and sort
    
    logger.info(f"Found {len(pdfs)} PDF files in {directory}")
    return pdfs


class TableMerger:
    """Handles merging split tables across pages.
    
    Sometimes a single curriculum table spans multiple pages.
    This class detects and merges these cases.
    """
    
    def __init__(self):
        self.pending_table: Optional[ExtractedTable] = None
    
    def process(self, table: ExtractedTable) -> Optional[ExtractedTable]:
        """Process a table, potentially merging with pending table.
        
        Args:
            table: Newly extracted table
            
        Returns:
            Complete table if ready, None if pending merge
        """
        if self.pending_table is None:
            # Check if this table looks incomplete (might continue)
            if self._looks_continued(table):
                self.pending_table = table
                return None
            return table
        
        # Check if new table is continuation of pending
        if self._is_continuation(self.pending_table, table):
            merged = self._merge_tables(self.pending_table, table)
            
            # Check if merged table still looks incomplete
            if self._looks_continued(merged):
                self.pending_table = merged
                return None
            
            self.pending_table = None
            return merged
        
        # Not a continuation - return pending and store new
        result = self.pending_table
        self.pending_table = table if self._looks_continued(table) else None
        return result
    
    def flush(self) -> Optional[ExtractedTable]:
        """Flush any pending table.
        
        Returns:
            Pending table if any
        """
        result = self.pending_table
        self.pending_table = None
        return result
    
    def _looks_continued(self, table: ExtractedTable) -> bool:
        """Check if table looks like it might continue on next page.
        
        Heuristic: Last row has lots of empty cells
        """
        if not table.rows:
            return False
        
        last_row = table.rows[-1]
        empty_count = sum(1 for cell in last_row if not cell)
        
        # If more than half empty, might be continued
        return empty_count > len(last_row) / 2
    
    def _is_continuation(self, prev: ExtractedTable, curr: ExtractedTable) -> bool:
        """Check if current table continues previous table.
        
        Heuristics:
        - Same number of columns
        - Similar or same headers
        - Pages are adjacent
        """
        # Must have same column count
        if prev.column_count != curr.column_count:
            return False
        
        # Pages should be adjacent
        if curr.page_number - prev.page_number > 1:
            return False
        
        # Current table headers should match or be empty
        headers_match = 0
        for h1, h2 in zip(prev.headers, curr.headers):
            h1_clean = h1.lower().strip() if h1 else ""
            h2_clean = h2.lower().strip() if h2 else ""
            
            if h2_clean == "" or h1_clean == h2_clean:
                headers_match += 1
        
        return headers_match >= prev.column_count * 0.7
    
    def _merge_tables(self, prev: ExtractedTable, curr: ExtractedTable) -> ExtractedTable:
        """Merge two tables into one.
        
        Args:
            prev: First table
            curr: Continuation table
            
        Returns:
            Merged table
        """
        # Use headers from first table
        # Combine rows
        merged_rows = prev.rows + curr.rows
        
        return ExtractedTable(
            headers=prev.headers,
            rows=merged_rows,
            page_number=prev.page_number,  # Keep original page
            curriculum_score=max(prev.curriculum_score, curr.curriculum_score)
        )


def extract_all_curriculum_tables(pdf_path: Path) -> list[ExtractedTable]:
    """Extract all curriculum tables from a PDF, handling page spanning.
    
    Args:
        pdf_path: Path to PDF file
        
    Returns:
        List of ExtractedTable objects
    """
    extractor = PDFTableExtractor()
    merger = TableMerger()
    
    tables = []
    
    for table in extractor.extract_tables(pdf_path):
        result = merger.process(table)
        if result:
            tables.append(result)
    
    # Flush any pending table
    final = merger.flush()
    if final:
        tables.append(final)
    
    return tables
