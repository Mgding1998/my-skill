from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
import tempfile
import unittest

from svg_geometry import measure_svg_bounds
from validate_svg import main, validate_file, validate_variant_pairs


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

    def test_non_circular_bounds_accept_289_square_pixels(self) -> None:
        svg = """\
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none">
  <rect x="3.5" y="3.5" width="17" height="17" fill="currentColor"/>
</svg>
"""
        with tempfile.TemporaryDirectory() as directory:
            path = self.write_svg(directory, "box-line.svg", svg)
            self.assertEqual(validate_file(path, size_class="non-circle"), [])
            bounds = measure_svg_bounds(path)
            self.assertEqual((bounds.width, bounds.height, bounds.area), (17, 17, 289))

    def test_non_circular_bounds_reject_20_by_16(self) -> None:
        svg = """\
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none">
  <path fill="currentColor" d="M2 4h20v16H2z"/>
</svg>
"""
        with tempfile.TemporaryDirectory() as directory:
            path = self.write_svg(directory, "carousel-line.svg", svg)
            messages = [
                issue.message
                for issue in validate_file(path, size_class="non-circle")
            ]
            self.assertTrue(any("289 px^2" in message for message in messages))
            self.assertTrue(any("320.0000" in message for message in messages))

    def test_circle_bounds_require_19_by_19_at_canvas_center(self) -> None:
        svg = """\
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none">
  <circle cx="12" cy="12" r="9.5" fill="currentColor"/>
</svg>
"""
        with tempfile.TemporaryDirectory() as directory:
            path = self.write_svg(directory, "face-line.svg", svg)
            self.assertEqual(validate_file(path, size_class="circle"), [])
            self.assertEqual(validate_file(path, size_class="auto"), [])

    def test_transforms_are_included_in_visible_bounds(self) -> None:
        svg = """\
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none">
  <g transform="translate(3.5 3.5)">
    <path fill="currentColor" d="M0 0h17v17H0z"/>
  </g>
</svg>
"""
        with tempfile.TemporaryDirectory() as directory:
            path = self.write_svg(directory, "box-fill.svg", svg)
            bounds = measure_svg_bounds(path)
            self.assertEqual((bounds.min_x, bounds.min_y), (3.5, 3.5))
            self.assertEqual((bounds.width, bounds.height, bounds.area), (17, 17, 289))

    def test_renderability_is_checked_without_size_class(self) -> None:
        samples = {
            "defs-line.svg": (
                """\
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none">
  <defs><path fill="currentColor" d="M3.5 3.5h17v17h-17z"/></defs>
</svg>
""",
                "no measurable visible fill geometry",
            ),
            "hidden-line.svg": (
                """\
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none">
  <rect x="3.5" y="3.5" width="17" height="17" fill="currentColor" opacity="0"/>
</svg>
""",
                "no measurable visible fill geometry",
            ),
            "malformed-line.svg": (
                """\
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none">
  <path fill="currentColor" d="M3.5 3.5 L broken"/>
</svg>
""",
                "malformed SVG path data",
            ),
            "outside-line.svg": (
                """\
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none">
  <rect x="30" y="30" width="17" height="17" fill="currentColor"/>
</svg>
""",
                "outside the 24x24 viewBox",
            ),
        }
        with tempfile.TemporaryDirectory() as directory:
            for name, (svg, expected) in samples.items():
                with self.subTest(name=name):
                    path = self.write_svg(directory, name, svg)
                    messages = [issue.message for issue in validate_file(path)]
                    self.assertTrue(
                        any(expected in message for message in messages),
                        messages,
                    )

    def test_unsafe_css_events_and_references_are_rejected(self) -> None:
        svg = """\
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24"
     fill="currentColor" onload="alert(1)">
  <style>rect { fill: red; }</style>
  <rect x="3.5" y="3.5" width="17" height="17" onclick="alert(1)"/>
  <use href="https://example.com/icon.svg#shape"/>
</svg>
"""
        with tempfile.TemporaryDirectory() as directory:
            path = self.write_svg(directory, "unsafe-line.svg", svg)
            messages = [issue.message for issue in validate_file(path)]
            self.assertTrue(any("<style>" in message for message in messages))
            self.assertTrue(any("Event attribute" in message for message in messages))
            self.assertTrue(any('attribute "href"' in message for message in messages))

    def test_missing_svg_namespace_is_rejected(self) -> None:
        svg = """\
<svg viewBox="0 0 24 24" fill="none">
  <rect x="3.5" y="3.5" width="17" height="17" fill="currentColor"/>
</svg>
"""
        with tempfile.TemporaryDirectory() as directory:
            path = self.write_svg(directory, "box-line.svg", svg)
            messages = [issue.message for issue in validate_file(path)]
            self.assertTrue(any("xmlns" in message for message in messages))

    def test_zero_area_fill_geometry_is_rejected(self) -> None:
        samples = {
            "line-line.svg": """\
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none">
  <line x1="3.5" y1="3.5" x2="20.5" y2="20.5" fill="currentColor"/>
</svg>
""",
            "degenerate-line.svg": """\
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none">
  <path fill="currentColor" d="M3.5 3.5L20.5 20.5"/>
</svg>
""",
        }
        with tempfile.TemporaryDirectory() as directory:
            for name, svg in samples.items():
                with self.subTest(name=name):
                    path = self.write_svg(directory, name, svg)
                    messages = [issue.message for issue in validate_file(path)]
                    self.assertTrue(
                        any(
                            "no measurable visible fill geometry" in message
                            for message in messages
                        ),
                        messages,
                    )

    def test_variant_suffix_requirement_rejects_singletons(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            singleton = self.write_svg(directory, "align-center.svg")
            self.assertEqual(validate_variant_pairs([singleton]), [])
            messages = [
                issue.message
                for issue in validate_variant_pairs(
                    [singleton],
                    require_variant_suffix=True,
                )
            ]
            self.assertTrue(any("-line.svg or -fill.svg" in message for message in messages))

    def test_cli_strict_treats_warnings_as_errors(self) -> None:
        svg = """\
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none">
  <rect x="3.5" y="3.5" width="17" height="17" style="fill: currentColor"/>
</svg>
"""
        with tempfile.TemporaryDirectory() as directory:
            path = self.write_svg(directory, "box-line.svg", svg)
            with redirect_stdout(StringIO()):
                self.assertEqual(main([str(path)]), 0)
                self.assertEqual(main([str(path), "--strict"]), 1)

    def test_cli_rejects_invalid_geometry_without_size_class(self) -> None:
        svg = """\
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none">
  <path fill="currentColor" d="M3.5 3.5L20.5 20.5"/>
</svg>
"""
        with tempfile.TemporaryDirectory() as directory:
            path = self.write_svg(directory, "invalid-line.svg", svg)
            with redirect_stdout(StringIO()):
                self.assertEqual(main([str(path)]), 1)


if __name__ == "__main__":
    unittest.main()
