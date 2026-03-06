"""Main pipeline for parsing CBC curriculum PDFs.

This module orchestrates the full parsing pipeline:
- Discovers PDF files
- Extracts tables in parallel
- Parses and validates curriculum data
- Stores results in SQLite database
- Exports JSON backup
"""

import logging
import json
import sys
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

from .parser import PDFTableExtractor, find_pdf_files, extract_all_curriculum_tables
from .row_parser import RowParser, ParsingContext, parse_subject_grade
from .validator import ValidationStats, validate_row, filter_valid_rows
from .database import CurriculumDatabase, CurriculumRecord

# Configure logging
def setup_logging(log_level: int = logging.INFO, log_file: Optional[str] = None):
    """Configure logging for the parser.
    
    Args:
        log_level: Logging level (default INFO)
        log_file: Optional file path for logs
    """
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    # Root logger for cbc_parser
    logger = logging.getLogger('cbc_parser')
    logger.setLevel(log_level)
    
    # Clear existing handlers
    logger.handlers.clear()
    
    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(log_level)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)
    
    # File handler (optional)
    if log_file:
        file_handler = logging.FileHandler(log_file, encoding='utf-8')
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
    
    return logger


logger = logging.getLogger(__name__)


@dataclass
class PDFParseResult:
    """Result of parsing a single PDF."""
    filename: str
    subject: str
    grade: str
    tables_found: int
    records_extracted: int
    records_inserted: int
    duplicates: int
    errors: int
    duration_seconds: float
    success: bool
    error_message: str = ""


@dataclass
class PipelineStats:
    """Aggregated statistics for the entire pipeline run."""
    pdfs_processed: int = 0
    pdfs_successful: int = 0
    pdfs_failed: int = 0
    total_tables: int = 0
    total_records_extracted: int = 0
    total_records_inserted: int = 0
    total_duplicates: int = 0
    total_errors: int = 0
    duration_seconds: float = 0.0
    results: list[PDFParseResult] = field(default_factory=list)
    
    def log_summary(self):
        """Log a summary of pipeline results."""
        logger.info("=" * 60)
        logger.info("PARSING PIPELINE SUMMARY")
        logger.info("=" * 60)
        logger.info(f"PDFs Processed:    {self.pdfs_processed}")
        logger.info(f"  Successful:      {self.pdfs_successful}")
        logger.info(f"  Failed:          {self.pdfs_failed}")
        logger.info(f"Tables Found:      {self.total_tables}")
        logger.info(f"Records Extracted: {self.total_records_extracted}")
        logger.info(f"Records Inserted:  {self.total_records_inserted}")
        logger.info(f"Duplicates Skipped:{self.total_duplicates}")
        logger.info(f"Errors:            {self.total_errors}")
        logger.info(f"Total Duration:    {self.duration_seconds:.1f}s")
        logger.info("=" * 60)
        
        # Show per-PDF results
        if self.results:
            logger.info("\nPer-PDF Results:")
            for result in self.results:
                status = "OK" if result.success else "FAILED"
                logger.info(
                    f"  [{status}] {result.filename}: "
                    f"{result.records_inserted} records "
                    f"({result.tables_found} tables)"
                )


class CurriculumPipeline:
    """Main pipeline for parsing CBC curriculum PDFs."""
    
    def __init__(self, 
                 pdf_dir: str = "cbc pdfs",
                 db_path: Optional[str] = None,
                 max_workers: int = 4):
        """Initialize the pipeline.
        
        Args:
            pdf_dir: Directory containing PDF files
            db_path: Path to SQLite database (optional)
            max_workers: Maximum parallel workers for PDF processing
        """
        self.pdf_dir = Path(pdf_dir)
        self.db = CurriculumDatabase(db_path)
        self.max_workers = max_workers
        self.stats = PipelineStats()
    
    def run(self, 
            clear_existing: bool = False,
            export_json: bool = True,
            json_path: str = "cbc_parsed.json") -> PipelineStats:
        """Run the full parsing pipeline.
        
        Args:
            clear_existing: If True, clear existing database before parsing
            export_json: If True, export results to JSON
            json_path: Path for JSON export
            
        Returns:
            PipelineStats with results
        """
        start_time = datetime.now()
        logger.info("Starting CBC Curriculum Parsing Pipeline")
        logger.info(f"PDF Directory: {self.pdf_dir}")
        
        # Initialize database
        self.db.initialize()
        
        if clear_existing:
            logger.warning("Clearing existing curriculum data")
            self.db.clear_all_data()
        
        # Find PDF files
        pdf_files = find_pdf_files(self.pdf_dir)
        
        if not pdf_files:
            logger.error(f"No PDF files found in {self.pdf_dir}")
            return self.stats
        
        logger.info(f"Found {len(pdf_files)} PDF files to process")
        
        # Process PDFs (parallel or sequential)
        if self.max_workers > 1 and len(pdf_files) > 1:
            self._process_parallel(pdf_files)
        else:
            self._process_sequential(pdf_files)
        
        # Calculate duration
        end_time = datetime.now()
        self.stats.duration_seconds = (end_time - start_time).total_seconds()
        
        # Export to JSON if requested
        if export_json:
            self.db.export_to_json(json_path)
            logger.info(f"Exported curriculum data to {json_path}")
        
        # Log database summary
        summary = self.db.get_curriculum_summary()
        logger.info(f"Database Summary: {summary}")
        
        # Log final summary
        self.stats.log_summary()
        
        return self.stats
    
    def _process_sequential(self, pdf_files: list[Path]):
        """Process PDF files sequentially."""
        for pdf_path in pdf_files:
            result = self._process_single_pdf(pdf_path)
            self._update_stats(result)
    
    def _process_parallel(self, pdf_files: list[Path]):
        """Process PDF files in parallel using ThreadPoolExecutor."""
        logger.info(f"Processing {len(pdf_files)} PDFs with {self.max_workers} workers")
        
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            # Submit all jobs
            future_to_pdf = {
                executor.submit(self._process_single_pdf, pdf): pdf 
                for pdf in pdf_files
            }
            
            # Collect results as they complete
            for future in as_completed(future_to_pdf):
                pdf_path = future_to_pdf[future]
                try:
                    result = future.result()
                    self._update_stats(result)
                except Exception as e:
                    logger.error(f"Error processing {pdf_path.name}: {e}")
                    self.stats.pdfs_failed += 1
                    self.stats.pdfs_processed += 1
    
    def _process_single_pdf(self, pdf_path: Path) -> PDFParseResult:
        """Process a single PDF file.
        
        Args:
            pdf_path: Path to PDF file
            
        Returns:
            PDFParseResult with extraction results
        """
        start_time = datetime.now()
        logger.info(f"Processing: {pdf_path.name}")
        
        # Extract subject and grade from filename
        subject, grade = parse_subject_grade(pdf_path.stem)
        logger.debug(f"  Subject: {subject}, Grade: {grade}")
        
        try:
            # Extract curriculum tables
            tables = extract_all_curriculum_tables(pdf_path)
            logger.info(f"  Found {len(tables)} curriculum tables")
            
            # Parse tables into records
            all_records = []
            row_parser = RowParser()
            row_parser.set_context(subject, grade, pdf_path.name)
            
            for table in tables:
                records = row_parser.parse_table(
                    table.rows, 
                    table.headers,
                    table.page_number
                )
                all_records.extend(records)
            
            logger.info(f"  Extracted {len(all_records)} curriculum records")
            
            # Insert into database
            if all_records:
                insert_stats = self.db.bulk_insert_records(all_records, pdf_path.name)
                inserted = insert_stats['inserted']
                duplicates = insert_stats['duplicates']
                errors = insert_stats['errors']
            else:
                inserted = duplicates = errors = 0
            
            duration = (datetime.now() - start_time).total_seconds()
            
            return PDFParseResult(
                filename=pdf_path.name,
                subject=subject,
                grade=grade,
                tables_found=len(tables),
                records_extracted=len(all_records),
                records_inserted=inserted,
                duplicates=duplicates,
                errors=errors,
                duration_seconds=duration,
                success=True
            )
            
        except Exception as e:
            duration = (datetime.now() - start_time).total_seconds()
            logger.error(f"  Error: {e}")
            
            return PDFParseResult(
                filename=pdf_path.name,
                subject=subject,
                grade=grade,
                tables_found=0,
                records_extracted=0,
                records_inserted=0,
                duplicates=0,
                errors=1,
                duration_seconds=duration,
                success=False,
                error_message=str(e)
            )
    
    def _update_stats(self, result: PDFParseResult):
        """Update aggregate statistics with a PDF result."""
        self.stats.pdfs_processed += 1
        
        if result.success:
            self.stats.pdfs_successful += 1
        else:
            self.stats.pdfs_failed += 1
        
        self.stats.total_tables += result.tables_found
        self.stats.total_records_extracted += result.records_extracted
        self.stats.total_records_inserted += result.records_inserted
        self.stats.total_duplicates += result.duplicates
        self.stats.total_errors += result.errors
        self.stats.results.append(result)


def main():
    """Main entry point for the parsing pipeline."""
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Parse CBC curriculum PDFs and store in database"
    )
    parser.add_argument(
        '--pdf-dir', 
        default='cbc pdfs',
        help='Directory containing PDF files (default: "cbc pdfs")'
    )
    parser.add_argument(
        '--db-path',
        default=None,
        help='Path to SQLite database (default: curriculum.db)'
    )
    parser.add_argument(
        '--json-output',
        default='cbc_parsed.json',
        help='Path for JSON export (default: cbc_parsed.json)'
    )
    parser.add_argument(
        '--workers',
        type=int,
        default=4,
        help='Number of parallel workers (default: 4)'
    )
    parser.add_argument(
        '--clear',
        action='store_true',
        help='Clear existing data before parsing'
    )
    parser.add_argument(
        '--no-json',
        action='store_true',
        help='Skip JSON export'
    )
    parser.add_argument(
        '--log-file',
        default=None,
        help='Path to log file (optional)'
    )
    parser.add_argument(
        '-v', '--verbose',
        action='store_true',
        help='Enable verbose logging'
    )
    
    args = parser.parse_args()
    
    # Setup logging
    log_level = logging.DEBUG if args.verbose else logging.INFO
    setup_logging(log_level, args.log_file)
    
    # Run pipeline
    pipeline = CurriculumPipeline(
        pdf_dir=args.pdf_dir,
        db_path=args.db_path,
        max_workers=args.workers
    )
    
    stats = pipeline.run(
        clear_existing=args.clear,
        export_json=not args.no_json,
        json_path=args.json_output
    )
    
    # Exit with error if any PDFs failed
    sys.exit(0 if stats.pdfs_failed == 0 else 1)


if __name__ == "__main__":
    main()
