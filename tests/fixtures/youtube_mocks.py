"""Mock YouTube Data API service for tests."""

from types import SimpleNamespace
from typing import Any, Dict, List, Optional
from unittest.mock import MagicMock

from googleapiclient.errors import HttpError


def http_error(status: int) -> HttpError:
    """Build an ``HttpError`` with the given HTTP status."""
    return HttpError(SimpleNamespace(status=status, reason="error"), b"{}")


def make_youtube_service(
    video_id: str = "vid123",
    chunk_results: Optional[List[Any]] = None,
    playlists: Optional[List[Dict[str, Any]]] = None,
    thumbnail_error: Optional[Exception] = None,
) -> MagicMock:
    """A MagicMock shaped like ``googleapiclient`` YouTube v3 resource."""
    service = MagicMock()

    insert_request = MagicMock()
    if chunk_results is None:
        progress = MagicMock()
        progress.progress.return_value = 0.5
        chunk_results = [(progress, None), (None, {"id": video_id})]
    insert_request.next_chunk.side_effect = chunk_results
    service.videos.return_value.insert.return_value = insert_request

    service.playlists.return_value.list.return_value.execute.return_value = {
        "items": playlists or []
    }
    service.playlists.return_value.insert.return_value.execute.return_value = {"id": "PLnew"}

    if thumbnail_error is not None:
        service.thumbnails.return_value.set.return_value.execute.side_effect = thumbnail_error
    return service
