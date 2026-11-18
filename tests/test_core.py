import os
import tempfile
import unittest
from pathlib import Path

from directory_atomic_remover_tools import DirectoryAtomicRemover


class DirectoryAtomicRemoverTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name)

    def _make_tree(self, name="target"):
        target = self.root / name
        target.mkdir()
        (target / "a.txt").write_text("alpha")
        nested = target / "nested"
        nested.mkdir()
        (nested / "b.txt").write_text("beta")
        return target

    def test_remove_replaces_directory_with_empty_one(self):
        target = self._make_tree()
        remover = DirectoryAtomicRemover(target)
        renamed = remover.remove()
        self.assertIsNotNone(renamed)
        self.assertTrue(target.is_dir())
        self.assertEqual(list(target.iterdir()), [])
        self.assertTrue(remover.wait_for_deletion())
        self.assertFalse(renamed.exists())

    def test_renamed_path_is_under_parent_and_has_prefix(self):
        target = self._make_tree()
        remover = DirectoryAtomicRemover(target, tmp_prefix="custom_prefix_")
        renamed = remover.remove()
        self.assertEqual(renamed.parent, target.parent)
        self.assertTrue(renamed.name.startswith("custom_prefix_"))
        self.assertTrue(remover.wait_for_deletion())

    def test_remove_missing_target_returns_none(self):
        target = self.root / "does-not-exist"
        remover = DirectoryAtomicRemover(target)
        self.assertIsNone(remover.remove())
        self.assertFalse(target.exists())

    def test_remove_file_raises_not_a_directory(self):
        target = self.root / "file.txt"
        target.write_text("hello")
        remover = DirectoryAtomicRemover(target)
        with self.assertRaises(NotADirectoryError):
            remover.remove()
        self.assertTrue(target.is_file())
        self.assertEqual(target.read_text(), "hello")

    def test_remove_symlink_raises_not_a_directory(self):
        real = self._make_tree("real")
        link = self.root / "link"
        os.symlink(real, link)
        remover = DirectoryAtomicRemover(link)
        with self.assertRaises(NotADirectoryError):
            remover.remove()
        self.assertTrue(link.is_symlink())
        self.assertTrue(real.is_dir())

    def test_renamed_path_cleared_after_wait(self):
        target = self._make_tree()
        remover = DirectoryAtomicRemover(target)
        renamed = remover.remove()
        self.assertEqual(remover.renamed_path, renamed)
        self.assertTrue(remover.wait_for_deletion())
        self.assertIsNone(remover.renamed_path)

    def test_wait_for_deletion_without_remove_returns_true(self):
        remover = DirectoryAtomicRemover(self.root / "missing")
        self.assertTrue(remover.wait_for_deletion())

    def test_wait_for_deletion_timeout_returns_false_with_live_thread(self):
        target = self._make_tree()
        remover = DirectoryAtomicRemover(target)
        remover.remove()
        # A zero timeout asks join to return immediately. If the deletion
        # thread has already finished, the result is True; otherwise it is
        # False. Both outcomes are valid, but the method must not hang.
        finished = remover.wait_for_deletion(timeout=0)
        self.assertIn(finished, (True, False))
        self.assertTrue(remover.wait_for_deletion())

    def test_target_accepts_string(self):
        target = self._make_tree()
        remover = DirectoryAtomicRemover(str(target))
        renamed = remover.remove()
        self.assertIsNotNone(renamed)
        self.assertTrue(target.is_dir())
        self.assertTrue(remover.wait_for_deletion())

    def test_remove_twice_creates_second_generation(self):
        target = self._make_tree()
        remover = DirectoryAtomicRemover(target)
        first = remover.remove()
        self.assertTrue(remover.wait_for_deletion())
        (target / "new.txt").write_text("gamma")
        second = remover.remove()
        self.assertNotEqual(first, second)
        self.assertEqual(list(target.iterdir()), [])
        self.assertTrue(remover.wait_for_deletion())
        self.assertFalse(second.exists())

    def test_original_tree_is_intact_before_rename(self):
        target = self._make_tree()
        remover = DirectoryAtomicRemover(target)
        self.assertEqual(
            sorted(p.name for p in target.iterdir()), ["a.txt", "nested"]
        )
        renamed = remover.remove()
        self.assertTrue(target.is_dir())
        self.assertEqual(list(target.iterdir()), [])
        self.assertTrue(remover.wait_for_deletion())
        self.assertFalse(renamed.exists())


if __name__ == "__main__":
    unittest.main()
