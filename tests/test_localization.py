import sys
import unittest
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from localization import DEFAULT_LANGUAGE, SUPPORTED_LANGUAGES, Localizer, normalize_language


class LocalizationTests(unittest.TestCase):
    def test_normalize_language_supports_chinese_english_and_indonesian(self):
        self.assertEqual(normalize_language("zh_CN"), "zh_CN")
        self.assertEqual(normalize_language("en_US"), "en_US")
        self.assertEqual(normalize_language("id_ID"), "id_ID")

    def test_default_language_is_english(self):
        self.assertEqual(DEFAULT_LANGUAGE, "en_US")

    def test_normalize_language_falls_back_to_english(self):
        self.assertEqual(normalize_language("fr_FR"), "en_US")

    def test_localizer_translates_status_labels(self):
        localizer = Localizer("id_ID")

        self.assertEqual(localizer.t("status.success"), "Berhasil")
        self.assertEqual(localizer.t("button.start"), "Mulai Kompresi")

    def test_supported_languages_have_display_names(self):
        self.assertEqual(set(SUPPORTED_LANGUAGES), {"zh_CN", "en_US", "id_ID"})
        localizer = Localizer("en_US")

        self.assertEqual(localizer.language_name("id_ID"), "Bahasa Indonesia")


if __name__ == "__main__":
    unittest.main()
