"""API routes for PDF parser service."""

import asyncio
import os
import tempfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import structlog
from fastapi import APIRouter, BackgroundTasks, Depends, File, HTTPException, UploadFile, status
from fastapi.responses import JSONResponse

from prime_parser.clients.http_client import HTTPClient
from prime_parser.config.settings import Settings
from prime_parser.core.pdf_parser import PDFParser
from prime_parser.models.domain_models import ParsedData
from prime_parser.utils.exceptions import DataExtractionError, ForwardingError, PDFParsingError
from prime_parser.api.dependencies import get_settings_dependency, validate_api_key

logger = structlog.get_logger()

router = APIRouter()

# Thread pool for synchronous PDF parsing
executor = ThreadPoolExecutor(max_workers=4)


async def process_pdf_background(
    temp_file_path: Path,
    request_id: int,
    settings: Settings,
) -> None:
    """Process PDF in background: parse and forward data.

    Args:
        temp_file_path: Path to temporary PDF file
        request_id: Request ID for logging
        settings: Application settings
    """
    logger.info("background_processing_started", request_id=request_id)

    try:
        # 1. Parse PDF (run in thread pool since pdfplumber is synchronous)
        loop = asyncio.get_event_loop()
        parser = PDFParser()

        report = await loop.run_in_executor(
            executor, parser.parse_pdf, temp_file_path
        )

        parsed_data = parser.to_parsed_data(report)

        logger.info(
            "pdf_parsed_successfully",
            request_id=request_id,
            date=parsed_data.report_date.isoformat(),
            total_energy=str(parsed_data.total_energy_production),
        )

        # 2. Forward data to external service
        http_client = HTTPClient(settings.forwarding)
        forward_response = await http_client.send_data(parsed_data)

        logger.info(
            "background_processing_completed",
            request_id=request_id,
            forward_response=forward_response,
        )

    except PDFParsingError as e:
        logger.error("pdf_parsing_error", request_id=request_id, error=str(e))
    except DataExtractionError as e:
        logger.error("data_extraction_error", request_id=request_id, error=str(e))
    except ForwardingError as e:
        logger.error("data_forwarding_error", request_id=request_id, error=str(e))
    except Exception as e:
        logger.error(
            "unexpected_error_in_background",
            request_id=request_id,
            error=str(e),
            error_type=type(e).__name__,
        )
    finally:
        # CRITICAL: Always delete temporary file
        if temp_file_path and temp_file_path.exists():
            try:
                os.unlink(temp_file_path)
                logger.debug(
                    "temp_file_deleted",
                    request_id=request_id,
                    temp_path=str(temp_file_path),
                )
            except Exception as e:
                logger.error(
                    "temp_file_deletion_failed",
                    request_id=request_id,
                    temp_path=str(temp_file_path),
                    error=str(e),
                )


@router.post(
    "/parse/ges/summary",
    status_code=status.HTTP_202_ACCEPTED,
    response_model=dict,
    summary="Parse PDF and forward data (Async)",
    description="Accept PDF file, return 202 immediately, parse and forward data in background",
)
async def parse_pdf_endpoint(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(..., description="PDF file to parse"),
    api_key: str = Depends(validate_api_key),
    settings: Settings = Depends(get_settings_dependency),
) -> dict:
    """Parse PDF file and forward data to external service asynchronously.

    Args:
        background_tasks: FastAPI background tasks
        file: Uploaded PDF file
        api_key: Validated API key
        settings: Application settings

    Returns:
        Accepted response
    """
    temp_file_path = None
    request_id = id(file)  # Simple request ID for logging

    logger.info(
        "parse_pdf_request_received",
        request_id=request_id,
        filename=file.filename,
        content_type=file.content_type,
    )

    try:
        # 1. Validate file type
        if not file.filename or not file.filename.lower().endswith(".pdf"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Only PDF files are allowed. Please upload a file with .pdf extension.",
            )

        # 2. Check file size (10MB limit)
        file.file.seek(0, 2)  # Seek to end
        file_size = file.file.tell()
        file.file.seek(0)  # Reset to beginning

        max_size = 10 * 1024 * 1024  # 10MB
        if file_size > max_size:
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail=f"File size ({file_size} bytes) exceeds maximum allowed size ({max_size} bytes)",
            )

        # 3. Save to temporary file
        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as temp:
            content = await file.read()
            temp.write(content)
            temp_file_path = Path(temp.name)

        logger.debug(
            "temp_file_created",
            request_id=request_id,
            temp_path=str(temp_file_path),
        )

        # 4. Schedule background task
        background_tasks.add_task(
            process_pdf_background,
            temp_file_path,
            request_id,
            settings,
        )

        logger.info(
            "background_task_scheduled",
            request_id=request_id,
            temp_path=str(temp_file_path),
        )

        return {
            "status": "accepted",
            "message": "PDF received and processing started",
            "request_id": request_id,
        }

    except Exception as e:
        # If something goes wrong *before* scheduling, clean up
        if temp_file_path and temp_file_path.exists():
            try:
                os.unlink(temp_file_path)
            except Exception:
                pass
        
        # Log and re-raise
        if isinstance(e, HTTPException):
            raise
            
        logger.error("request_failed", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Internal server error: {e}",
        )
