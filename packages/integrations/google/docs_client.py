"""Google Docs API client. Requires google-api-python-client."""
from __future__ import annotations

from packages.integrations.base import IntegrationClient


class GoogleDocsClient(IntegrationClient):
    """Google Docs API client. Requires google-api-python-client."""

    def __init__(self, credentials_data: dict | None = None) -> None:
        super().__init__("google_docs")
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
                self._service = build("docs", "v1", credentials=creds)
            else:
                self._log.warning("No credentials — Google Docs client in stub mode")
        except ImportError:
            self._log.warning("google-api-python-client not installed — stub mode")

    def health_check(self) -> bool:
        self._ensure_service()
        return self._service is not None

    def create_document(self, title: str, body_content: str = "") -> dict:
        """Create a new Google Doc. Returns {"documentId": ..., "url": ...}."""
        self._ensure_service()
        if self._service is None:
            return {
                "documentId": "stub_doc_id",
                "url": "https://docs.google.com/stub",
                "stub": True,
            }

        def _create():
            doc = self._service.documents().create(body={"title": title}).execute()
            doc_id = doc["documentId"]
            if body_content:
                self._service.documents().batchUpdate(
                    documentId=doc_id,
                    body={
                        "requests": [
                            {
                                "insertText": {
                                    "location": {"index": 1},
                                    "text": body_content,
                                }
                            }
                        ]
                    },
                ).execute()
            return {
                "documentId": doc_id,
                "url": f"https://docs.google.com/document/d/{doc_id}/edit",
            }

        return self._execute_with_retry(_create)
