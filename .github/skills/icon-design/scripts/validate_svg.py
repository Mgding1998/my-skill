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

    vector_count = 0
    visible_fill_count = 0

    def walk(element: ET.Element, inherited_fill: str, inherited_stroke: str) -> None:
        nonlocal vector_count, visible_fill_count

        tag = local_name(element.tag)
        style = parse_style(element.get("style"))
        fill = style.get("fill", element.get("fill", inherited_fill))
        stroke = style.get("stroke", element.get("stroke", inherited_stroke))

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
                issues.append(
                    Issue(
                        "ERROR",
                        path,
                        f"Visible stroke on <{tag}> must be expanded to filled geometry.",
                    )
                )

            if normalized_fill == "currentcolor":
                visible_fill_count += 1
            elif normalized_fill in {"", "none"}:
                pass
            elif allow_black and normalized_fill in BLACK_VALUES:
                visible_fill_count += 1
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
            walk(child, fill, stroke)

    walk(root, "black", "none")

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
