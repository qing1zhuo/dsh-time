"""设置项读写测试（桌宠大小、位置这些）。"""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.store import Settings, Store  # noqa: E402


class PetSettingsTests(unittest.TestCase):
    def test_defaults(self) -> None:
        settings = Settings()
        self.assertAlmostEqual(settings.pet_scale, 1.0)
        self.assertTrue(settings.pet_enabled)
        self.assertTrue(settings.pet_topmost)
        self.assertIsNone(settings.pet_x)

    def test_scale_is_clamped(self) -> None:
        self.assertAlmostEqual(Settings.from_dict({"pet_scale": 1.25}).pet_scale, 1.25)
        self.assertAlmostEqual(Settings.from_dict({"pet_scale": 9}).pet_scale, 1.8)
        self.assertAlmostEqual(Settings.from_dict({"pet_scale": 0.1}).pet_scale, 0.6)

    def test_bad_scale_falls_back(self) -> None:
        self.assertAlmostEqual(Settings.from_dict({"pet_scale": "big"}).pet_scale, 1.0)
        self.assertAlmostEqual(Settings.from_dict({"pet_scale": None}).pet_scale, 1.0)
        self.assertAlmostEqual(Settings.from_dict({"pet_scale": float("nan")}).pet_scale, 1.0)

    def test_scale_survives_roundtrip(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "schedule.json"
            store = Store(path)
            store.settings = Settings(pet_scale=1.24, pet_x=120, pet_y=340)
            self.assertTrue(store.save())

            restored = Store(path)
            restored.load()
            self.assertAlmostEqual(restored.settings.pet_scale, 1.24)
            self.assertEqual(restored.settings.pet_x, 120)
            self.assertEqual(restored.settings.pet_y, 340)


if __name__ == "__main__":
    unittest.main()
