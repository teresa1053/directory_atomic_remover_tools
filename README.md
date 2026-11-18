# directory_atomic_remover_tools

A tiny standard-library-only helper that replaces a directory with an empty one
without ever exposing a partially removed tree to concurrent readers.

```python
from pathlib import Path
from directory_atomic_remover_tools import DirectoryAtomicRemover

target = Path("build")
remover = DirectoryAtomicRemover(target)
renamed = remover.remove()

# The original path now exists and is empty. The old tree is being deleted
# in a background thread at `renamed`.
remover.wait_for_deletion()
```

## Why this exists

Deleting a directory in place with `shutil.rmtree` is observable: a reader that
walks the tree while it is being removed can see a mix of present and absent
entries. For cases such as replacing a cache directory or a generated output
folder, that half-removed state is worse than either the old tree or an empty
directory.

The remover takes the simplest atomic step available on POSIX and Windows:
rename the directory to a temporary sibling name, then create a fresh empty
directory at the original path. Readers that look at the original path see
either the complete old tree (before the rename) or the empty replacement
(after it). The renamed tree is deleted afterwards in a daemon thread so the
caller is not blocked by a large tree.

The trade-off is that the deletion is asynchronous. If the process exits before
the background thread finishes, the renamed directory is left on disk. A
caller that needs deterministic cleanup can call `wait_for_deletion()`; the
library does not install signal handlers or atexit hooks, because doing so
would surprise callers that manage their own shutdown.

## API

`DirectoryAtomicRemover(target, *, tmp_prefix=".directory_atomic_remover_tmp_")`

- `target`: a `str` or `pathlib.Path` pointing at the directory to replace.
- `tmp_prefix`: prefix for the temporary sibling name used during deletion.

Methods and properties:

- `remove()`: renames the target out of the way, creates an empty directory at
  the original path, and starts background deletion. Returns the `Path` of the
  renamed directory, or `None` if the target does not exist. Raises
  `NotADirectoryError` if the target is a file or a symlink.
- `wait_for_deletion(timeout=None)`: joins the background deletion thread.
  Returns `True` if the thread finished, `False` if `timeout` expired first.
- `target`: the original path passed to the constructor.
- `renamed_path`: the temporary path while deletion is in progress, otherwise
  `None`.

## Edge cases

- A missing target is a no-op: `remove()` returns `None`.
- A file or symlink at the target path raises `NotADirectoryError` and is left
  untouched. Symlinks are not followed, because renaming the link would not
  remove the directory the caller is probably thinking of.
- If creating the empty replacement fails, the rename is rolled back and the
  error is re-raised, so the original tree is preserved.
- The background deletion uses `shutil.rmtree(..., ignore_errors=True)`. A
  permissions problem in one branch does not abort the rest of the cleanup, but
  the renamed directory may remain partially populated. Inspect
  `renamed_path` before calling `wait_for_deletion()` if you need to detect
  that case.
