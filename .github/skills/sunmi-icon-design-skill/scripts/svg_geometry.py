#!/usr/bin/env python3
"""Measure visible SVG geometry without external dependencies."""

from __future__ import annotations

from dataclasses import dataclass
import math
from pathlib import Path
import re
import xml.etree.ElementTree as ET


Matrix = tuple[float, float, float, float, float, float]
Point = tuple[float, float]

IDENTITY: Matrix = (1.0, 0.0, 0.0, 1.0, 0.0, 0.0)
NUMBER_PATTERN = r"[-+]?(?:\d*\.\d+|\d+\.?)(?:[eE][-+]?\d+)?"
PATH_TOKEN = re.compile(rf"[AaCcHhLlMmQqSsTtVvZz]|{NUMBER_PATTERN}")
NUMBER_TOKEN = re.compile(NUMBER_PATTERN)
TRANSFORM_TOKEN = re.compile(r"([A-Za-z]+)\s*\(([^)]*)\)")
PATH_ARITY = {
    "A": 7,
    "C": 6,
    "H": 1,
    "L": 2,
    "M": 2,
    "Q": 4,
    "S": 4,
    "T": 2,
    "V": 1,
}
SKIP_CONTAINERS = {
    "clipPath",
    "defs",
    "filter",
    "linearGradient",
    "mask",
    "pattern",
    "radialGradient",
    "symbol",
}


class GeometryError(ValueError):
    """Raised when visible geometry cannot be measured reliably."""


@dataclass
class Bounds:
    min_x: float = math.inf
    min_y: float = math.inf
    max_x: float = -math.inf
    max_y: float = -math.inf

    @property
    def is_empty(self) -> bool:
        return self.min_x == math.inf

    @property
    def width(self) -> float:
        return 0.0 if self.is_empty else self.max_x - self.min_x

    @property
    def height(self) -> float:
        return 0.0 if self.is_empty else self.max_y - self.min_y

    @property
    def area(self) -> float:
        return self.width * self.height

    @property
    def center_x(self) -> float:
        return (self.min_x + self.max_x) / 2

    @property
    def center_y(self) -> float:
        return (self.min_y + self.max_y) / 2

    def include(self, point: Point) -> None:
        x, y = point
        self.min_x = min(self.min_x, x)
        self.min_y = min(self.min_y, y)
        self.max_x = max(self.max_x, x)
        self.max_y = max(self.max_y, y)


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


def compose(left: Matrix, right: Matrix) -> Matrix:
    a1, b1, c1, d1, e1, f1 = left
    a2, b2, c2, d2, e2, f2 = right
    return (
        a1 * a2 + c1 * b2,
        b1 * a2 + d1 * b2,
        a1 * c2 + c1 * d2,
        b1 * c2 + d1 * d2,
        a1 * e2 + c1 * f2 + e1,
        b1 * e2 + d1 * f2 + f1,
    )


def transform_point(matrix: Matrix, point: Point) -> Point:
    a, b, c, d, e, f = matrix
    x, y = point
    return a * x + c * y + e, b * x + d * y + f


def parse_numbers(raw: str) -> list[float]:
    matches = list(NUMBER_TOKEN.finditer(raw))
    position = 0
    values: list[float] = []
    for match in matches:
        if re.sub(r"[\s,]+", "", raw[position : match.start()]):
            raise GeometryError(f'Invalid numeric list: "{raw}".')
        values.append(float(match.group()))
        position = match.end()
    if re.sub(r"[\s,]+", "", raw[position:]):
        raise GeometryError(f'Invalid numeric list: "{raw}".')
    return values


def parse_transform(raw: str | None) -> Matrix:
    if not raw:
        return IDENTITY

    matrix = IDENTITY
    position = 0
    for match in TRANSFORM_TOKEN.finditer(raw):
        if re.sub(r"[\s,]+", "", raw[position : match.start()]):
            raise GeometryError(f'Invalid transform: "{raw}".')
        name = match.group(1)
        values = parse_numbers(match.group(2))

        if name == "matrix" and len(values) == 6:
            operation: Matrix = (
                values[0],
                values[1],
                values[2],
                values[3],
                values[4],
                values[5],
            )
        elif name == "translate" and len(values) in {1, 2}:
            operation = (
                1.0,
                0.0,
                0.0,
                1.0,
                values[0],
                values[1] if len(values) == 2 else 0.0,
            )
        elif name == "scale" and len(values) in {1, 2}:
            operation = (
                values[0],
                0.0,
                0.0,
                values[1] if len(values) == 2 else values[0],
                0.0,
                0.0,
            )
        elif name == "rotate" and len(values) in {1, 3}:
            angle = math.radians(values[0])
            rotation: Matrix = (
                math.cos(angle),
                math.sin(angle),
                -math.sin(angle),
                math.cos(angle),
                0.0,
                0.0,
            )
            if len(values) == 3:
                cx, cy = values[1:]
                operation = compose(
                    compose((1, 0, 0, 1, cx, cy), rotation),
                    (1, 0, 0, 1, -cx, -cy),
                )
            else:
                operation = rotation
        elif name == "skewX" and len(values) == 1:
            operation = (1, 0, math.tan(math.radians(values[0])), 1, 0, 0)
        elif name == "skewY" and len(values) == 1:
            operation = (1, math.tan(math.radians(values[0])), 0, 1, 0, 0)
        else:
            raise GeometryError(f'Unsupported transform: "{match.group()}".')

        matrix = compose(matrix, operation)
        position = match.end()

    if position == 0 or re.sub(r"[\s,]+", "", raw[position:]):
        raise GeometryError(f'Invalid transform: "{raw}".')
    return matrix


def tokenize_path(data: str) -> list[str]:
    tokens: list[str] = []
    position = 0
    for match in PATH_TOKEN.finditer(data):
        if re.sub(r"[\s,]+", "", data[position : match.start()]):
            raise GeometryError("Unsupported or malformed SVG path data.")
        tokens.append(match.group())
        position = match.end()
    if re.sub(r"[\s,]+", "", data[position:]):
        raise GeometryError("Unsupported or malformed SVG path data.")
    return tokens


def is_command(token: str) -> bool:
    return len(token) == 1 and token.isalpha()


def relative_point(current: Point, x: float, y: float, relative: bool) -> Point:
    return (current[0] + x, current[1] + y) if relative else (x, y)


def include_line(bounds: Bounds, matrix: Matrix, start: Point, end: Point) -> None:
    bounds.include(transform_point(matrix, start))
    bounds.include(transform_point(matrix, end))


def quadratic_value(p0: float, p1: float, p2: float, t: float) -> float:
    one_minus_t = 1 - t
    return (
        one_minus_t * one_minus_t * p0
        + 2 * one_minus_t * t * p1
        + t * t * p2
    )


def cubic_value(p0: float, p1: float, p2: float, p3: float, t: float) -> float:
    one_minus_t = 1 - t
    return (
        one_minus_t**3 * p0
        + 3 * one_minus_t * one_minus_t * t * p1
        + 3 * one_minus_t * t * t * p2
        + t**3 * p3
    )


def include_quadratic(
    bounds: Bounds,
    matrix: Matrix,
    start: Point,
    control: Point,
    end: Point,
) -> None:
    p0, p1, p2 = (
        transform_point(matrix, point) for point in (start, control, end)
    )
    candidates = {0.0, 1.0}
    for axis in range(2):
        denominator = p0[axis] - 2 * p1[axis] + p2[axis]
        if abs(denominator) <= 1e-12:
            continue
        t = (p0[axis] - p1[axis]) / denominator
        if 0 < t < 1:
            candidates.add(t)
    for t in candidates:
        bounds.include(
            (
                quadratic_value(p0[0], p1[0], p2[0], t),
                quadratic_value(p0[1], p1[1], p2[1], t),
            )
        )


def quadratic_roots(a: float, b: float, c: float) -> list[float]:
    if abs(a) <= 1e-12:
        return [] if abs(b) <= 1e-12 else [-c / b]
    discriminant = b * b - 4 * a * c
    if discriminant < 0:
        return []
    root = math.sqrt(max(0.0, discriminant))
    return [(-b - root) / (2 * a), (-b + root) / (2 * a)]


def include_cubic(
    bounds: Bounds,
    matrix: Matrix,
    start: Point,
    control1: Point,
    control2: Point,
    end: Point,
) -> None:
    p0, p1, p2, p3 = (
        transform_point(matrix, point)
        for point in (start, control1, control2, end)
    )
    candidates = {0.0, 1.0}
    for axis in range(2):
        a = -p0[axis] + 3 * p1[axis] - 3 * p2[axis] + p3[axis]
        b = 2 * (p0[axis] - 2 * p1[axis] + p2[axis])
        c = p1[axis] - p0[axis]
        candidates.update(t for t in quadratic_roots(a, b, c) if 0 < t < 1)
    for t in candidates:
        bounds.include(
            (
                cubic_value(p0[0], p1[0], p2[0], p3[0], t),
                cubic_value(p0[1], p1[1], p2[1], p3[1], t),
            )
        )


def vector_angle(first: Point, second: Point) -> float:
    cross = first[0] * second[1] - first[1] * second[0]
    dot = first[0] * second[0] + first[1] * second[1]
    return math.atan2(cross, dot)


def angle_on_arc(angle: float, start: float, delta: float) -> bool:
    full_turn = 2 * math.pi
    if abs(delta) >= full_turn - 1e-10:
        return True
    if delta >= 0:
        return (angle - start) % full_turn <= delta + 1e-10
    return (start - angle) % full_turn <= -delta + 1e-10


def include_ellipse_arc(
    bounds: Bounds,
    matrix: Matrix,
    center: Point,
    rx: float,
    ry: float,
    rotation: float,
    start_angle: float,
    delta_angle: float,
) -> None:
    cos_rotation = math.cos(rotation)
    sin_rotation = math.sin(rotation)
    x_cos = rx * cos_rotation
    x_sin = -ry * sin_rotation
    y_cos = rx * sin_rotation
    y_sin = ry * cos_rotation
    a, b, c, d, _, _ = matrix
    transformed_x_cos = a * x_cos + c * y_cos
    transformed_x_sin = a * x_sin + c * y_sin
    transformed_y_cos = b * x_cos + d * y_cos
    transformed_y_sin = b * x_sin + d * y_sin

    candidates = {
        start_angle,
        start_angle + delta_angle,
        math.atan2(transformed_x_sin, transformed_x_cos),
        math.atan2(transformed_x_sin, transformed_x_cos) + math.pi,
        math.atan2(transformed_y_sin, transformed_y_cos),
        math.atan2(transformed_y_sin, transformed_y_cos) + math.pi,
    }
    for angle in candidates:
        if not angle_on_arc(angle, start_angle, delta_angle):
            continue
        local_point = (
            center[0] + x_cos * math.cos(angle) + x_sin * math.sin(angle),
            center[1] + y_cos * math.cos(angle) + y_sin * math.sin(angle),
        )
        bounds.include(transform_point(matrix, local_point))


def include_arc(
    bounds: Bounds,
    matrix: Matrix,
    start: Point,
    rx: float,
    ry: float,
    x_axis_rotation: float,
    large_arc: bool,
    sweep: bool,
    end: Point,
) -> None:
    rx = abs(rx)
    ry = abs(ry)
    if rx == 0 or ry == 0:
        include_line(bounds, matrix, start, end)
        return
    if start == end:
        return

    rotation = math.radians(x_axis_rotation % 360)
    cos_rotation = math.cos(rotation)
    sin_rotation = math.sin(rotation)
    dx = (start[0] - end[0]) / 2
    dy = (start[1] - end[1]) / 2
    transformed_x = cos_rotation * dx + sin_rotation * dy
    transformed_y = -sin_rotation * dx + cos_rotation * dy

    scale = transformed_x**2 / rx**2 + transformed_y**2 / ry**2
    if scale > 1:
        factor = math.sqrt(scale)
        rx *= factor
        ry *= factor

    numerator = (
        rx**2 * ry**2
        - rx**2 * transformed_y**2
        - ry**2 * transformed_x**2
    )
    denominator = (
        rx**2 * transformed_y**2 + ry**2 * transformed_x**2
    )
    coefficient = 0.0
    if denominator > 0:
        sign = -1 if large_arc == sweep else 1
        coefficient = sign * math.sqrt(max(0.0, numerator / denominator))

    center_x_prime = coefficient * rx * transformed_y / ry
    center_y_prime = coefficient * -ry * transformed_x / rx
    center = (
        cos_rotation * center_x_prime
        - sin_rotation * center_y_prime
        + (start[0] + end[0]) / 2,
        sin_rotation * center_x_prime
        + cos_rotation * center_y_prime
        + (start[1] + end[1]) / 2,
    )
    start_vector = (
        (transformed_x - center_x_prime) / rx,
        (transformed_y - center_y_prime) / ry,
    )
    end_vector = (
        (-transformed_x - center_x_prime) / rx,
        (-transformed_y - center_y_prime) / ry,
    )
    start_angle = vector_angle((1, 0), start_vector)
    delta_angle = vector_angle(start_vector, end_vector)
    if not sweep and delta_angle > 0:
        delta_angle -= 2 * math.pi
    elif sweep and delta_angle < 0:
        delta_angle += 2 * math.pi

    include_ellipse_arc(
        bounds,
        matrix,
        center,
        rx,
        ry,
        rotation,
        start_angle,
        delta_angle,
    )


def include_path(bounds: Bounds, matrix: Matrix, data: str) -> None:
    tokens = tokenize_path(data)
    index = 0
    command: str | None = None
    current = (0.0, 0.0)
    subpath_start = current
    previous_command: str | None = None
    previous_cubic_control: Point | None = None
    previous_quadratic_control: Point | None = None

    while index < len(tokens):
        if is_command(tokens[index]):
            command = tokens[index]
            index += 1
            if command.upper() == "Z":
                include_line(bounds, matrix, current, subpath_start)
                current = subpath_start
                previous_command = "Z"
                previous_cubic_control = None
                previous_quadratic_control = None
                command = None
                continue
            if index >= len(tokens) or is_command(tokens[index]):
                raise GeometryError("SVG path command has no coordinates.")
        elif command is None:
            raise GeometryError("SVG path data must begin with a command.")

        upper = command.upper()
        arity = PATH_ARITY.get(upper)
        if arity is None or index + arity > len(tokens):
            raise GeometryError(f"Unsupported or incomplete SVG path command {command}.")
        group = tokens[index : index + arity]
        if any(is_command(token) for token in group):
            raise GeometryError(f"Incomplete SVG path command {command}.")
        values = [float(token) for token in group]
        index += arity
        relative = command.islower()

        if upper == "M":
            current = relative_point(current, values[0], values[1], relative)
            subpath_start = current
            previous_cubic_control = None
            previous_quadratic_control = None
            previous_command = "M"
            command = "l" if relative else "L"
            continue

        if upper == "L":
            end = relative_point(current, values[0], values[1], relative)
            include_line(bounds, matrix, current, end)
            current = end
        elif upper == "H":
            end = (
                current[0] + values[0] if relative else values[0],
                current[1],
            )
            include_line(bounds, matrix, current, end)
            current = end
        elif upper == "V":
            end = (
                current[0],
                current[1] + values[0] if relative else values[0],
            )
            include_line(bounds, matrix, current, end)
            current = end
        elif upper == "C":
            control1 = relative_point(current, values[0], values[1], relative)
            control2 = relative_point(current, values[2], values[3], relative)
            end = relative_point(current, values[4], values[5], relative)
            include_cubic(bounds, matrix, current, control1, control2, end)
            current = end
            previous_cubic_control = control2
        elif upper == "S":
            control1 = (
                (
                    2 * current[0] - previous_cubic_control[0],
                    2 * current[1] - previous_cubic_control[1],
                )
                if previous_command in {"C", "S"} and previous_cubic_control
                else current
            )
            control2 = relative_point(current, values[0], values[1], relative)
            end = relative_point(current, values[2], values[3], relative)
            include_cubic(bounds, matrix, current, control1, control2, end)
            current = end
            previous_cubic_control = control2
        elif upper == "Q":
            control = relative_point(current, values[0], values[1], relative)
            end = relative_point(current, values[2], values[3], relative)
            include_quadratic(bounds, matrix, current, control, end)
            current = end
            previous_quadratic_control = control
        elif upper == "T":
            control = (
                (
                    2 * current[0] - previous_quadratic_control[0],
                    2 * current[1] - previous_quadratic_control[1],
                )
                if previous_command in {"Q", "T"} and previous_quadratic_control
                else current
            )
            end = relative_point(current, values[0], values[1], relative)
            include_quadratic(bounds, matrix, current, control, end)
            current = end
            previous_quadratic_control = control
        elif upper == "A":
            if values[3] not in {0.0, 1.0} or values[4] not in {0.0, 1.0}:
                raise GeometryError("SVG arc flags must be 0 or 1.")
            end = relative_point(current, values[5], values[6], relative)
            include_arc(
                bounds,
                matrix,
                current,
                values[0],
                values[1],
                values[2],
                bool(values[3]),
                bool(values[4]),
                end,
            )
            current = end

        if upper not in {"C", "S"}:
            previous_cubic_control = None
        if upper not in {"Q", "T"}:
            previous_quadratic_control = None
        previous_command = upper


def attribute_number(
    element: ET.Element,
    name: str,
    default: float | None = None,
) -> float:
    raw = element.get(name)
    if raw is None:
        if default is None:
            raise GeometryError(f"<{local_name(element.tag)}> is missing {name}.")
        return default
    try:
        return float(raw)
    except ValueError as error:
        raise GeometryError(
            f'<{local_name(element.tag)}> has non-numeric {name}="{raw}".'
        ) from error


def include_element(bounds: Bounds, element: ET.Element, matrix: Matrix) -> None:
    tag = local_name(element.tag)
    if tag == "path":
        data = (element.get("d") or "").strip()
        if data:
            include_path(bounds, matrix, data)
    elif tag == "circle":
        center = (
            attribute_number(element, "cx", 0),
            attribute_number(element, "cy", 0),
        )
        radius = attribute_number(element, "r")
        include_ellipse_arc(
            bounds, matrix, center, radius, radius, 0, 0, 2 * math.pi
        )
    elif tag == "ellipse":
        center = (
            attribute_number(element, "cx", 0),
            attribute_number(element, "cy", 0),
        )
        include_ellipse_arc(
            bounds,
            matrix,
            center,
            attribute_number(element, "rx"),
            attribute_number(element, "ry"),
            0,
            0,
            2 * math.pi,
        )
    elif tag == "rect":
        x = attribute_number(element, "x", 0)
        y = attribute_number(element, "y", 0)
        width = attribute_number(element, "width")
        height = attribute_number(element, "height")
        for point in (
            (x, y),
            (x + width, y),
            (x + width, y + height),
            (x, y + height),
        ):
            bounds.include(transform_point(matrix, point))
    elif tag == "line":
        include_line(
            bounds,
            matrix,
            (attribute_number(element, "x1", 0), attribute_number(element, "y1", 0)),
            (attribute_number(element, "x2", 0), attribute_number(element, "y2", 0)),
        )
    elif tag in {"polygon", "polyline"}:
        values = parse_numbers(element.get("points") or "")
        if len(values) % 2:
            raise GeometryError(f"<{tag}> points must contain x/y pairs.")
        for index in range(0, len(values), 2):
            bounds.include(transform_point(matrix, (values[index], values[index + 1])))


def measure_svg_bounds(path: Path) -> Bounds:
    try:
        root = ET.parse(path).getroot()
    except (ET.ParseError, OSError) as error:
        raise GeometryError(f"Cannot parse SVG geometry: {error}") from error

    bounds = Bounds()

    def walk(
        element: ET.Element,
        parent_matrix: Matrix,
        inherited_fill: str,
        inherited_opacity: float,
    ) -> None:
        tag = local_name(element.tag)
        if tag in SKIP_CONTAINERS:
            return

        style = parse_style(element.get("style"))
        if style.get("display", element.get("display", "")) == "none":
            return
        if style.get("visibility", element.get("visibility", "")) == "hidden":
            return

        fill = style.get("fill", element.get("fill", inherited_fill)).strip().lower()
        try:
            opacity = inherited_opacity * float(
                style.get("opacity", element.get("opacity", "1"))
            )
            fill_opacity = float(
                style.get("fill-opacity", element.get("fill-opacity", "1"))
            )
        except ValueError as error:
            raise GeometryError("Opacity values must be numeric.") from error

        matrix = compose(parent_matrix, parse_transform(element.get("transform")))
        if tag in {"circle", "ellipse", "line", "path", "polygon", "polyline", "rect"}:
            if fill not in {"", "none"} and opacity > 0 and fill_opacity > 0:
                include_element(bounds, element, matrix)

        for child in element:
            walk(child, matrix, fill, opacity)

    walk(root, IDENTITY, "black", 1.0)
    if bounds.is_empty:
        raise GeometryError("SVG has no measurable visible fill geometry.")
    return bounds
