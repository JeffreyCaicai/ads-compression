import sys
import unittest
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from localization import DEFAULT_LANGUAGE, SUPPORTED_LANGUAGES, TRANSLATIONS, Localizer, normalize_language
from settings import (
    MODE_H265_PRODUCTION_BEST_DETAIL,
    MODE_H265_PRODUCTION_BEST_DETAIL_2PASS,
    MODE_H265_PRODUCTION_AUTO_DETAIL_2PASS,
    MODE_H265_SMALL_FILE,
    MODE_H265_SMART_AUTO,
    MODE_SCREEN_SAFE_HIGH_MOTION,
)


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
        self.assertEqual(localizer.encoding_mode("high_motion"), "High Motion - Kualitas Gerak Lebih Baik")
        self.assertEqual(
            localizer.encoding_mode(MODE_SCREEN_SAFE_HIGH_MOTION),
            "Screen Safe - Gerak Tinggi Stabil",
        )
        self.assertEqual(
            localizer.encoding_mode(MODE_H265_SMALL_FILE),
            "H.265 Small File - Standard Content",
        )
        self.assertEqual(
            localizer.encoding_mode(MODE_H265_PRODUCTION_BEST_DETAIL),
            "H.265 Production - Best Detail",
        )
        self.assertEqual(
            localizer.encoding_mode(MODE_H265_PRODUCTION_BEST_DETAIL_2PASS),
            "H.265 Production - Best Detail (2-pass)",
        )
        self.assertEqual(
            localizer.encoding_mode(MODE_H265_SMART_AUTO),
            "H.265 Smart Auto - Analyze Content",
        )

    def test_supported_languages_have_display_names(self):
        self.assertEqual(set(SUPPORTED_LANGUAGES), {"zh_CN", "en_US", "id_ID"})
        localizer = Localizer("en_US")

        self.assertEqual(localizer.language_name("id_ID"), "Bahasa Indonesia")

    def test_auto_detail_mode_has_default_english_label(self):
        localizer = Localizer("en_US")

        self.assertEqual(
            localizer.t("encoding_mode.h265_production_auto_detail_2pass"),
            "H.265 Production - Auto Detail (2-pass)",
        )

    def test_supported_languages_define_quality_audit_messages(self):
        keys = {
            "message.quality_passed",
            "message.quality_retry_started",
            "message.quality_retry_kept_maximum",
            "message.quality_retry_restored_best",
            "message.quality_warning",
            "message.quality_check_failed",
        }

        for language in SUPPORTED_LANGUAGES:
            with self.subTest(language=language):
                self.assertTrue(keys.issubset(TRANSLATIONS[language]))


if __name__ == "__main__":
    unittest.main()
