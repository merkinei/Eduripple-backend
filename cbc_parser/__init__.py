"""CBC Curriculum PDF Parser Package.

This package provides a robust, modular system for extracting curriculum
data from Kenya CBC (Competency-Based Curriculum) PDF documents.

Modules:
    - cleaner: Text cleaning and normalization
    - header_normalizer: Maps header variations to canonical names
    - validator: Data validation and filtering
    - database: Normalized SQLite database operations
    - row_parser: Converts table rows to structured records
    - parser: PDF reading and table extraction
    - main: Pipeline orchestration

Usage:
    from cbc_parser import CurriculumPipeline
    
    pipeline = CurriculumPipeline(pdf_dir="cbc pdfs")
    stats = pipeline.run()
    
    # Or run from command line:
    # python -m cbc_parser --pdf-dir "cbc pdfs" --clear
"""

from .database import CurriculumDatabase, CurriculumRecord
from .main import CurriculumPipeline, PipelineStats, setup_logging
from .parser import PDFTableExtractor, find_pdf_files
from .row_parser import RowParser, parse_subject_grade
from .validator import ValidationStats, validate_row
from .cleaner import clean_text, extract_list_items
from .header_normalizer import normalize_header, is_curriculum_table

__version__ = "2.0.0"

__all__ = [
    # Main pipeline
    "CurriculumPipeline",
    "PipelineStats",
    "setup_logging",
    
    # Database
    "CurriculumDatabase",
    "CurriculumRecord",
    
    # Parser
    "PDFTableExtractor",
    "find_pdf_files",
    
    # Row parsing
    "RowParser",
    "parse_subject_grade",
    
    # Validation
    "ValidationStats",
    "validate_row",
    
    # Utilities
    "clean_text",
    "extract_list_items",
    "normalize_header",
    "is_curriculum_table",
]
