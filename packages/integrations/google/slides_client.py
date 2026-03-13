"""Google Slides API client. Requires google-api-python-client."""
from __future__ import annotations

from packages.integrations.base import IntegrationClient


class GoogleSlidesClient(IntegrationClient):
    """Google Slides API client. Requires google-api-python-client."""

    def __init__(self, credentials_data: dict | None = None) -> None:
        super().__init__("google_slides")
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
                self._service = build("slides", "v1", credentials=creds)
            else:
                self._log.warning("No credentials — Google Slides client in stub mode")
        except ImportError:
            self._log.warning("google-api-python-client not installed — stub mode")

    def health_check(self) -> bool:
        self._ensure_service()
        return self._service is not None

    def create_presentation(self, title: str, slides_data: list[dict] | None = None) -> dict:
        """Create a new Google Slides presentation.

        Args:
            title: Presentation title.
            slides_data: Optional list of dicts with "title" and "body" keys
                         for each slide to create.

        Returns:
            {"presentationId": ..., "url": ...}
        """
        self._ensure_service()
        if self._service is None:
            return {
                "presentationId": "stub_presentation_id",
                "url": "https://docs.google.com/presentation/d/stub/edit",
                "stub": True,
            }

        def _create():
            presentation = (
                self._service.presentations()
                .create(body={"title": title})
                .execute()
            )
            pres_id = presentation["presentationId"]

            if slides_data:
                requests = []
                for slide_info in slides_data:
                    requests.append({"createSlide": {"slideLayoutReference": {"predefinedLayout": "TITLE_AND_BODY"}}})
                if requests:
                    self._service.presentations().batchUpdate(
                        presentationId=pres_id,
                        body={"requests": requests},
                    ).execute()

            return {
                "presentationId": pres_id,
                "url": f"https://docs.google.com/presentation/d/{pres_id}/edit",
            }

        return self._execute_with_retry(_create)
