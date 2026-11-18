import os
import shutil
import tempfile
import threading
import uuid
from pathlib import Path


class DirectoryAtomicRemover:
    """Remove a directory atomically from the perspective of readers.

    The remover renames the target directory out of the way, creates a fresh
    empty directory at the original path, and deletes the renamed tree in a
    background thread. Readers that open the original path never observe a
    half-removed tree: they either see the old complete tree (before the
    rename) or the new empty replacement (after the rename).

    The background deletion is best effort. If the process exits before the
    thread finishes, the renamed directory remains on disk. Call
    :meth:`wait_for_deletion` when you need deterministic cleanup, for example
    in tests or before shutting down.

    A failure during the initial rename leaves the original directory intact
    and raises the underlying :class:`OSError`. A failure while creating the
    replacement directory rolls the rename back and re-raises the error.
    """

    def __init__(self, target, *, tmp_prefix=".directory_atomic_remover_tmp_"):
        """Create a remover for ``target``.

        ``target`` may be a string or :class:`pathlib.Path`. The directory is
        not touched until :meth:`remove` is called.
        """
        self._target = Path(target)
        self._tmp_prefix = tmp_prefix
        self._thread = None
        self._renamed_path = None

    @property
    def target(self):
        """The original path passed to the constructor."""
        return self._target

    @property
    def renamed_path(self):
        """The temporary path used while the old tree is being deleted.

        This is ``None`` before :meth:`remove` succeeds and after the old tree
        has been fully removed and the internal reference cleared.
        """
        return self._renamed_path

    def remove(self):
        """Atomically replace the target directory with an empty directory.

        Returns the path of the renamed directory that is being deleted in the
        background. If the target does not exist, returns ``None`` and does
        nothing.

        The target must be a directory. If it is a file or a symlink, a
        :class:`NotADirectoryError` is raised and the target is left untouched.
        """
        target = self._target

        if not target.exists() and not target.is_symlink():
            return None

        if target.is_symlink() or not target.is_dir():
            raise NotADirectoryError(
                "target is not a directory: {!r}".format(str(target))
            )

        parent = target.parent
        renamed = self._make_tmp_path(parent)

        os.rename(str(target), str(renamed))

        try:
            os.mkdir(str(target))
        except OSError:
            os.rename(str(renamed), str(target))
            raise

        self._renamed_path = renamed
        self._thread = threading.Thread(
            target=self._delete_tree,
            args=(renamed,),
            name="directory-atomic-remover",
            daemon=True,
        )
        self._thread.start()
        return renamed

    def wait_for_deletion(self, timeout=None):
        """Wait for the background deletion thread to finish.

        Returns ``True`` if the thread finished (or was never started) and
        ``False`` if ``timeout`` expired first. ``timeout`` is in seconds and
        matches :meth:`threading.Thread.join`.
        """
        thread = self._thread
        if thread is None:
            return True
        thread.join(timeout)
        if thread.is_alive():
            return False
        self._thread = None
        self._renamed_path = None
        return True

    def _make_tmp_path(self, parent):
        for _ in range(100):
            candidate = parent / (
                self._tmp_prefix + uuid.uuid4().hex
            )
            if not candidate.exists():
                return candidate
        raise FileExistsError(
            "could not allocate a temporary name in {!r}".format(str(parent))
        )

    def _delete_tree(self, path):
        # shutil.rmtree is used instead of os.rmdir because the renamed tree
        # may contain nested directories. ignore_errors keeps a permissions
        # problem in one branch from aborting the whole cleanup; the caller can
        # still detect a partial deletion by inspecting the renamed path.
        shutil.rmtree(str(path), ignore_errors=True)
