import unittest

from nba2k26_trainer.core.scanner import scan_for_player_table_candidates


class MemoryWithoutHandle:
    def read_bytes(self, address: int, size: int):
        return None

    def read_wstring(self, address: int, max_len: int = 64):
        return None


class ScannerTests(unittest.TestCase):
    def test_scan_for_player_table_candidates_skips_fake_memory_without_handle(self):
        messages = []
        candidates = scan_for_player_table_candidates(
            MemoryWithoutHandle(),
            progress_callback=messages.append,
        )

        self.assertEqual(candidates, [])
        self.assertTrue(messages)
        self.assertIn("does not expose a process handle", messages[-1])


if __name__ == "__main__":
    unittest.main()
