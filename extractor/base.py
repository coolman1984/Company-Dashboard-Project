"""
base.py - the common contract every file-type extractor implements.

A subclass only has to declare which file types it handles, whether its
dependencies are available right now, and how to read one file into a
type-specific `content` dict. The base class stamps the universal envelope
(see raw.py) so all extractors produce interchangeable output.
"""
from __future__ import annotations

import os
from typing import Tuple

from . import raw


class Extractor:
    # Subclasses override these.
    name: str = "base"
    document_type: str = "unknown"
    extensions: Tuple[str, ...] = ()

    def handles(self, path: str) -> bool:
        return os.path.splitext(path)[1].lower() in self.extensions

    def is_available(self) -> Tuple[bool, str]:
        """Return (available, reason). Reason explains why not, if False."""
        return True, "ok"

    def extract_content(self, path: str):
        """Return (content_dict, warnings_list). Implemented by subclasses."""
        raise NotImplementedError

    def extract(self, path: str, intake_root: str) -> dict:
        """Read one file and return the full raw-document envelope."""
        content, warnings = self.extract_content(path)
        return raw.build_envelope(
            path=path,
            intake_root=intake_root,
            extractor_name=self.name,
            document_type=self.document_type,
            content=content,
            warnings=warnings,
        )


def optional_import(module_name: str):
    """Import a module if present; return None instead of raising.

    Lets an extractor advertise itself but report 'unavailable' cleanly when
    its third-party dependency (or Windows/COM) is missing, so the engine
    never crashes on a machine that lacks one library. Catches BaseException
    because some native dependencies fail at import time with low-level panics
    that are not ordinary Exceptions; genuine interrupts are still re-raised.
    """
    try:
        return __import__(module_name)
    except (KeyboardInterrupt, SystemExit):
        raise
    except BaseException:  # noqa: BLE001 - any import failure means "unavailable"
        return None
