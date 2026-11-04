import asyncio
import io
import clamd
from typing import Tuple
import logging

from app.config import settings

logger = logging.getLogger(__name__)

# Prevent slamming ClamAV with too many concurrent connections during bulk upload
_clamav_semaphore = asyncio.Semaphore(2)

async def scan_file_bytes(file_bytes: bytes) -> Tuple[bool, str]:
    """
    Scans a file for malware using ClamAV.
    Returns:
        (is_clean, message)
        If clean: (True, "Clear from malware")
        If malware found: (False, "Found: MalwareName")
        If error: Raises an Exception or returns (False, error msg) depending on how we want to handle it.
    """
    def _scan():
        try:
            # Create a network socket to ClamAV container
            cd = clamd.ClamdNetworkSocket(host=settings.CLAMAV_HOST, port=settings.CLAMAV_PORT, timeout=15)
            
            # Use instream to send file bytes without writing to shared disk
            stream = io.BytesIO(file_bytes)
            result = cd.instream(stream)
            
            if 'stream' in result:
                status, details = result['stream']
                if status == 'OK':
                    return True, "Clear from malware"
                elif status == 'FOUND':
                    return False, f"Malware detected: {details}"
                else:
                    return False, f"Unknown ClamAV status: {status}"
            else:
                return False, "Unexpected ClamAV response format"
        except clamd.BufferTooLongError:
            return False, "File too large for ClamAV to scan"
        except clamd.ConnectionError as e:
            logger.error(f"ClamAV Connection Error: {e}")
            raise Exception("Malware scanner unavailable. Please try again later.")
        except Exception as e:
            logger.error(f"Error scanning file with ClamAV: {e}")
            raise Exception("An error occurred during malware scanning.")

    # Run the synchronous clamd network call in a thread pool to avoid blocking the event loop
    async with _clamav_semaphore:
        return await asyncio.to_thread(_scan)
