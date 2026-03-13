"""Google Sheets API client. Requires google-api-python-client."""
from __future__ import annotations

from packages.integrations.base import IntegrationClient


class GoogleSheetsClient(IntegrationClient):
    """Google Sheets API client. Requires google-api-python-client."""

    def __init__(self, credentials_data: dict | None = None) -> None:
        super().__init__("google_sheets")
        self._credentials_data = credentials_data
        self._service = None

    def _ensure_service(self) -> None:
        if self._service is not None:
            return
        try:
            from google.oauth2.credentials import Credentials  # type: ignore[import-untyped]
            from googleapiclient.discovery import build  # type: ignore[import-untyped]

            if self._credentials_data:
                creds = Credentials.from_authorized_user_info(self._credentials_data)
                self._service = build("sheets", "v4", credentials=creds)
            else:
                self._log.warning("No credentials — Google Sheets client in stub mode")
        except ImportError:
            self._log.warning("google-api-python-client not installed — stub mode")

    def health_check(self) -> bool:
        self._ensure_service()
        return self._service is not None

    def create_spreadsheet(self, title: str, data: list[list[str]] | None = None) -> dict:
        """Create a new Google Sheet, optionally populated with data.

        Args:
            title: Spreadsheet title.
            data: Optional 2D list of cell values to populate Sheet1.

        Returns:
            {"spreadsheetId": ..., "url": ...}
        """
        self._ensure_service()
        if self._service is None:
            return {
                "spreadsheetId": "stub_spreadsheet_id",
                "url": "https://docs.google.com/spreadsheets/d/stub/edit",
                "stub": True,
            }

        def _create():
            spreadsheet = (
                self._service.spreadsheets()
                .create(body={"properties": {"title": title}})
                .execute()
            )
            ss_id = spreadsheet["spreadsheetId"]

            if data:
                self._service.spreadsheets().values().update(
                    spreadsheetId=ss_id,
                    range="Sheet1!A1",
                    valueInputOption="RAW",
                    body={"values": data},
                ).execute()

            return {
                "spreadsheetId": ss_id,
                "url": f"https://docs.google.com/spreadsheets/d/{ss_id}/edit",
            }

        return self._execute_with_retry(_create)
