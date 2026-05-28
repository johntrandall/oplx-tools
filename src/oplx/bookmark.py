"""Generate macOS NSURL bookmark data for <attachment> elements.

OmniPlan stores task attachments as::

    <attachment uri="file:///abs/path/to/file.ext">
      <bookmarkData>BASE64_NSURL_BOOKMARK</bookmarkData>
    </attachment>

The ``<bookmarkData>`` child is REQUIRED for ``file://`` URIs — without
it, OmniPlan opens the document but silently drops the attachment from
its in-memory model (``count attachments of task`` returns 0). See the
oplx-format spec § ``ATTACH-NO-BOOKMARK`` silent-corruption entry.

The bookmark binary encodes inode + path + volume UUID so the link
survives renames. It is an Apple-internal NSKeyedArchiver-style format;
treat as opaque. Generate fresh on emit; do not attempt to round-trip
parsed bookmarks.

This module is macOS-only. PyObjC is a soft dependency — install it via::

    pip install 'oplx-tools[macos]'

Calling ``make_bookmark()`` on a non-Mac platform or without PyObjC
raises ``OSError`` with a clean pointer at the extra.
"""

from __future__ import annotations

import base64
import sys
from pathlib import Path


class BookmarkUnavailableError(OSError):
    """Raised when bookmark generation is unsupported in the current environment."""


def make_bookmark(path: str | Path) -> tuple[str, str]:
    """Generate ``(uri, bookmark_data_b64)`` for a local file path.

    Args:
        path: Absolute or relative path to a file. Relative paths are
            resolved against the current working directory. The file
            must exist — OmniPlan's bookmark resolver uses the inode
            number captured at generation time.

    Returns:
        A 2-tuple ``(uri, bookmark_data)`` where:
        - ``uri`` is ``NSURL.absoluteString()`` — e.g.
          ``file:///Users/me/Documents/spec.pdf``.
        - ``bookmark_data`` is the base64-encoded NSURL bookmark, suitable
          for the ``<bookmarkData>`` child element of ``<attachment>``.

    Raises:
        BookmarkUnavailableError: if not running on macOS, or if PyObjC
            is not installed. The error message points at the
            ``oplx-tools[macos]`` extra.
        FileNotFoundError: if ``path`` does not exist on disk.
        OSError: if the macOS bookmark API returns an error (rare —
            typically only on permissions or unusual filesystems).
    """
    if sys.platform != "darwin":
        raise BookmarkUnavailableError(
            "oplx.bookmark.make_bookmark is macOS-only — NSURL bookmark data "
            "is an Apple-platform format. OmniPlan runs on macOS only, so "
            "this should not block .oplx generation on other platforms; emit "
            "attachments from a Mac, or skip <attachment> elements entirely."
        )

    try:
        from Foundation import NSURL  # type: ignore[import-not-found]
    except ImportError as exc:
        raise BookmarkUnavailableError(
            "pyobjc-framework-Cocoa is not installed. Install the optional "
            "macOS extra: `pip install 'oplx-tools[macos]'` (or "
            "`uv pip install 'oplx-tools[macos]'`)."
        ) from exc

    abspath = str(Path(path).resolve())
    if not Path(abspath).exists():
        raise FileNotFoundError(
            f"Cannot generate bookmark for missing file: {abspath}"
        )

    url = NSURL.fileURLWithPath_(abspath)
    bookmark, err = url.bookmarkDataWithOptions_includingResourceValuesForKeys_relativeToURL_error_(
        0, None, None, None,
    )
    if err is not None or bookmark is None:
        raise OSError(f"NSURL bookmarkDataWithOptions failed for {abspath}: {err}")

    uri = url.absoluteString()
    b64 = base64.b64encode(bytes(bookmark)).decode("ascii")
    return uri, b64
