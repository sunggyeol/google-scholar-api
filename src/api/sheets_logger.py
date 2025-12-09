"""
Google Sheets Logger for API Requests and Responses
Logs all API requests and responses to a Google Sheet for tracking and analysis
"""
from datetime import datetime
from typing import Optional, Dict, Any
import json
from pathlib import Path

from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from loguru import logger


class GoogleSheetsLogger:
    """
    Logger that writes API requests and responses to Google Sheets
    """
    
    # Google Sheets API scopes
    SCOPES = ['https://www.googleapis.com/auth/spreadsheets']
    
    def __init__(
        self,
        spreadsheet_id: str,
        credentials_path: str,
        sheet_name: str = "API Logs",
        enabled: bool = True
    ):
        """
        Initialize Google Sheets Logger
        
        Args:
            spreadsheet_id: The ID of the Google Sheet (from URL)
            credentials_path: Path to service account credentials JSON file
            sheet_name: Name of the sheet tab to write to
            enabled: Whether logging is enabled
        """
        self.spreadsheet_id = spreadsheet_id
        self.credentials_path = credentials_path
        self.sheet_name = sheet_name
        self.enabled = enabled
        self.service = None
        
        if self.enabled:
            self._initialize_service()
            self._ensure_headers()
    
    def _initialize_service(self):
        """Initialize Google Sheets API service"""
        try:
            creds_path = Path(self.credentials_path)
            if not creds_path.exists():
                logger.warning(f"Google Sheets credentials not found at {self.credentials_path}")
                self.enabled = False
                return
            
            credentials = Credentials.from_service_account_file(
                self.credentials_path,
                scopes=self.SCOPES
            )
            
            self.service = build('sheets', 'v4', credentials=credentials)
            logger.info("Google Sheets API service initialized successfully")
            
        except Exception as e:
            logger.error(f"Failed to initialize Google Sheets service: {e}")
            self.enabled = False
    
    def _ensure_headers(self):
        """Ensure the sheet has proper headers"""
        if not self.enabled or not self.service:
            return
        
        try:
            # First, try to get spreadsheet metadata to check if sheet exists
            spreadsheet = self.service.spreadsheets().get(
                spreadsheetId=self.spreadsheet_id
            ).execute()
            
            # Check if the sheet tab exists
            sheet_exists = False
            for sheet in spreadsheet.get('sheets', []):
                if sheet['properties']['title'] == self.sheet_name:
                    sheet_exists = True
                    break
            
            # If sheet doesn't exist, create it
            if not sheet_exists:
                logger.info(f"Sheet tab '{self.sheet_name}' not found, creating it...")
                requests = [{
                    'addSheet': {
                        'properties': {
                            'title': self.sheet_name
                        }
                    }
                }]
                self.service.spreadsheets().batchUpdate(
                    spreadsheetId=self.spreadsheet_id,
                    body={'requests': requests}
                ).execute()
                logger.info(f"Created sheet tab '{self.sheet_name}'")
            
            # Check if sheet has headers
            result = self.service.spreadsheets().values().get(
                spreadsheetId=self.spreadsheet_id,
                range=f"{self.sheet_name}!A1:M1"
            ).execute()
            
            values = result.get('values', [])
            
            # If no headers, add them
            if not values:
                headers = [
                    'Timestamp',
                    'Method',
                    'Endpoint',
                    'Status Code',
                    'Request Query Params',
                    'Request Body',
                    'Response Time (s)',
                    'Cache Hit',
                    'Success',
                    'Error',
                    'Client IP',
                    'User Agent',
                    'Response Size (bytes)'
                ]
                
                self.service.spreadsheets().values().update(
                    spreadsheetId=self.spreadsheet_id,
                    range=f"{self.sheet_name}!A1:M1",
                    valueInputOption='RAW',
                    body={'values': [headers]}
                ).execute()
                
                logger.info(f"Headers added to sheet '{self.sheet_name}'")
                
        except HttpError as e:
            if e.resp.status == 404:
                logger.error(f"Spreadsheet {self.spreadsheet_id} not found")
            elif e.resp.status == 403:
                logger.error(f"Permission denied. Make sure the service account has Editor access to the spreadsheet")
            else:
                logger.error(f"Error ensuring headers: {e}")
            self.enabled = False
        except Exception as e:
            logger.error(f"Error ensuring headers: {e}")
            self.enabled = False
    
    def log_request(
        self,
        method: str,
        endpoint: str,
        status_code: int,
        query_params: Optional[Dict[str, Any]] = None,
        request_body: Optional[Dict[str, Any]] = None,
        response_time: Optional[float] = None,
        cache_hit: Optional[bool] = None,
        success: bool = True,
        error: Optional[str] = None,
        client_ip: Optional[str] = None,
        user_agent: Optional[str] = None,
        response_size: Optional[int] = None
    ):
        """
        Log a single API request to Google Sheets
        
        Args:
            method: HTTP method (GET, POST, etc.)
            endpoint: API endpoint path
            status_code: HTTP status code
            query_params: Query parameters dict
            request_body: Request body dict
            response_time: Response time in seconds
            cache_hit: Whether response was from cache
            success: Whether request was successful
            error: Error message if any
            client_ip: Client IP address
            user_agent: Client user agent
            response_size: Response size in bytes
        """
        if not self.enabled or not self.service:
            return
        
        try:
            # Prepare row data
            timestamp = datetime.utcnow().isoformat()
            
            # Convert dicts to JSON strings for storage
            query_params_str = json.dumps(query_params) if query_params else ""
            request_body_str = json.dumps(request_body) if request_body else ""
            
            # Truncate long strings to avoid cell size limits (50000 chars)
            if len(query_params_str) > 5000:
                query_params_str = query_params_str[:5000] + "... [truncated]"
            if len(request_body_str) > 5000:
                request_body_str = request_body_str[:5000] + "... [truncated]"
            
            row = [
                timestamp,
                method,
                endpoint,
                status_code,
                query_params_str,
                request_body_str,
                f"{response_time:.3f}" if response_time else "",
                "Yes" if cache_hit else "No" if cache_hit is not None else "",
                "Yes" if success else "No",
                error or "",
                client_ip or "",
                user_agent or "",
                response_size or ""
            ]
            
            # Append row to sheet
            self.service.spreadsheets().values().append(
                spreadsheetId=self.spreadsheet_id,
                range=f"{self.sheet_name}!A:M",
                valueInputOption='RAW',
                insertDataOption='INSERT_ROWS',
                body={'values': [row]}
            ).execute()
            
            logger.debug(f"Logged request to Google Sheets: {method} {endpoint}")
            
        except HttpError as e:
            logger.error(f"HTTP error logging to Google Sheets: {e}")
        except Exception as e:
            logger.error(f"Error logging to Google Sheets: {e}")
    
    async def log_request_async(self, *args, **kwargs):
        """
        Async wrapper for log_request
        Note: Google Sheets API is synchronous, but we run it in a way that doesn't block
        """
        # In production, you might want to use asyncio.to_thread or a background task
        # For now, we'll just call the sync version
        self.log_request(*args, **kwargs)
    
    def get_logs_count(self) -> int:
        """
        Get the total number of logged requests
        
        Returns:
            Number of rows (excluding header)
        """
        if not self.enabled or not self.service:
            return 0
        
        try:
            result = self.service.spreadsheets().values().get(
                spreadsheetId=self.spreadsheet_id,
                range=f"{self.sheet_name}!A:A"
            ).execute()
            
            values = result.get('values', [])
            # Subtract 1 for header row
            return max(0, len(values) - 1)
            
        except Exception as e:
            logger.error(f"Error getting logs count: {e}")
            return 0
    
    def clear_logs(self) -> bool:
        """
        Clear all logs (keeping headers)
        
        Returns:
            True if successful, False otherwise
        """
        if not self.enabled or not self.service:
            return False
        
        try:
            # Get the range to clear (everything except header)
            self.service.spreadsheets().values().clear(
                spreadsheetId=self.spreadsheet_id,
                range=f"{self.sheet_name}!A2:M"
            ).execute()
            
            logger.info("Cleared all logs from Google Sheets")
            return True
            
        except Exception as e:
            logger.error(f"Error clearing logs: {e}")
            return False


# Global instance (will be initialized in main.py)
sheets_logger: Optional[GoogleSheetsLogger] = None


def init_sheets_logger(
    spreadsheet_id: str,
    credentials_path: str,
    sheet_name: str = "API Logs",
    enabled: bool = True
) -> GoogleSheetsLogger:
    """
    Initialize the global sheets logger instance
    
    Args:
        spreadsheet_id: The ID of the Google Sheet
        credentials_path: Path to service account credentials JSON
        sheet_name: Name of the sheet tab
        enabled: Whether logging is enabled
        
    Returns:
        GoogleSheetsLogger instance
    """
    global sheets_logger
    sheets_logger = GoogleSheetsLogger(
        spreadsheet_id=spreadsheet_id,
        credentials_path=credentials_path,
        sheet_name=sheet_name,
        enabled=enabled
    )
    return sheets_logger


def get_sheets_logger() -> Optional[GoogleSheetsLogger]:
    """Get the global sheets logger instance"""
    return sheets_logger

