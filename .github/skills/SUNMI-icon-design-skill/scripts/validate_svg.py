#!/usr/bin/env python3
"""Validate production SVG icons against the icon-design skill contract."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path
import re
import sys
import xml.etree.ElementTree as ET


SVG_NAME = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
NUMBER = re.compile(r"^\s*([-+]?(?:\d+(?:\.\d*)?|\.\d+))(?:px)?\s*$")
FORBIDDEN_TAGS = {
    "animate",
    "animateMotion",
    "animateTransform",
    "foreignObject",
    "image",
    "script",
    "set",
    "text",
}
COMPLEX_TAGS = {
    "clipPath",
    "filter",
    "linearGradient",
    "mask",
    "pattern",
    "radialGradient",
}
VECTOR_TAGS = {"circle", "ellipse", "line", "path", "polygon", "polyline", "rect"}
BLACK_VALUES = {
    "#000",
    "#000000",
    "black",
    "rgb(0 0 0)",
    "rgb(0,0,0)",
    "rgba(0,0,0,1)",
}
LINE_LAYER_IDS = ("Original", "Outlined")


@dataclass(frozen=True)
class Issue:
    severity: str
    path: Path
    message: str


def local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


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


def is_allowed_color(value: str, allow_black: bool) -> bool:
    normalized = normalized_paint(value)
    return normalized == "currentcolor" or (allow_black and normalized in BLACK_VALUES)


def validate_file(path: Path, allow_black: bool = False) -> list[Issue]:
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
        root = ET.parse(path).getroot()
    except (ET.ParseError, OSError) as error:
        return issues + [Issue("ERROR", path, f"Cannot parse SVG: {error}")]

    if local_name(root.tag) != "svg":
        return issues + [Issue("ERROR", path, "Root element must be <svg>.")]

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

    if root.get("style"):
        issues.append(Issue("WARN", path, "Remove inline style from the SVG root."))

    is_line_icon = path.stem.endswith("-line")
    original_layer: ET.Element | None = None
    outlined_layer: ET.Element | None = None

    if is_line_icon:
        top_level_graphics = [
            child for child in root if local_name(child.tag) not in {"desc", "title"}
        ]
        layer_ids = tuple(
            child.get("id", "") if local_name(child.tag) == "g" else ""
            for child in top_level_graphics
        )
        if layer_ids != LINE_LAYER_IDS:
            issues.append(
                Issue(
                    "ERROR",
                    path,
                    "Line SVG must contain exactly two top-level <g> layers in this order: "
                    "Original, Outlined.",
                )
            )
        else:
            original_layer, outlined_layer = top_level_graphics
            if normalized_paint(original_layer.get("display", "")) != "none":
                issues.append(
                    Issue(
                        "ERROR",
                        path,
                        'Original layer must use display="none" so it is hidden by default.',
                    )
                )
            outlined_style = parse_style(outlined_layer.get("style"))
            outlined_display = outlined_style.get(
                "display", outlined_layer.get("display", "")
            )
            outlined_visibility = outlined_style.get(
                "visibility", outlined_layer.get("visibility", "")
            )
            if normalized_paint(outlined_display) == "none" or normalized_paint(
                outlined_visibility
            ) in {"hidden", "collapse"}:
                issues.append(
                    Issue("ERROR", path, "Outlined layer must be visible by default.")
                )

    vector_count = 0
    visible_fill_count = 0
    original_stroke_count = 0
    outlined_fill_count = 0

    def walk(
        element: ET.Element,
        inherited_fill: str,
        inherited_stroke: str,
        inherited_stroke_width: str,
        inherited_linecap: str,
        inherited_linejoin: str,
        inherited_hidden: bool,
        line_layer: str | None,
    ) -> None:
        nonlocal vector_count, visible_fill_count
        nonlocal original_stroke_count, outlined_fill_count

        tag = local_name(element.tag)
        style = parse_style(element.get("style"))
        fill = style.get("fill", element.get("fill", inherited_fill))
        stroke = style.get("stroke", element.get("stroke", inherited_stroke))
        stroke_width = style.get(
            "stroke-width", element.get("stroke-width", inherited_stroke_width)
        )
        linecap = style.get(
            "stroke-linecap", element.get("stroke-linecap", inherited_linecap)
        )
        linejoin = style.get(
            "stroke-linejoin", element.get("stroke-linejoin", inherited_linejoin)
        )
        display = style.get("display", element.get("display", ""))
        visibility = style.get("visibility", element.get("visibility", ""))
        opacity = style.get("opacity", element.get("opacity", ""))
        try:
            fully_transparent = bool(opacity) and float(opacity) == 0.0
        except ValueError:
            fully_transparent = False
        hidden = (
            inherited_hidden
            or normalized_paint(display) == "none"
            or normalized_paint(visibility) in {"hidden", "collapse"}
            or fully_transparent
        )

        if element is original_layer:
            line_layer = "Original"
        elif element is outlined_layer:
            line_layer = "Outlined"

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

        if element.get("style"):
            issues.append(Issue("WARN", path, f"Remove inline style from <{tag}>."))

        if tag in VECTOR_TAGS:
            vector_count += 1
            normalized_fill = normalized_paint(fill)
            normalized_stroke = normalized_paint(stroke)

            if normalized_stroke not in {"", "none"}:
                if (
                    is_line_icon
                    and line_layer == "Original"
                    and hidden
                    and is_allowed_color(stroke, allow_black)
                ):
                    original_stroke_count += 1
                    if parse_length(stroke_width) is None or parse_length(stroke_width) <= 0:
                        issues.append(
                            Issue(
                                "ERROR",
                                path,
                                f"Original stroke on <{tag}> must define a positive stroke-width.",
                            )
                        )
                    if normalized_paint(linecap) not in {"butt", "round", "square"}:
                        issues.append(
                            Issue(
                                "ERROR",
                                path,
                                f"Original stroke on <{tag}> must define stroke-linecap.",
                            )
                        )
                    if normalized_paint(linejoin) not in {"miter", "round", "bevel"}:
                        issues.append(
                            Issue(
                                "ERROR",
                                path,
                                f"Original stroke on <{tag}> must define stroke-linejoin.",
                            )
                        )
                elif (
                    is_line_icon
                    and line_layer == "Original"
                    and hidden
                ):
                    issues.append(
                        Issue(
                            "ERROR",
                            path,
                            f'Original stroke on <{tag}> must use currentColor; found "{stroke}".',
                        )
                    )
                else:
                    issues.append(
                        Issue(
                            "ERROR",
                            path,
                            f"Stroke on <{tag}> is allowed only inside the hidden Original "
                            "layer of a Line SVG.",
                        )
                    )

            if line_layer == "Original" and normalized_fill not in {"", "none"}:
                issues.append(
                    Issue(
                        "ERROR",
                        path,
                        f'Original geometry on <{tag}> must use fill="none"; found "{fill}".',
                    )
                )
            elif is_allowed_color(fill, allow_black):
                if not hidden:
                    visible_fill_count += 1
                    if line_layer == "Outlined":
                        outlined_fill_count += 1
            elif normalized_fill in {"", "none"}:
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
            walk(
                child,
                fill,
                stroke,
                stroke_width,
                linecap,
                linejoin,
                hidden,
                line_layer,
            )

    walk(root, "black", "none", "", "", "", False, None)

    if vector_count == 0:
        issues.append(Issue("ERROR", path, "SVG must contain vector geometry."))
    elif visible_fill_count == 0:
        issues.append(
            Issue(
                "ERROR",
                path,
                "SVG has no visible currentColor fill geometry.",
            )
        )

    if is_line_icon and original_layer is not None and original_stroke_count == 0:
        issues.append(
            Issue(
                "ERROR",
                path,
                "Original layer must contain editable currentColor stroke geometry.",
            )
        )
    if is_line_icon and outlined_layer is not None and outlined_fill_count == 0:
        issues.append(
            Issue(
                "ERROR",
                path,
                "Outlined layer must contain visible currentColor fill geometry.",
            )
        )

    return deduplicate_issues(issues)


def deduplicate_issues(issues: list[Issue]) -> list[Issue]:
    seen: set[tuple[str, Path, str]] = set()
    result: list[Issue] = []
    for issue in issues:
        key = (issue.severity, issue.path, issue.message)
        if key not in seen:
            seen.add(key)
            result.append(issue)
    return result


def validate_variant_pairs(paths: list[Path]) -> list[Issue]:
    by_directory: dict[Path, dict[str, dict[str, Path]]] = {}
    for path in paths:
        stem = path.stem
        if stem.endswith("-line"):
            base, variant = stem[:-5], "line"
        elif stem.endswith("-fill"):
            base, variant = stem[:-5], "fill"
        else:
            continue
        by_directory.setdefault(path.parent, {}).setdefault(base, {})[variant] = path

    issues: list[Issue] = []
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
        description="Validate 24x24 monochrome SVG icons and dual-layer Line assets."
    )
    parser.add_argument("paths", nargs="+", help="SVG files or directories to scan recursively.")
    parser.add_argument(
        "--allow-black",
        action="store_true",
        help="Allow black paints when auditing raw Figma exports. Production should use currentColor.",
    )
    parser.add_argument(
        "--require-pairs",
        action="store_true",
        help="Require every *-line.svg to have *-fill.svg in the same directory and vice versa.",
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Return a failing status when warnings are present.",
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
        issues.extend(validate_file(path, allow_black=args.allow_black))
    if args.require_pairs:
        issues.extend(validate_variant_pairs(paths))

    issues = deduplicate_issues(issues)
    for issue in issues:
        print(f"[{issue.severity}] {issue.path}: {issue.message}")

    errors = sum(issue.severity == "ERROR" for issue in issues)
    warnings = sum(issue.severity == "WARN" for issue in issues)
    print(f"Checked {len(paths)} SVG file(s): {errors} error(s), {warnings} warning(s).")
    return 1 if errors or (args.strict and warnings) else 0


if __name__ == "__main__":
    raise SystemExit(main())
