"""Public API for the directory atomic remover tools.

Exports :class:`DirectoryAtomicRemover`, which renames a directory out of the
way and deletes it in the background while leaving a clean replacement in
place.
"""

from .core import DirectoryAtomicRemover

__all__ = ["DirectoryAtomicRemover"]
