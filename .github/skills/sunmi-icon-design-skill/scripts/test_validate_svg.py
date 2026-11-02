from pathlib import Path
import tempfile
import unittest

from validate_svg import validate_file, validate_variant_pairs


VALID_SVG = """\
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none">
  <path fill="currentColor" d="M4 11h16v2H4z"/>
</svg>
"""


class ValidateSvgTests(unittest.TestCase):
    def write_svg(self, directory: str, name: str, content: str = VALID_SVG) -> Path:
        path = Path(directory, name)
        path.write_text(content, encoding="utf-8")
        return path

    def test_valid_current_color_icon(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = self.write_svg(directory, "add-line.svg")
            self.assertEqual(validate_file(path), [])

    def test_fixed_black_requires_explicit_raw_export_mode(self) -> None:
        svg = VALID_SVG.replace("currentColor", "black")
        with tempfile.TemporaryDirectory() as directory:
            path = self.write_svg(directory, "add-line.svg", svg)
            self.assertTrue(any(issue.severity == "ERROR" for issue in validate_file(path)))
            self.assertEqual(validate_file(path, allow_black=True), [])

    def test_visible_stroke_is_rejected(self) -> None:
        svg = """\
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none">
  <path d="M4 12h16" stroke="currentColor" stroke-width="2"/>
</svg>
"""
        with tempfile.TemporaryDirectory() as directory:
            path = self.write_svg(directory, "minus-line.svg", svg)
            messages = [issue.message for issue in validate_file(path)]
            self.assertTrue(any("stroke" in message for message in messages))

    def test_invalid_name_and_view_box_are_rejected(self) -> None:
        svg = VALID_SVG.replace('viewBox="0 0 24 24"', 'viewBox="0 0 20 20"')
        with tempfile.TemporaryDirectory() as directory:
            path = self.write_svg(directory, "Add Line.svg", svg)
            messages = [issue.message for issue in validate_file(path)]
            self.assertTrue(any("kebab-case" in message for message in messages))
            self.assertTrue(any("viewBox" in message for message in messages))

    def test_forbidden_raster_content_is_rejected(self) -> None:
        svg = """\
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none">
  <path fill="currentColor" d="M4 4h16v16H4z"/>
  <image href="icon.png" width="24" height="24"/>
</svg>
"""
        with tempfile.TemporaryDirectory() as directory:
            path = self.write_svg(directory, "photo-fill.svg", svg)
            messages = [issue.message for issue in validate_file(path)]
            self.assertTrue(any("<image>" in message for message in messages))

    def test_variant_pairing(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            line = self.write_svg(directory, "home-line.svg")
            self.assertEqual(len(validate_variant_pairs([line])), 1)
            fill = self.write_svg(directory, "home-fill.svg")
            self.assertEqual(validate_variant_pairs([line, fill]), [])


if __name__ == "__main__":
    unittest.main()
