import importlib
import sys
import unittest
from unittest.mock import patch
from pathlib import Path


class LocalConfigTests(unittest.TestCase):
    def test_openai_config_reads_environment_before_files(self):
        eval_dir = Path(__file__).resolve().parents[2] / "evaluation"
        sys.path.insert(0, str(eval_dir))
        try:
            module = importlib.import_module("hypergraphrag.openai_config")
            module.load_openai_config.cache_clear()
            with patch.dict(
                "os.environ",
                {
                    "OPENAI_API_KEY": "unit-test-key",
                    "OPENAI_BASE_URL": "https://example.invalid/v1",
                    "OPENAI_MODEL": "deepseek-v4-flash",
                    "OPENAI_EMBED_MODEL": "local:Qwen/Qwen3-Embedding-0.6B",
                },
                clear=False,
            ):
                config = module.load_openai_config()
            self.assertEqual(config.api_key, "unit-test-key")
            self.assertEqual(config.base_url, "https://example.invalid/v1")
            self.assertEqual(config.model, "deepseek-v4-flash")
            self.assertTrue(config.embed_model.startswith("local:"))
        finally:
            module.load_openai_config.cache_clear()
            if str(eval_dir) in sys.path:
                sys.path.remove(str(eval_dir))


if __name__ == "__main__":
    unittest.main()
