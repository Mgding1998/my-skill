#!/usr/bin/env python3
"""Validate production SVG icons against the icon-design skill contract."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path
import re
import sys
import xml.etree.ElementTree as ET

from svg_geometry import Bounds, GeometryError, measure_svg_bounds


SVG_NAMESPACE = "http://www.w3.org/2000/svg"
SVG_NAME = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
NUMBER = re.compile(r"^\s*([-+]?(?:\d+(?:\.\d*)?|\.\d+))(?:px)?\s*$")
URL_FUNCTION = re.compile(r"url\s*\(", re.IGNORECASE)
UNSAFE_DOCUMENT_PATTERNS = {
    "<!doctype": "DOCTYPE declarations are not allowed in production SVGs.",
    "<?xml-stylesheet": "External XML stylesheets are not allowed in production SVGs.",
}
FORBIDDEN_TAGS = {
    "animate",
    "animateMotion",
    "animateTransform",
    "foreignObject",
    "image",
    "script",
    "set",
    "style",
    "text",
    "use",
}
COMPLEX_TAGS = {
    "clipPath",
    "defs",
    "filter",
    "linearGradient",
    "mask",
    "pattern",
    "radialGradient",
    "symbol",
}
VECTOR_TAGS = {"circle", "ellipse", "line", "path", "polygon", "polyline", "rect"}
KNOWN_TAGS = (
    {"desc", "g", "svg", "title"} | FORBIDDEN_TAGS | COMPLEX_TAGS | VECTOR_TAGS
)
NON_RENDERING_CONTAINERS = COMPLEX_TAGS
BLACK_VALUES = {
    "#000",
    "#000000",
    "black",
    "rgb(0 0 0)",
    "rgb(0,0,0)",
    "rgba(0,0,0,1)",
}
NON_CIRCLE_AREA = 289.0
AREA_TOLERANCE = 1.0
CIRCLE_SIZE = 19.0
CIRCLE_TOLERANCE = 0.1


@dataclass(frozen=True)
class Issue:
    severity: str
    path: Path
    message: str


def local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def namespace_name(tag: str) -> str:
    if tag.startswith("{") and "}" in tag:
        return tag[1:].split("}", 1)[0]
    return ""


def parse_style(raw: str | None) -> dict[str, str]:
    if not raw:
        return {}
    declarations: dict[str, str] = {}
    for item in raw.split(";"):
        if ":" not in item:
            continue
        name, value = item.split(":", 1)
        declarations[name.strip()] = value.strip()
    return declarations


def parse_length(raw: str | None) -> float | None:
    if raw is None:
        return None
    match = NUMBER.match(raw)
    return float(match.group(1)) if match else None


def parse_view_box(raw: str | None) -> list[float] | None:
    if raw is None:
        return None
    try:
        values = [float(value) for value in re.split(r"[\s,]+", raw.strip())]
    except ValueError:
        return None
    return values if len(values) == 4 else None


def is_close_sequence(values: list[float] | None, expected: list[float]) -> bool:
    return values is not None and all(
        abs(actual - target) <= 1e-6 for actual, target in zip(values, expected)
    )


def normalized_paint(value: str) -> str:
    return re.sub(r"\s+", " ", value.strip()).lower()


def validate_file(
    path: Path,
    allow_black: bool = False,
    size_class: str | None = None,
) -> list[Issue]:
    issues: list[Issue] = []

    if not SVG_NAME.fullmatch(path.stem):
        issues.append(
            Issue(
                "ERROR",
                path,
                "File name must be lowercase kebab-case without spaces or copy suffixes.",
            )
        )

    try:
        raw_svg = path.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as error:
        return issues + [Issue("ERROR", path, f"Cannot read SVG: {error}")]

    lowered_svg = raw_svg.lower()
    for marker, message in UNSAFE_DOCUMENT_PATTERNS.items():
        if marker in lowered_svg:
            issues.append(Issue("ERROR", path, message))

    try:
        root = ET.fromstring(raw_svg)
    except ET.ParseError as error:
        return issues + [Issue("ERROR", path, f"Cannot parse SVG: {error}")]

    if local_name(root.tag) != "svg":
        return issues + [Issue("ERROR", path, "Root element must be <svg>.")]
    if namespace_name(root.tag) != SVG_NAMESPACE:
        issues.append(
            Issue(
                "ERROR",
                path,
                f'Root <svg> must use xmlns="{SVG_NAMESPACE}".',
            )
        )

    if not is_close_sequence(parse_view_box(root.get("viewBox")), [0.0, 0.0, 24.0, 24.0]):
        issues.append(Issue("ERROR", path, 'viewBox must be exactly "0 0 24 24".'))

    for dimension in ("width", "height"):
        raw = root.get(dimension)
        if raw is not None and parse_length(raw) != 24.0:
            issues.append(
                Issue("ERROR", path, f'{dimension} must be 24, 24px, or omitted; found "{raw}".')
            )

    if normalized_paint(root.get("preserveAspectRatio", "")) == "none":
        issues.append(
            Issue("ERROR", path, 'Remove preserveAspectRatio="none" to prevent distortion.')
        )

    def walk(
        element: ET.Element,
        inherited_fill: str,
        inherited_stroke: str,
        rendered_context: bool,
    ) -> None:
        tag = local_name(element.tag)
        style = parse_style(element.get("style"))
        fill = style.get("fill", element.get("fill", inherited_fill))
        stroke = style.get("stroke", element.get("stroke", inherited_stroke))

        if namespace_name(element.tag) != SVG_NAMESPACE:
            issues.append(
                Issue("ERROR", path, f"Element <{tag}> must use the SVG namespace.")
            )

        for raw_name, value in element.attrib.items():
            name = local_name(raw_name).lower()
            if name.startswith("on"):
                issues.append(
                    Issue("ERROR", path, f'Event attribute "{name}" is not allowed.')
                )
            if name == "href":
                issues.append(
                    Issue("ERROR", path, f'External/reference attribute "{name}" is not allowed.')
                )
            if URL_FUNCTION.search(value):
                issues.append(
                    Issue("ERROR", path, f'URL-valued attribute "{name}" is not allowed.')
                )

        if tag in FORBIDDEN_TAGS:
            issues.append(Issue("ERROR", path, f"Forbidden SVG element <{tag}>."))
        elif tag in COMPLEX_TAGS:
            issues.append(
                Issue(
                    "WARN",
                    path,
                    f"Complex element <{tag}> is outside the simple monochrome icon contract.",
                )
            )
        elif tag not in KNOWN_TAGS:
            issues.append(Issue("ERROR", path, f"Unsupported SVG element <{tag}>."))

        if element.get("style"):
            issues.append(Issue("WARN", path, f"Remove inline style from <{tag}>."))
        if element.get("class"):
            issues.append(Issue("WARN", path, f"Remove class from <{tag}>."))

        current_rendered_context = (
            rendered_context and tag not in NON_RENDERING_CONTAINERS
        )
        if current_rendered_context and tag in VECTOR_TAGS:
            normalized_fill = normalized_paint(fill)
            normalized_stroke = normalized_paint(stroke)

            if normalized_stroke not in {"", "none"}:
                issues.append(
                    Issue(
                        "ERROR",
                        path,
                        f"Visible stroke on <{tag}> must be expanded to filled geometry.",
                    )
                )

            if tag == "line":
                issues.append(
                    Issue(
                        "ERROR",
                        path,
                        "<line> cannot produce filled production geometry; expand it to a path.",
                    )
                )
            elif normalized_fill == "currentcolor":
                pass
            elif normalized_fill in {"", "none"}:
                pass
            elif allow_black and normalized_fill in BLACK_VALUES:
                pass
            else:
                issues.append(
                    Issue(
                        "ERROR",
                        path,
                        f'Visible fill on <{tag}> must use currentColor; found "{fill}".',
                    )
                )

            if tag == "path" and not (element.get("d") or "").strip():
                issues.append(Issue("ERROR", path, "<path> must have non-empty d data."))

        for child in element:
            walk(child, fill, stroke, current_rendered_context)

    walk(root, "black", "none", True)

    try:
        bounds = measure_svg_bounds(path)
    except GeometryError as error:
        issues.append(Issue("ERROR", path, f"Cannot measure visible bounds: {error}"))
    else:
        issues.extend(validate_visible_bounds(path, size_class, bounds))

    return deduplicate_issues(issues)


def validate_visible_bounds(
    path: Path,
    size_class: str | None,
    bounds: Bounds | None = None,
) -> list[Issue]:
    if size_class is not None and size_class not in {"auto", "circle", "non-circle"}:
        raise ValueError(f"Unsupported size class: {size_class}")

    if bounds is None:
        try:
            bounds = measure_svg_bounds(path)
        except GeometryError as error:
            return [Issue("ERROR", path, f"Cannot measure visible bounds: {error}")]

    issues: list[Issue] = []
    if (
        bounds.min_x < -CIRCLE_TOLERANCE
        or bounds.min_y < -CIRCLE_TOLERANCE
        or bounds.max_x > 24 + CIRCLE_TOLERANCE
        or bounds.max_y > 24 + CIRCLE_TOLERANCE
    ):
        issues.append(Issue("ERROR", path, "Visible geometry extends outside the 24x24 viewBox."))

    if size_class is None:
        return issues

    resolved_class = size_class
    if size_class == "auto":
        is_strict_circle_box = (
            abs(bounds.width - CIRCLE_SIZE) <= CIRCLE_TOLERANCE
            and abs(bounds.height - CIRCLE_SIZE) <= CIRCLE_TOLERANCE
            and abs(bounds.center_x - 12) <= CIRCLE_TOLERANCE
            and abs(bounds.center_y - 12) <= CIRCLE_TOLERANCE
        )
        resolved_class = "circle" if is_strict_circle_box else "non-circle"

    if resolved_class == "circle":
        if (
            abs(bounds.width - CIRCLE_SIZE) > CIRCLE_TOLERANCE
            or abs(bounds.height - CIRCLE_SIZE) > CIRCLE_TOLERANCE
            or abs(bounds.center_x - 12) > CIRCLE_TOLERANCE
            or abs(bounds.center_y - 12) > CIRCLE_TOLERANCE
        ):
            issues.append(
                Issue(
                    "ERROR",
                    path,
                    "Circular icons must have 19x19 visible bounds centered at (12,12); "
                    f"found {bounds.width:.4f}x{bounds.height:.4f} centered at "
                    f"({bounds.center_x:.4f},{bounds.center_y:.4f}).",
                )
            )
    elif abs(bounds.area - NON_CIRCLE_AREA) > AREA_TOLERANCE:
        issues.append(
            Issue(
                "ERROR",
                path,
                "Non-circular visible bounds must have area 289 px^2 (17x17) "
                f"within +/-{AREA_TOLERANCE:g}; found {bounds.width:.4f}x"
                f"{bounds.height:.4f} = {bounds.area:.4f} px^2.",
            )
        )
    return issues


def deduplicate_issues(issues: list[Issue]) -> list[Issue]:
    seen: set[tuple[str, Path, str]] = set()
    result: list[Issue] = []
    for issue in issues:
        key = (issue.severity, issue.path, issue.message)
        if key not in seen:
            seen.add(key)
            result.append(issue)
    return result


def validate_variant_pairs(
    paths: list[Path],
    require_variant_suffix: bool = False,
) -> list[Issue]:
    by_directory: dict[Path, dict[str, dict[str, Path]]] = {}
    issues: list[Issue] = []
    for path in paths:
        stem = path.stem
        if stem.endswith("-line"):
            base, variant = stem[:-5], "line"
        elif stem.endswith("-fill"):
            base, variant = stem[:-5], "fill"
        else:
            if require_variant_suffix:
                issues.append(
                    Issue(
                        "ERROR",
                        path,
                        "File must end in -line.svg or -fill.svg for a paired delivery.",
                    )
                )
            continue
        by_directory.setdefault(path.parent, {}).setdefault(base, {})[variant] = path

    for groups in by_directory.values():
        for base, variants in sorted(groups.items()):
            missing = {"line", "fill"} - variants.keys()
            if not missing:
                continue
            existing_path = next(iter(variants.values()))
            issues.append(
                Issue(
                    "ERROR",
                    existing_path,
                    f'Variant pair "{base}" is missing: {", ".join(sorted(missing))}.',
                )
            )
    return issues


def collect_svg_paths(inputs: list[str]) -> list[Path]:
    paths: list[Path] = []
    for raw in inputs:
        path = Path(raw)
        if path.is_dir():
            paths.extend(candidate for candidate in path.rglob("*.svg") if candidate.is_file())
        elif path.is_file() and path.suffix.lower() == ".svg":
            paths.append(path)
    return sorted(set(candidate.resolve() for candidate in paths))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Validate 24x24 monochrome SVG icons for production delivery."
    )
    parser.add_argument("paths", nargs="+", help="SVG files or directories to scan recursively.")
    parser.add_argument(
        "--allow-black",
        action="store_true",
        help="Allow black fills when auditing raw Figma exports. Production should use currentColor.",
    )
    parser.add_argument(
        "--require-pairs",
        action="store_true",
        help="Require every *-line.svg to have *-fill.svg in the same directory and vice versa.",
    )
    parser.add_argument(
        "--require-variant-suffix",
        action="store_true",
        help=(
            "Reject files without -line.svg or -fill.svg and require complete pairs. "
            "Use only for paired icon sets, not Editor-style singletons."
        ),
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Treat warnings as errors; this does not add manual visual checks.",
    )
    parser.add_argument(
        "--size-class",
        choices=("auto", "circle", "non-circle"),
        help=(
            "Validate visible bounds: non-circle requires 289 px^2, circle requires "
            "19x19 centered at (12,12), and auto accepts either rule."
        ),
    )
    parser.add_argument(
        "--report-bounds",
        action="store_true",
        help="Print measured visible bounds and bounding-box area for every SVG.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    paths = collect_svg_paths(args.paths)
    if not paths:
        print("No SVG files found.", file=sys.stderr)
        return 2

    issues: list[Issue] = []
    for path in paths:
        issues.extend(
            validate_file(
                path,
                allow_black=args.allow_black,
                size_class=args.size_class,
            )
        )
    if args.require_pairs or args.require_variant_suffix:
        issues.extend(
            validate_variant_pairs(
                paths,
                require_variant_suffix=args.require_variant_suffix,
            )
        )

    issues = deduplicate_issues(issues)
    for issue in issues:
        print(f"[{issue.severity}] {issue.path}: {issue.message}")

    if args.report_bounds:
        for path in paths:
            try:
                bounds = measure_svg_bounds(path)
            except GeometryError as error:
                print(f"[BOUNDS] {path}: unavailable ({error})")
                continue
            print(
                f"[BOUNDS] {path}: x={bounds.min_x:.4f}, y={bounds.min_y:.4f}, "
                f"width={bounds.width:.4f}, height={bounds.height:.4f}, "
                f"area={bounds.area:.4f}"
            )

    errors = sum(issue.severity == "ERROR" for issue in issues)
    warnings = sum(issue.severity == "WARN" for issue in issues)
    print(f"Checked {len(paths)} SVG file(s): {errors} error(s), {warnings} warning(s).")
    return 1 if errors or (args.strict and warnings) else 0


if __name__ == "__main__":
    raise SystemExit(main())
