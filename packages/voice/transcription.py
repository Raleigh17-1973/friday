from __future__ import annotations

import os
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class TranscriptionResult:
    text: str
    language: str
    duration_seconds: float
    confidence: float
    segments: list[dict] = field(default_factory=list)  # [{start, end, text}]
    metadata: dict[str, Any] = field(default_factory=dict)


class VoiceTranscriptionService:
    """Transcribe audio to text using OpenAI Whisper API (or local fallback).

    Priority:
    1. OpenAI Whisper API (if OPENAI_API_KEY set)
    2. Local whisper package (if installed: pip install openai-whisper)
    3. Stub result
    """

    def __init__(self) -> None:
        self._api_key = os.getenv("OPENAI_API_KEY", "")
        self._model = os.getenv("WHISPER_MODEL", "whisper-1")

    def transcribe_file(self, audio_path: Path) -> TranscriptionResult:
        """Transcribe an audio file. Supports mp3, mp4, wav, m4a, webm, ogg."""
        audio_path = Path(audio_path)
        if not audio_path.exists():
            raise FileNotFoundError(f"Audio file not found: {audio_path}")

        # Try OpenAI API first
        if self._api_key:
            try:
                return self._transcribe_openai(audio_path)
            except Exception:
                pass  # fall through to local

        # Try local whisper
        try:
            return self._transcribe_local(audio_path)
        except ImportError:
            pass

        # Stub
        return TranscriptionResult(
            text=f"[Transcription stub — set OPENAI_API_KEY or install openai-whisper to enable. File: {audio_path.name}]",
            language="en",
            duration_seconds=0.0,
            confidence=0.0,
            metadata={"stub": True, "file": str(audio_path)},
        )

    def transcribe_bytes(self, audio_bytes: bytes, filename: str = "audio.mp3") -> TranscriptionResult:
        """Transcribe audio from bytes."""
        with tempfile.NamedTemporaryFile(suffix=Path(filename).suffix, delete=False) as tmp:
            tmp.write(audio_bytes)
            tmp_path = Path(tmp.name)
        try:
            return self.transcribe_file(tmp_path)
        finally:
            try:
                tmp_path.unlink()
            except OSError:
                pass

    def _transcribe_openai(self, audio_path: Path) -> TranscriptionResult:
        """Call OpenAI Whisper API."""
        import urllib.request
        import urllib.error
        import json

        with open(audio_path, "rb") as f:
            audio_data = f.read()

        # Build multipart form data
        boundary = "----FridayVoiceBoundary"
        body_parts = [
            f"--{boundary}\r\nContent-Disposition: form-data; name=\"model\"\r\n\r\n{self._model}\r\n".encode(),
            f"--{boundary}\r\nContent-Disposition: form-data; name=\"response_format\"\r\n\r\njson\r\n".encode(),
            f"--{boundary}\r\nContent-Disposition: form-data; name=\"file\"; filename=\"{audio_path.name}\"\r\nContent-Type: audio/mpeg\r\n\r\n".encode(),
            audio_data,
            f"\r\n--{boundary}--\r\n".encode(),
        ]
        body = b"".join(body_parts)

        req = urllib.request.Request(
            "https://api.openai.com/v1/audio/transcriptions",
            data=body,
            headers={
                "Authorization": f"Bearer {self._api_key}",
                "Content-Type": f"multipart/form-data; boundary={boundary}",
            },
            method="POST",
        )

        with urllib.request.urlopen(req, timeout=60) as resp:  # nosec B310
            data = json.loads(resp.read().decode("utf-8"))

        return TranscriptionResult(
            text=data.get("text", ""),
            language=data.get("language", "en"),
            duration_seconds=float(data.get("duration", 0)),
            confidence=0.95,
            segments=data.get("segments", []),
            metadata={"model": self._model, "source": "openai_whisper"},
        )

    def _transcribe_local(self, audio_path: Path) -> TranscriptionResult:
        """Use local whisper package."""
        import whisper  # type: ignore
        model = whisper.load_model("base")
        result = model.transcribe(str(audio_path))
        segments = [
            {"start": s["start"], "end": s["end"], "text": s["text"]}
            for s in result.get("segments", [])
        ]
        return TranscriptionResult(
            text=result.get("text", ""),
            language=result.get("language", "en"),
            duration_seconds=segments[-1]["end"] if segments else 0.0,
            confidence=0.9,
            segments=segments,
            metadata={"model": "whisper-base-local", "source": "local_whisper"},
        )
