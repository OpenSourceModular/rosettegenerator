import math
import os

from flask import jsonify, request

import octoprint.plugin

from .holtz_patterns import HOLTZ_FUNCTIONS

try:
    from shapely.geometry import GeometryCollection, MultiPolygon, Polygon
    from shapely.ops import unary_union
except ImportError:
    GeometryCollection = None
    MultiPolygon = None
    Polygon = None
    unary_union = None


ROSETTE_TYPES = [
    "Bump",
    "Dip",
    "Arch",
    "Concave+Convex",
    "Puffy",
    "W",
    "X + 1",
    "Flat",
    "Lotus",
    "A",
    "Sine",
    "Sine Skip",
    "Bead",
]

HOLTZ_TYPES = ["Holtz - {0}".format(letter) for letter in "ABCDEFGHIJKLMNOPQRS"]
HOLTZ_DEFAULT_N2 = 5
HOLTZ_DEFAULT_A2 = 0.2

TAU = 2.0 * math.pi


def _as_bool(value):
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in ("1", "true", "yes", "on"):
            return True
        if normalized in ("0", "false", "no", "off"):
            return False
    if isinstance(value, (int, float)):
        return bool(value)
    return False


def _linspace(start, end, count):
    if count <= 1:
        return [start]
    step = (end - start) / float(count - 1)
    return [start + (idx * step) for idx in range(count)]


def _normalize_angle(angle):
    return angle % TAU


def _is_between_ccw(start, target, end):
    span = (_normalize_angle(end) - _normalize_angle(start)) % TAU
    reach = (_normalize_angle(target) - _normalize_angle(start)) % TAU
    return reach <= span + 1e-12


def _distance(p0, p1):
    return math.hypot(p0[0] - p1[0], p0[1] - p1[1])


def _rotate_point(point, angle_rad):
    cos_a = math.cos(angle_rad)
    sin_a = math.sin(angle_rad)
    x, y = point
    return (x * cos_a - y * sin_a, x * sin_a + y * cos_a)


def _rotate_segments(segments, angle_rad):
    if abs(angle_rad) <= 1e-12:
        return segments

    rotated = []
    for segment in segments:
        if segment[0] == "arc":
            _, p0, p1, p2 = segment
            rotated.append(
                (
                    "arc",
                    _rotate_point(p0, angle_rad),
                    _rotate_point(p1, angle_rad),
                    _rotate_point(p2, angle_rad),
                )
            )
        else:
            _, p0, p1 = segment
            rotated.append(("line", _rotate_point(p0, angle_rad), _rotate_point(p1, angle_rad)))
    return rotated


def arc_through_three_points(p0, p1, p2, samples=80):
    x1, y1 = p0
    x2, y2 = p1
    x3, y3 = p2

    det = 2.0 * (x1 * (y2 - y3) + x2 * (y3 - y1) + x3 * (y1 - y2))
    if abs(det) < 1e-12:
        raise ValueError("Arc points are collinear. Increase rosette height or reduce count.")

    x1_sq_y1_sq = x1 * x1 + y1 * y1
    x2_sq_y2_sq = x2 * x2 + y2 * y2
    x3_sq_y3_sq = x3 * x3 + y3 * y3

    cx = (
        x1_sq_y1_sq * (y2 - y3)
        + x2_sq_y2_sq * (y3 - y1)
        + x3_sq_y3_sq * (y1 - y2)
    ) / det
    cy = (
        x1_sq_y1_sq * (x3 - x2)
        + x2_sq_y2_sq * (x1 - x3)
        + x3_sq_y3_sq * (x2 - x1)
    ) / det

    radius = math.hypot(x1 - cx, y1 - cy)

    a0 = math.atan2(y1 - cy, x1 - cx)
    am = math.atan2(y2 - cy, x2 - cx)
    a2 = math.atan2(y3 - cy, x3 - cx)

    if _is_between_ccw(a0, am, a2):
        span = (_normalize_angle(a2) - _normalize_angle(a0)) % TAU
        angles = _linspace(a0, a0 + span, samples)
    else:
        span = (_normalize_angle(a0) - _normalize_angle(a2)) % TAU
        angles = _linspace(a0, a0 - span, samples)

    x = [cx + radius * math.cos(angle) for angle in angles]
    y = [cy + radius * math.sin(angle) for angle in angles]
    return x, y


def generate_bump_arcs(radius, count, height):
    ref_radius = radius - height
    if ref_radius <= 0:
        raise ValueError("Height of bumps must be smaller than radius")

    arcs = []
    angle_step = TAU / float(count)
    half_span = angle_step / 2.0

    for idx in range(count):
        center = idx * angle_step
        start = center - half_span
        end = center + half_span
        p_start = (ref_radius * math.cos(start), ref_radius * math.sin(start))
        p_peak = (radius * math.cos(center), radius * math.sin(center))
        p_end = (ref_radius * math.cos(end), ref_radius * math.sin(end))
        arcs.append((p_start, p_peak, p_end))

    return arcs, ref_radius


def generate_dip_arcs(radius, count, height):
    inner_radius = radius - height
    if inner_radius <= 0:
        raise ValueError("Height of dips must be smaller than radius")

    arcs = []
    angle_step = TAU / float(count)
    half_span = angle_step / 2.0

    for idx in range(count):
        center = idx * angle_step
        start = center - half_span
        end = center + half_span
        p_start = (radius * math.cos(start), radius * math.sin(start))
        p_dip = (inner_radius * math.cos(center), inner_radius * math.sin(center))
        p_end = (radius * math.cos(end), radius * math.sin(end))
        arcs.append((p_start, p_dip, p_end))

    return arcs, inner_radius


def _line_to_inner_at_45(outer_point, outer_angle, inner_radius, toward_ccw):
    radial = (math.cos(outer_angle), math.sin(outer_angle))
    tangent = (-math.sin(outer_angle), math.cos(outer_angle))
    tangent_sign = 1.0 if toward_ccw else -1.0
    root_two = math.sqrt(2.0)

    direction = (
        (tangent_sign * tangent[0] - radial[0]) / root_two,
        (tangent_sign * tangent[1] - radial[1]) / root_two,
    )

    x0, y0 = outer_point
    dx, dy = direction

    b = 2.0 * (x0 * dx + y0 * dy)
    c = (x0 * x0 + y0 * y0) - (inner_radius * inner_radius)
    disc = (b * b) - (4.0 * c)
    if disc <= 0.0:
        raise ValueError("Height of arches is too large for this radius")

    sqrt_disc = math.sqrt(disc)
    lam_1 = (-b - sqrt_disc) / 2.0
    lam_2 = (-b + sqrt_disc) / 2.0
    positive_solutions = [value for value in (lam_1, lam_2) if value > 1e-12]
    if not positive_solutions:
        raise ValueError("Could not construct 45-degree arch side line")

    lam = min(positive_solutions)
    return (x0 + lam * dx, y0 + lam * dy)


def generate_arch_segments(radius, count, height):
    inner_radius = radius - height
    if inner_radius <= 0:
        raise ValueError("Height of arches must be smaller than radius")

    segments = []
    angle_step = TAU / float(count)
    half_span = angle_step / 2.0

    for idx in range(count):
        center = idx * angle_step
        start = center - half_span
        end = center + half_span

        p_outer_start = (radius * math.cos(start), radius * math.sin(start))
        p_outer_peak = (radius * math.cos(center), radius * math.sin(center))
        p_outer_end = (radius * math.cos(end), radius * math.sin(end))

        p_inner_start = _line_to_inner_at_45(p_outer_start, start, inner_radius, toward_ccw=True)
        p_inner_end = _line_to_inner_at_45(p_outer_end, end, inner_radius, toward_ccw=False)

        segments.append(("line", p_outer_start, p_inner_start))
        segments.append(("arc", p_inner_start, p_outer_peak, p_inner_end))
        segments.append(("line", p_inner_end, p_outer_end))

    return segments, inner_radius


def generate_concave_convex_arcs(radius, count, height, split_pct=0.5):
    r_mid = radius - height / 2.0
    r_inner = radius - height
    if r_inner <= 0:
        raise ValueError("Height must be smaller than radius")
    if not (0.0 < split_pct < 1.0):
        raise ValueError("Split % must be between 0 and 100")

    segments = []
    angle_step = TAU / float(count)
    half_span = angle_step / 2.0
    convex_span = (1.0 - split_pct) * angle_step
    concave_span = split_pct * angle_step

    for idx in range(count):
        center = idx * angle_step
        start = center - half_span
        split_angle = start + convex_span

        p_bump_start = (r_mid * math.cos(start), r_mid * math.sin(start))
        p_bump_peak = (
            radius * math.cos(start + convex_span / 2.0),
            radius * math.sin(start + convex_span / 2.0),
        )
        p_bump_end = (r_mid * math.cos(split_angle), r_mid * math.sin(split_angle))

        p_dip_start = p_bump_end
        p_dip_valley = (
            r_inner * math.cos(split_angle + concave_span / 2.0),
            r_inner * math.sin(split_angle + concave_span / 2.0),
        )
        p_dip_end = (r_mid * math.cos(start + angle_step), r_mid * math.sin(start + angle_step))

        segments.append(("arc", p_bump_start, p_bump_peak, p_bump_end))
        segments.append(("arc", p_dip_start, p_dip_valley, p_dip_end))

    return segments, r_mid


def generate_puffy_segments(radius, count, offset):
    if offset < 0:
        raise ValueError("Offset must be greater than or equal to 0")

    segments = []
    angle_step = TAU / float(count)
    half_span = angle_step / 2.0

    for idx in range(count):
        center_angle = idx * angle_step
        start_angle = center_angle - half_span
        end_angle = center_angle + half_span

        p_start = (radius * math.cos(start_angle), radius * math.sin(start_angle))
        p_end = (radius * math.cos(end_angle), radius * math.sin(end_angle))

        arc_center = (
            offset * math.cos(center_angle + math.pi),
            offset * math.sin(center_angle + math.pi),
        )
        arc_radius = _distance(arc_center, p_start)
        p_mid = (
            arc_center[0] + arc_radius * math.cos(center_angle),
            arc_center[1] + arc_radius * math.sin(center_angle),
        )

        segments.append(("arc", p_start, p_mid, p_end))

    return segments, radius


def generate_w_segments(radius, count, height):
    inner_radius = radius - height
    if inner_radius <= 0:
        raise ValueError("Height must be smaller than radius")

    segments = []
    angle_step = TAU / float(count)
    half_span = angle_step / 2.0

    for idx in range(count):
        center_angle = idx * angle_step
        start_angle = center_angle - half_span
        end_angle = center_angle + half_span

        p_start = (radius * math.cos(start_angle), radius * math.sin(start_angle))
        p_mid = (inner_radius * math.cos(center_angle), inner_radius * math.sin(center_angle))
        p_end = (radius * math.cos(end_angle), radius * math.sin(end_angle))

        segments.append(("line", p_start, p_mid))
        segments.append(("line", p_mid, p_end))

    return segments, inner_radius


def generate_x_plus_one_segments(radius, count, height, x_count):
    inner_radius = radius - height
    if inner_radius <= 0:
        raise ValueError("Height must be smaller than radius")
    if x_count < 1:
        raise ValueError("X must be at least 1")

    segments = []
    angle_step = TAU / float(count)
    half_span = angle_step / 2.0

    for idx in range(count):
        segment_start = idx * angle_step
        midpoint = segment_start + half_span

        first_peak_angle = segment_start + (half_span / 2.0)
        p_first_start = (inner_radius * math.cos(segment_start), inner_radius * math.sin(segment_start))
        p_first_peak = (radius * math.cos(first_peak_angle), radius * math.sin(first_peak_angle))
        p_first_end = (inner_radius * math.cos(midpoint), inner_radius * math.sin(midpoint))
        segments.append(("arc", p_first_start, p_first_peak, p_first_end))

        sub_span = half_span / float(x_count)
        for jdx in range(x_count):
            sub_start_angle = midpoint + (jdx * sub_span)
            sub_end_angle = sub_start_angle + sub_span
            sub_peak_angle = sub_start_angle + (sub_span / 2.0)

            p_sub_start = (inner_radius * math.cos(sub_start_angle), inner_radius * math.sin(sub_start_angle))
            p_sub_peak = (radius * math.cos(sub_peak_angle), radius * math.sin(sub_peak_angle))
            p_sub_end = (inner_radius * math.cos(sub_end_angle), inner_radius * math.sin(sub_end_angle))
            segments.append(("arc", p_sub_start, p_sub_peak, p_sub_end))

    return segments, inner_radius


def generate_flat_segments(radius, count):
    segments = []
    angle_step = TAU / float(count)

    for idx in range(count):
        start_angle = idx * angle_step
        end_angle = ((idx + 1) % count) * angle_step
        p_start = (radius * math.cos(start_angle), radius * math.sin(start_angle))
        p_end = (radius * math.cos(end_angle), radius * math.sin(end_angle))
        segments.append(("line", p_start, p_end))

    return segments, radius


def generate_lotus_segments(radius, count, height):
    inner_radius = radius - height
    if inner_radius <= 0:
        raise ValueError("Height must be smaller than radius")

    saddle_radius = radius - (0.35 * height)
    segments = []
    angle_step = TAU / float(count)
    half_span = angle_step / 2.0
    quarter_span = angle_step / 4.0

    for idx in range(count):
        center_angle = idx * angle_step
        start_angle = center_angle - half_span
        end_angle = center_angle + half_span

        p_start = (inner_radius * math.cos(start_angle), inner_radius * math.sin(start_angle))
        p_saddle = (saddle_radius * math.cos(center_angle), saddle_radius * math.sin(center_angle))
        p_end = (inner_radius * math.cos(end_angle), inner_radius * math.sin(end_angle))

        p_left_peak = (
            radius * math.cos(center_angle - quarter_span),
            radius * math.sin(center_angle - quarter_span),
        )
        p_right_peak = (
            radius * math.cos(center_angle + quarter_span),
            radius * math.sin(center_angle + quarter_span),
        )

        segments.append(("arc", p_start, p_left_peak, p_saddle))
        segments.append(("arc", p_saddle, p_right_peak, p_end))

    return segments, saddle_radius


def generate_a_segments(radius, count, height):
    inner_radius = radius - height
    if inner_radius <= 0:
        raise ValueError("Height must be smaller than radius")

    transition_radius = radius - (0.35 * height)
    segments = []
    angle_step = TAU / float(count)
    third_span = angle_step / 3.0

    for idx in range(count):
        start_angle = idx * angle_step
        first_split_angle = start_angle + third_span
        second_split_angle = start_angle + (2.0 * third_span)
        end_angle = start_angle + angle_step

        p_start = (radius * math.cos(start_angle), radius * math.sin(start_angle))
        p_first_split = (inner_radius * math.cos(first_split_angle), inner_radius * math.sin(first_split_angle))
        p_second_split = (
            inner_radius * math.cos(second_split_angle),
            inner_radius * math.sin(second_split_angle),
        )
        p_end = (radius * math.cos(end_angle), radius * math.sin(end_angle))

        p_first_ctrl = (
            transition_radius * math.cos(start_angle + (third_span / 2.0)),
            transition_radius * math.sin(start_angle + (third_span / 2.0)),
        )
        p_center_peak = (
            radius * math.cos(start_angle + (angle_step / 2.0)),
            radius * math.sin(start_angle + (angle_step / 2.0)),
        )
        p_last_ctrl = (
            transition_radius * math.cos(second_split_angle + (third_span / 2.0)),
            transition_radius * math.sin(second_split_angle + (third_span / 2.0)),
        )

        segments.append(("arc", p_start, p_first_ctrl, p_first_split))
        segments.append(("arc", p_first_split, p_center_peak, p_second_split))
        segments.append(("arc", p_second_split, p_last_ctrl, p_end))

    return segments, inner_radius


def generate_sine_segments(radius, count, amplitude, samples_per_period=120):
    inner_radius = radius - amplitude
    if amplitude <= 0:
        raise ValueError("Amplitude must be greater than 0")
    if inner_radius <= 0:
        raise ValueError("Amplitude must be smaller than radius")

    total_samples = max(count * samples_per_period, 2)
    theta_values = _linspace(0.0, TAU, total_samples + 1)
    radial_values = [
        (radius - (amplitude / 2.0)) + ((amplitude / 2.0) * math.sin((count * theta) + (math.pi / 2.0)))
        for theta in theta_values
    ]

    segments = []
    points = [
        (radial * math.cos(theta), radial * math.sin(theta))
        for theta, radial in zip(theta_values, radial_values)
    ]

    for start_point, end_point in zip(points, points[1:]):
        segments.append(("line", start_point, end_point))

    return segments, radius - (amplitude / 2.0)


def generate_sine_skip_segments(radius, count, amplitude, skip, samples_per_segment=120):
    inner_radius = radius - amplitude
    if amplitude <= 0:
        raise ValueError("Amplitude must be greater than 0")
    if inner_radius <= 0:
        raise ValueError("Amplitude must be smaller than radius")
    if skip < 2:
        raise ValueError("Skip must be at least 2")

    angle_step = TAU / float(count)
    total_samples = max(samples_per_segment, 8)
    segments = []

    for segment_index in range(count):
        segment_start = segment_index * angle_step
        draw_segment = (segment_index % skip) != (skip - 1)

        theta_values = _linspace(segment_start, segment_start + angle_step, total_samples + 1)

        if draw_segment:
            radial_values = [
                inner_radius + (amplitude * (0.5 + (0.5 * math.sin((local * TAU) + (math.pi / 2.0)))))
                for local in _linspace(0.0, 1.0, total_samples + 1)
            ]
        else:
            radial_values = [radius] * (total_samples + 1)

        points = [
            (radial * math.cos(theta), radial * math.sin(theta))
            for theta, radial in zip(theta_values, radial_values)
        ]

        for start_point, end_point in zip(points, points[1:]):
            segments.append(("line", start_point, end_point))

    return segments, inner_radius


def generate_bead_segments(radius, count, amplitude, flat_length):
    if amplitude <= 0:
        raise ValueError("Amplitude must be greater than 0")
    if flat_length < 0:
        raise ValueError("Flat length must be greater than or equal to 0")

    construction_radius = radius - (amplitude / 2.0)
    inner_radius = radius - amplitude
    if construction_radius <= 0 or inner_radius <= 0:
        raise ValueError("Amplitude must be smaller than radius")

    angle_step = TAU / float(count)
    flat_angle = flat_length / construction_radius
    if (2.0 * flat_angle) >= angle_step:
        raise ValueError("Flat length is too large for selected radius and segment count")

    bulge_span = (angle_step - (2.0 * flat_angle)) / 2.0
    if bulge_span <= 1e-6:
        raise ValueError("Flat length leaves no room for bead bulges")

    segments = []
    for idx in range(count):
        segment_start = idx * angle_step
        first_arc_end = segment_start + bulge_span
        first_flat_end = first_arc_end + flat_angle
        second_arc_end = first_flat_end + bulge_span
        segment_end = segment_start + angle_step

        p_first_start = (
            construction_radius * math.cos(segment_start),
            construction_radius * math.sin(segment_start),
        )
        p_first_peak = (
            radius * math.cos(segment_start + (bulge_span / 2.0)),
            radius * math.sin(segment_start + (bulge_span / 2.0)),
        )
        p_first_end = (
            construction_radius * math.cos(first_arc_end),
            construction_radius * math.sin(first_arc_end),
        )
        segments.append(("arc", p_first_start, p_first_peak, p_first_end))

        if flat_angle > 1e-6:
            p_first_flat_mid = (
                construction_radius * math.cos(first_arc_end + (flat_angle / 2.0)),
                construction_radius * math.sin(first_arc_end + (flat_angle / 2.0)),
            )
            p_first_flat_end = (
                construction_radius * math.cos(first_flat_end),
                construction_radius * math.sin(first_flat_end),
            )
            segments.append(("arc", p_first_end, p_first_flat_mid, p_first_flat_end))
        else:
            p_first_flat_end = p_first_end

        p_second_valley = (
            inner_radius * math.cos(first_flat_end + (bulge_span / 2.0)),
            inner_radius * math.sin(first_flat_end + (bulge_span / 2.0)),
        )
        p_second_arc_end = (
            construction_radius * math.cos(second_arc_end),
            construction_radius * math.sin(second_arc_end),
        )
        segments.append(("arc", p_first_flat_end, p_second_valley, p_second_arc_end))

        if flat_angle > 1e-6:
            p_second_flat_mid = (
                construction_radius * math.cos(second_arc_end + (flat_angle / 2.0)),
                construction_radius * math.sin(second_arc_end + (flat_angle / 2.0)),
            )
            p_second_flat_end = (
                construction_radius * math.cos(segment_end),
                construction_radius * math.sin(segment_end),
            )
            segments.append(("arc", p_second_arc_end, p_second_flat_mid, p_second_flat_end))

    return segments, construction_radius


def get_rosette_geometry(kind, radius, count, height, extra=None, phase=0.0):
    if radius <= 0:
        raise ValueError("Radius must be greater than 0")
    if count < 1:
        raise ValueError("Count must be at least 1")
    if phase < 0.0 or phase > 180.0:
        raise ValueError("Phase must be between 0 and 180 degrees")

    if kind == "Bump":
        if height <= 0:
            raise ValueError("Height must be greater than 0")
        arc_triplets, reference_radius = generate_bump_arcs(radius, count, height)
        segments = [("arc", p0, p1, p2) for (p0, p1, p2) in arc_triplets]
    elif kind == "Dip":
        if height <= 0:
            raise ValueError("Height must be greater than 0")
        arc_triplets, reference_radius = generate_dip_arcs(radius, count, height)
        segments = [("arc", p0, p1, p2) for (p0, p1, p2) in arc_triplets]
    elif kind == "Arch":
        if height <= 0:
            raise ValueError("Height must be greater than 0")
        segments, reference_radius = generate_arch_segments(radius, count, height)
    elif kind == "Concave+Convex":
        if height <= 0:
            raise ValueError("Height must be greater than 0")
        split_pct = extra if extra is not None else 0.5
        segments, reference_radius = generate_concave_convex_arcs(radius, count, height, split_pct)
    elif kind == "Puffy":
        segments, reference_radius = generate_puffy_segments(radius, count, height)
    elif kind == "W":
        if height <= 0:
            raise ValueError("Height must be greater than 0")
        segments, reference_radius = generate_w_segments(radius, count, height)
    elif kind == "X + 1":
        if height <= 0:
            raise ValueError("Height must be greater than 0")
        if extra is None:
            raise ValueError("X value is required for X + 1 style")
        segments, reference_radius = generate_x_plus_one_segments(radius, count, height, int(extra))
    elif kind == "Flat":
        segments, reference_radius = generate_flat_segments(radius, count)
    elif kind == "Lotus":
        if height <= 0:
            raise ValueError("Height must be greater than 0")
        segments, reference_radius = generate_lotus_segments(radius, count, height)
    elif kind == "A":
        if height <= 0:
            raise ValueError("Height must be greater than 0")
        segments, reference_radius = generate_a_segments(radius, count, height)
    elif kind == "Sine":
        segments, reference_radius = generate_sine_segments(radius, count, height)
    elif kind == "Sine Skip":
        if extra is None:
            raise ValueError("Skip value is required for Sine Skip style")
        segments, reference_radius = generate_sine_skip_segments(radius, count, height, int(extra))
    elif kind == "Bead":
        if extra is None:
            raise ValueError("Flat length is required for Bead style")
        segments, reference_radius = generate_bead_segments(radius, count, height, extra)
    else:
        raise ValueError("Rosette style is not implemented")

    segments = _rotate_segments(segments, -math.radians(phase))
    return segments, reference_radius


def _evaluate_holtz_value(holtz_style, n, repeat, n2, a2):
    style_key = holtz_style.replace("Holtz - ", "Holtz")
    holtz_fn = HOLTZ_FUNCTIONS[style_key]

    if style_key in ("HoltzA", "HoltzB", "HoltzF", "HoltzG", "HoltzK", "HoltzP"):
        return holtz_fn(n)
    if style_key in ("HoltzC", "HoltzD", "HoltzL", "HoltzM", "HoltzN", "HoltzO", "HoltzR"):
        return holtz_fn(n, repeat)
    return holtz_fn(n, repeat, n2, a2)


def get_holtz_geometry(holtz_style, radius, count, height, phase=0.0, n2=HOLTZ_DEFAULT_N2, a2=HOLTZ_DEFAULT_A2):
    if holtz_style not in HOLTZ_TYPES:
        raise ValueError("Unknown Holtz style")
    if radius <= 0:
        raise ValueError("Radius must be greater than 0")
    if count < 1:
        raise ValueError("Count must be at least 1")
    if height < 0:
        raise ValueError("Height must be 0 or greater")
    if phase < 0.0 or phase > 180.0:
        raise ValueError("Phase must be between 0 and 180 degrees")

    n2 = max(3, int(n2))
    a2 = float(a2)

    sample_count = max(720, int(count) * 120)
    points = []
    min_radius = radius

    for idx in range(sample_count):
        normalized_angle = idx / float(sample_count)
        value = _evaluate_holtz_value(holtz_style, normalized_angle * count, count, n2, a2)
        current_radius = radius - (height * value)
        min_radius = min(min_radius, current_radius)
        angle = normalized_angle * TAU
        points.append((current_radius * math.cos(angle), current_radius * math.sin(angle)))

    segments = []
    for idx, point in enumerate(points):
        next_point = points[(idx + 1) % len(points)]
        segments.append(("line", point, next_point))

    segments = _rotate_segments(segments, -math.radians(phase))
    return segments, min_radius


def build_curve_path_data(segments):
    path_parts = []
    is_first_segment = True
    all_x = []
    all_y = []

    for segment in segments:
        if segment[0] == "arc":
            _, p0, p1, p2 = segment
            x_vals, y_vals = arc_through_three_points(p0, p1, p2)
        else:
            _, p0, p1 = segment
            x_vals = [p0[0], p1[0]]
            y_vals = [p0[1], p1[1]]

        if not x_vals:
            continue

        all_x.extend(x_vals)
        all_y.extend(y_vals)

        if is_first_segment:
            path_parts.append("M {0:.6f} {1:.6f}".format(x_vals[0], y_vals[0]))
            start_index = 1
            is_first_segment = False
        else:
            start_index = 0

        for px, py in zip(x_vals[start_index:], y_vals[start_index:]):
            path_parts.append("L {0:.6f} {1:.6f}".format(px, py))

    if path_parts:
        path_parts.append("Z")
    if not all_x or not all_y:
        raise ValueError("No curve data was generated")

    return " ".join(path_parts), (min(all_x), min(all_y), max(all_x), max(all_y))


def _append_polar_guides(svg_lines, bounds, angle_offset_deg=0.0, guide_opacity=0.7):
    min_x, min_y, max_x, max_y = bounds
    guide_opacity = max(0.0, min(1.0, float(guide_opacity)))
    svg_lines.append("  <g id=\"guides\" opacity=\"{0:.3f}\">".format(guide_opacity))
    max_extent = max(abs(min_x), abs(max_x), abs(min_y), abs(max_y)) * 1.5
    for angle_deg in range(0, 360, 45):
        angle_rad = math.radians(angle_deg + angle_offset_deg)
        x1 = max_extent * math.cos(angle_rad)
        y1 = max_extent * math.sin(angle_rad)
        x2 = -x1
        y2 = -y1
        svg_lines.append(
            "    <line x1=\"{0:.2f}\" y1=\"{1:.2f}\" x2=\"{2:.2f}\" y2=\"{3:.2f}\" stroke=\"#aaaaaa\" stroke-width=\"0.1\" stroke-dasharray=\"0.5,0.5\" />".format(
                x1, y1, x2, y2
            )
        )
        label_dist = max_extent * 0.85
        label_x = label_dist * math.cos(angle_rad)
        label_y = label_dist * math.sin(angle_rad)
        svg_lines.append(
            "    <text x=\"{0:.2f}\" y=\"{1:.2f}\" font-size=\"3\" font-family=\"Arial\" fill=\"#999999\" text-anchor=\"middle\" dominant-baseline=\"middle\">{2}°</text>".format(
                label_x, label_y, angle_deg
            )
        )
    svg_lines.append("  </g>")


def _mirror_segments_horizontally(segments):
    mirrored = []
    for segment in segments:
        if segment[0] == "arc":
            _, p0, p1, p2 = segment
            mirrored.append(("arc", (-p0[0], p0[1]), (-p1[0], p1[1]), (-p2[0], p2[1])))
        else:
            _, p0, p1 = segment
            mirrored.append(("line", (-p0[0], p0[1]), (-p1[0], p1[1])))
    return mirrored


def _mirror_points_horizontally(points):
    return [(-px, py) for px, py in points]


def build_svg_document(
    path_data,
    bounds,
    stroke="#000000",
    stroke_width=0.25,
    docname="RosetteGenerator.svg",
    include_guides=False,
    guide_angle_offset_deg=0.0,
    guide_opacity=0.7,
):
    if not path_data:
        raise ValueError("No curve data was generated")
    min_x, min_y, max_x, max_y = bounds
    margin = max(stroke_width * 2.0, 0.5)

    view_min_x = min_x - margin
    view_min_y = min_y - margin
    view_w = (max_x - min_x) + (2.0 * margin)
    view_h = (max_y - min_y) + (2.0 * margin)

    svg_lines = [
        "<?xml version=\"1.0\" encoding=\"UTF-8\" standalone=\"no\"?>",
        "<svg",
        "   version=\"1.1\"",
        "   viewBox=\"{0:.6f} {1:.6f} {2:.6f} {3:.6f}\"".format(
            view_min_x, view_min_y, view_w, view_h
        ),
        "   id=\"svg1\"",
        "   sodipodi:docname=\"{0}\"".format(docname),
        "   inkscape:version=\"1.4.2\"",
        "   xmlns:inkscape=\"http://www.inkscape.org/namespaces/inkscape\"",
        "   xmlns:sodipodi=\"http://sodipodi.sourceforge.net/DTD/sodipodi-0.dtd\"",
        "   xmlns=\"http://www.w3.org/2000/svg\"",
        "   xmlns:svg=\"http://www.w3.org/2000/svg\">",
        "  <defs id=\"defs1\" />",
        "  <sodipodi:namedview",
        "     id=\"namedview1\"",
        "     pagecolor=\"#ffffff\"",
        "     bordercolor=\"#000000\"",
        "     borderopacity=\"0.25\"",
        "     inkscape:showpageshadow=\"2\"",
        "     inkscape:pageopacity=\"0.0\"",
        "     inkscape:pagecheckerboard=\"0\"",
        "     inkscape:deskcolor=\"#d1d1d1\"",
        "     inkscape:current-layer=\"svg1\" />",
    ]

    if include_guides:
        _append_polar_guides(
            svg_lines,
            bounds,
            angle_offset_deg=guide_angle_offset_deg,
            guide_opacity=guide_opacity,
        )

    svg_lines.append(
        "  <path d=\"{0}\" fill=\"none\" stroke=\"{1}\" stroke-width=\"{2:.6f}\" stroke-linecap=\"round\" stroke-linejoin=\"round\" id=\"path1\" />".format(
            path_data, stroke, stroke_width
        )
    )
    svg_lines.append("</svg>")
    return "\n".join(svg_lines)


def build_svg_document_multi(
    path_entries,
    bounds,
    stroke_width=0.25,
    docname="RosetteGenerator.svg",
    include_guides=False,
    guide_angle_offset_deg=0.0,
    guide_opacity=0.7,
):
    if not path_entries:
        raise ValueError("No curve data was generated")

    min_x, min_y, max_x, max_y = bounds
    margin = max(stroke_width * 2.0, 0.5)
    view_min_x = min_x - margin
    view_min_y = min_y - margin
    view_w = (max_x - min_x) + (2.0 * margin)
    view_h = (max_y - min_y) + (2.0 * margin)

    svg_lines = [
        "<?xml version=\"1.0\" encoding=\"UTF-8\" standalone=\"no\"?>",
        "<svg",
        "   version=\"1.1\"",
        "   viewBox=\"{0:.6f} {1:.6f} {2:.6f} {3:.6f}\"".format(
            view_min_x, view_min_y, view_w, view_h
        ),
        "   id=\"svg1\"",
        "   sodipodi:docname=\"{0}\"".format(docname),
        "   inkscape:version=\"1.4.2\"",
        "   xmlns:inkscape=\"http://www.inkscape.org/namespaces/inkscape\"",
        "   xmlns:sodipodi=\"http://sodipodi.sourceforge.net/DTD/sodipodi-0.dtd\"",
        "   xmlns=\"http://www.w3.org/2000/svg\"",
        "   xmlns:svg=\"http://www.w3.org/2000/svg\">",
        "  <defs id=\"defs1\" />",
        "  <sodipodi:namedview",
        "     id=\"namedview1\"",
        "     pagecolor=\"#ffffff\"",
        "     bordercolor=\"#000000\"",
        "     borderopacity=\"0.25\"",
        "     inkscape:showpageshadow=\"2\"",
        "     inkscape:pageopacity=\"0.0\"",
        "     inkscape:pagecheckerboard=\"0\"",
        "     inkscape:deskcolor=\"#d1d1d1\"",
        "     inkscape:current-layer=\"svg1\" />",
    ]

    if include_guides:
        _append_polar_guides(
            svg_lines,
            bounds,
            angle_offset_deg=guide_angle_offset_deg,
            guide_opacity=guide_opacity,
        )

    path_id = 1
    for entry in path_entries:
        svg_lines.append(
            "  <path d=\"{0}\" fill=\"none\" stroke=\"{1}\" stroke-width=\"{2:.6f}\" stroke-linecap=\"round\" stroke-linejoin=\"round\" id=\"path{3}\" />".format(
                entry["path"], entry["stroke"], stroke_width, path_id
            )
        )
        path_id += 1

    svg_lines.append("</svg>")
    return "\n".join(svg_lines)


class RosetteGeneratorPlugin(
    octoprint.plugin.StartupPlugin,
    octoprint.plugin.TemplatePlugin,
    octoprint.plugin.AssetPlugin,
    octoprint.plugin.SettingsPlugin,
    octoprint.plugin.BlueprintPlugin,
):
    def on_after_startup(self):
        self._logger.info("RosetteGenerator plugin loaded")

    def get_settings_defaults(self):
        default_export_dir = os.path.join(self.get_plugin_data_folder(), "exports")
        return {
            "outer_radius": 50.0,
            "amplitude": 5.0,
            "num_segments": 12,
            "phase": 0.0,
            "split_percent": 50.0,
            "x_count": 3,
            "skip_count": 2,
            "flat_length": 8.0,
            "default_style": "Bump",
            "default_holtz_style": "",
            "default_holtz_n2": HOLTZ_DEFAULT_N2,
            "default_holtz_a2": HOLTZ_DEFAULT_A2,
            "show_guides": True,
            "auto_preview": True,
            "export_dir": default_export_dir,
        }

    def get_template_configs(self):
        return [
            {
                "type": "tab",
                "name": "Rosette Generator",
                "template": "rosettegenerator_tab.jinja2",
                "custom_bindings": True,
            }
        ]

    def get_assets(self):
        return {
            "js": ["js/rosettegenerator.js"],
            "css": ["css/rosettegenerator.css"],
        }

    def _parse_rosette_payload(self, payload):
        payload = payload or {}

        kind = str(payload.get("kind", self._settings.get(["default_style"]))).strip()
        holtz_style = str(payload.get("holtz_style", self._settings.get(["default_holtz_style"]) or "")).strip()
        if kind not in ROSETTE_TYPES:
            raise ValueError("Unknown rosette style")
        if holtz_style and holtz_style not in HOLTZ_TYPES:
            raise ValueError("Unknown Holtz style")

        radius = float(payload.get("radius", self._settings.get_float(["outer_radius"])))
        count = int(payload.get("count", self._settings.get_int(["num_segments"])))
        height = float(payload.get("height", self._settings.get_float(["amplitude"])))
        phase = float(payload.get("phase", self._settings.get_float(["phase"])))
        holtz_n2 = int(payload.get("holtz_n2", self._settings.get_int(["default_holtz_n2"])))
        holtz_a2 = float(payload.get("holtz_a2", self._settings.get_float(["default_holtz_a2"])))
        stored_show_guides = self._settings.get(["show_guides"])
        if stored_show_guides is None:
            stored_show_guides = self._settings.get_float(["guide_opacity"]) > 0.0
        show_guides = _as_bool(payload.get("show_guides", stored_show_guides))
        guide_opacity = 0.7 if show_guides else 0.0

        extra = None
        if kind == "Concave+Convex":
            split_percent = float(payload.get("split_percent", self._settings.get_float(["split_percent"])))
            extra = split_percent / 100.0
        elif kind == "X + 1":
            extra = int(payload.get("x_count", self._settings.get_int(["x_count"])))
        elif kind == "Sine Skip":
            extra = max(2, int(payload.get("skip_count", self._settings.get_int(["skip_count"]) or 2)))
        elif kind == "Bead":
            extra = float(payload.get("flat_length", self._settings.get_float(["flat_length"])))

        return {
            "kind": kind,
            "holtz_style": holtz_style,
            "holtz_n2": holtz_n2,
            "holtz_a2": holtz_a2,
            "show_guides": show_guides,
            "guide_opacity": guide_opacity,
            "radius": radius,
            "count": count,
            "height": height,
            "phase": phase,
            "extra": extra,
        }

    def _build_svg_from_payload(self, payload, include_guides=False, mirror_horizontally=False, guide_angle_offset_deg=0.0):
        params = self._parse_rosette_payload(payload)

        path_data, bounds, _segments = self._build_path_and_bounds_from_params(
            params,
            mirror_horizontally=mirror_horizontally,
        )
        docname = str(payload.get("filename") or "RosetteGenerator.svg").strip()
        if not docname.lower().endswith(".svg"):
            docname = "{0}.svg".format(docname)
        svg = build_svg_document(
            path_data,
            bounds,
            docname=docname,
            include_guides=include_guides,
            guide_angle_offset_deg=guide_angle_offset_deg,
            guide_opacity=params["guide_opacity"],
        )
        return svg, path_data, params, bounds

    def _build_path_and_bounds_from_params(self, params, mirror_horizontally=False):
        if params["holtz_style"]:
            segments, _ = get_holtz_geometry(
                params["holtz_style"],
                params["radius"],
                params["count"],
                params["height"],
                phase=params["phase"],
                n2=params["holtz_n2"],
                a2=params["holtz_a2"],
            )
        else:
            segments, _ = get_rosette_geometry(
                params["kind"],
                params["radius"],
                params["count"],
                params["height"],
                extra=params["extra"],
                phase=params["phase"],
            )
        if mirror_horizontally:
            segments = _mirror_segments_horizontally(segments)
        path_data, bounds = build_curve_path_data(segments)
        return path_data, bounds, segments

    def _segments_to_outline_points(self, segments):
        outline_points = []

        for segment in segments:
            if segment[0] == "arc":
                _, p0, p1, p2 = segment
                x_vals, y_vals = arc_through_three_points(p0, p1, p2, samples=120)
            else:
                _, p0, p1 = segment
                x_vals = [p0[0], p1[0]]
                y_vals = [p0[1], p1[1]]

            points = list(zip(x_vals, y_vals))
            if outline_points and points:
                points = points[1:]
            outline_points.extend(points)

        if outline_points and outline_points[0] != outline_points[-1]:
            outline_points.append(outline_points[0])

        return outline_points

    def _build_polygon_from_payload(self, payload):
        if Polygon is None:
            raise RuntimeError("Merge requires the shapely package.")

        params = self._parse_rosette_payload(payload)
        if params["holtz_style"]:
            segments, _ = get_holtz_geometry(
                params["holtz_style"],
                params["radius"],
                params["count"],
                params["height"],
                phase=params["phase"],
                n2=params["holtz_n2"],
                a2=params["holtz_a2"],
            )
        else:
            segments, _ = get_rosette_geometry(
                params["kind"],
                params["radius"],
                params["count"],
                params["height"],
                extra=params["extra"],
                phase=params["phase"],
            )

        outline_points = self._segments_to_outline_points(segments)
        if len(outline_points) < 4:
            raise ValueError("Not enough points to build geometry.")

        geometry = Polygon(outline_points)
        if not geometry.is_valid:
            geometry = geometry.buffer(0)
        if geometry.is_empty:
            raise ValueError("Generated geometry is empty.")

        return geometry

    def _iter_polygon_parts(self, geometry):
        if geometry is None or geometry.is_empty:
            return
        if geometry.geom_type == "Polygon":
            yield geometry
            return
        if geometry.geom_type == "MultiPolygon":
            for polygon in geometry.geoms:
                yield polygon
            return
        if geometry.geom_type == "GeometryCollection":
            for part in geometry.geoms:
                for nested in self._iter_polygon_parts(part):
                    yield nested

    def _build_svg_from_geometry(
        self,
        geometry,
        stroke="#000000",
        stroke_width=0.25,
        docname="RosetteGenerator.svg",
        include_guides=False,
        mirror_horizontally=False,
        guide_angle_offset_deg=0.0,
    ):
        if geometry is None or geometry.is_empty:
            raise ValueError("No merged geometry was generated")

        path_parts = []
        all_x = []
        all_y = []
        for polygon in self._iter_polygon_parts(geometry):
            exterior_points = list(polygon.exterior.coords)
            if not exterior_points:
                continue
            if mirror_horizontally:
                exterior_points = _mirror_points_horizontally(exterior_points)
            all_x.extend([point[0] for point in exterior_points])
            all_y.extend([point[1] for point in exterior_points])
            path_parts.append("M {0:.6f} {1:.6f}".format(exterior_points[0][0], exterior_points[0][1]))
            for px, py in exterior_points[1:]:
                path_parts.append("L {0:.6f} {1:.6f}".format(px, py))
            path_parts.append("Z")

            for interior in polygon.interiors:
                interior_points = list(interior.coords)
                if not interior_points:
                    continue
                if mirror_horizontally:
                    interior_points = _mirror_points_horizontally(interior_points)
                all_x.extend([point[0] for point in interior_points])
                all_y.extend([point[1] for point in interior_points])
                path_parts.append("M {0:.6f} {1:.6f}".format(interior_points[0][0], interior_points[0][1]))
                for px, py in interior_points[1:]:
                    path_parts.append("L {0:.6f} {1:.6f}".format(px, py))
                path_parts.append("Z")

        d_value = " ".join(path_parts)
        if not d_value or not all_x or not all_y:
            raise ValueError("No merged geometry was generated")

        min_x = min(all_x)
        min_y = min(all_y)
        max_x = max(all_x)
        max_y = max(all_y)
        margin = max(stroke_width * 2.0, 0.5)

        view_min_x = min_x - margin
        view_min_y = min_y - margin
        view_w = (max_x - min_x) + (2.0 * margin)
        view_h = (max_y - min_y) + (2.0 * margin)

        svg_lines = [
            "<?xml version=\"1.0\" encoding=\"UTF-8\" standalone=\"no\"?>",
            "<svg",
            "   version=\"1.1\"",
            "   viewBox=\"{0:.6f} {1:.6f} {2:.6f} {3:.6f}\"".format(
                view_min_x, view_min_y, view_w, view_h
            ),
            "   id=\"svg1\"",
            "   sodipodi:docname=\"{0}\"".format(docname),
            "   inkscape:version=\"1.4.2\"",
            "   xmlns:inkscape=\"http://www.inkscape.org/namespaces/inkscape\"",
            "   xmlns:sodipodi=\"http://sodipodi.sourceforge.net/DTD/sodipodi-0.dtd\"",
            "   xmlns=\"http://www.w3.org/2000/svg\"",
            "   xmlns:svg=\"http://www.w3.org/2000/svg\">",
            "  <defs id=\"defs1\" />",
            "  <sodipodi:namedview",
            "     id=\"namedview1\"",
            "     pagecolor=\"#ffffff\"",
            "     bordercolor=\"#000000\"",
            "     borderopacity=\"0.25\"",
            "     inkscape:showpageshadow=\"2\"",
            "     inkscape:pageopacity=\"0.0\"",
            "     inkscape:pagecheckerboard=\"0\"",
            "     inkscape:deskcolor=\"#d1d1d1\"",
            "     inkscape:current-layer=\"svg1\" />",
        ]

        if include_guides:
            _append_polar_guides(
                svg_lines,
                (min_x, min_y, max_x, max_y),
                angle_offset_deg=guide_angle_offset_deg,
            )

        svg_lines.append(
            "  <path d=\"{0}\" fill=\"none\" stroke=\"{1}\" stroke-width=\"{2:.6f}\" stroke-linecap=\"round\" stroke-linejoin=\"round\" id=\"path1\" />".format(
                d_value, stroke, stroke_width
            )
        )
        svg_lines.append("</svg>")
        svg = "\n".join(svg_lines)

        return svg, d_value

    @octoprint.plugin.BlueprintPlugin.route("/settings", methods=["GET", "POST"])
    def settings_endpoint(self):
        if request.method == "GET":
            stored_show_guides = self._settings.get(["show_guides"])
            if stored_show_guides is None:
                stored_show_guides = self._settings.get_float(["guide_opacity"]) > 0.0
            return jsonify(
                {
                    "ok": True,
                    "settings": {
                        "default_style": self._settings.get(["default_style"]),
                        "default_holtz_style": str(self._settings.get(["default_holtz_style"]) or ""),
                        "default_holtz_n2": self._settings.get_int(["default_holtz_n2"]),
                        "default_holtz_a2": self._settings.get_float(["default_holtz_a2"]),
                        "show_guides": _as_bool(stored_show_guides),
                        "outer_radius": self._settings.get_float(["outer_radius"]),
                        "amplitude": self._settings.get_float(["amplitude"]),
                        "num_segments": self._settings.get_int(["num_segments"]),
                        "phase": self._settings.get_float(["phase"]),
                        "split_percent": self._settings.get_float(["split_percent"]),
                        "x_count": self._settings.get_int(["x_count"]),
                        "skip_count": max(2, self._settings.get_int(["skip_count"]) or 2),
                        "flat_length": self._settings.get_float(["flat_length"]),
                        "auto_preview": _as_bool(self._settings.get(["auto_preview"])),
                        "export_dir": str(self._settings.get(["export_dir"]) or ""),
                    },
                    "merge_available": unary_union is not None and Polygon is not None,
                }
            )

        payload = request.get_json(silent=True) or {}
        settings = payload.get("settings") or {}

        try:
            default_style = str(settings.get("default_style", self._settings.get(["default_style"]))).strip()
            default_holtz_style = str(settings.get("default_holtz_style", self._settings.get(["default_holtz_style"]) or "")).strip()
            default_holtz_n2 = int(settings.get("default_holtz_n2", self._settings.get_int(["default_holtz_n2"])))
            default_holtz_a2 = float(settings.get("default_holtz_a2", self._settings.get_float(["default_holtz_a2"])))
            show_guides = _as_bool(settings.get("show_guides", self._settings.get(["show_guides"])))
            if default_style not in ROSETTE_TYPES:
                raise ValueError("Unknown default style")
            if default_holtz_style and default_holtz_style not in HOLTZ_TYPES:
                raise ValueError("Unknown default Holtz style")

            self._settings.set(["default_style"], default_style)
            self._settings.set(["default_holtz_style"], default_holtz_style)
            self._settings.set_int(["default_holtz_n2"], max(3, default_holtz_n2))
            self._settings.set_float(["default_holtz_a2"], default_holtz_a2)
            self._settings.set(["show_guides"], show_guides)
            self._settings.set_float(["outer_radius"], float(settings.get("outer_radius", self._settings.get_float(["outer_radius"]))))
            self._settings.set_float(["amplitude"], float(settings.get("amplitude", self._settings.get_float(["amplitude"]))))
            self._settings.set_int(["num_segments"], int(settings.get("num_segments", self._settings.get_int(["num_segments"]))))
            self._settings.set_float(["phase"], float(settings.get("phase", self._settings.get_float(["phase"]))))
            self._settings.set_float(["split_percent"], float(settings.get("split_percent", self._settings.get_float(["split_percent"]))))
            self._settings.set_int(["x_count"], int(settings.get("x_count", self._settings.get_int(["x_count"]))))
            self._settings.set_int(["skip_count"], max(2, int(settings.get("skip_count", self._settings.get_int(["skip_count"]) or 2))))
            self._settings.set_float(["flat_length"], float(settings.get("flat_length", self._settings.get_float(["flat_length"]))))
            self._settings.set(["auto_preview"], _as_bool(settings.get("auto_preview", self._settings.get(["auto_preview"]))))
            self._settings.set(["export_dir"], str(settings.get("export_dir", self._settings.get(["export_dir"]) or "")).strip())
            self._settings.save()

            return jsonify({"ok": True, "message": "Defaults saved"})
        except Exception as exc:
            return jsonify({"ok": False, "error": str(exc)}), 400

    @octoprint.plugin.BlueprintPlugin.route("/preview", methods=["POST"])
    def preview(self):
        payload = request.get_json(silent=True) or {}
        try:
            held_payload = payload.get("held")

            svg, path_data, params, current_bounds = self._build_svg_from_payload(
                payload,
                include_guides=True,
                mirror_horizontally=True,
                guide_angle_offset_deg=180.0,
            )

            if held_payload:
                _svg_held, held_path, _held_params, held_bounds = self._build_svg_from_payload(
                    held_payload,
                    include_guides=True,
                    mirror_horizontally=True,
                    guide_angle_offset_deg=180.0,
                )

                combined_bounds = (
                    min(current_bounds[0], held_bounds[0]),
                    min(current_bounds[1], held_bounds[1]),
                    max(current_bounds[2], held_bounds[2]),
                    max(current_bounds[3], held_bounds[3]),
                )
                docname = str(payload.get("filename") or "RosetteGenerator.svg").strip()
                if not docname.lower().endswith(".svg"):
                    docname = "{0}.svg".format(docname)
                svg = build_svg_document_multi(
                    [
                        {"path": held_path, "stroke": "#888888"},
                        {"path": path_data, "stroke": "#000000"},
                    ],
                    combined_bounds,
                    docname=docname,
                    include_guides=True,
                    guide_angle_offset_deg=180.0,
                    guide_opacity=params["guide_opacity"],
                )

            return jsonify({"ok": True, "svg": svg, "path": path_data})
        except Exception as exc:
            return jsonify({"ok": False, "error": str(exc)}), 400

    @octoprint.plugin.BlueprintPlugin.route("/export", methods=["POST"])
    def export(self):
        payload = request.get_json(silent=True) or {}
        filename = payload.get("filename", "RosetteGenerator.svg")
        if not filename.lower().endswith(".svg"):
            filename = "{0}.svg".format(filename)

        try:
            if _as_bool(payload.get("export_merged")):
                held_payload = payload.get("held")
                current_payload = payload.get("current")
                if not held_payload or not current_payload:
                    raise ValueError("Merged export requires held and current rosettes.")

                if unary_union is None or Polygon is None:
                    raise ValueError("Merge export requires shapely. Install shapely in OctoPrint's Python environment.")

                held_geometry = self._build_polygon_from_payload(held_payload)
                current_geometry = self._build_polygon_from_payload(current_payload)
                merged_geometry = unary_union([held_geometry, current_geometry])
                if not merged_geometry.is_valid:
                    merged_geometry = merged_geometry.buffer(0)
                if merged_geometry.is_empty:
                    raise ValueError("Merged geometry is empty")

                svg, _path_data = self._build_svg_from_geometry(merged_geometry, docname=filename)
            else:
                svg, _path_data, _params, _bounds = self._build_svg_from_payload(payload)
        except Exception as exc:
            return jsonify({"ok": False, "error": str(exc)}), 400

        export_dir = str(payload.get("export_dir") or self._settings.get(["export_dir"]) or "").strip()
        if not export_dir:
            return jsonify({"ok": False, "error": "Export folder is not set."}), 400

        export_dir = os.path.abspath(export_dir)
        try:
            os.makedirs(export_dir, exist_ok=True)
        except Exception as exc:
            return jsonify({"ok": False, "error": "Could not create export folder: {0}".format(exc)}), 400

        export_path = os.path.join(export_dir, filename)
        try:
            with open(export_path, "w", encoding="utf-8") as out_file:
                out_file.write(svg)
        except Exception as exc:
            return jsonify({"ok": False, "error": "Could not save SVG: {0}".format(exc)}), 400

        return jsonify({"ok": True, "path": export_path})

    @octoprint.plugin.BlueprintPlugin.route("/merge", methods=["POST"])
    def merge(self):
        if unary_union is None or Polygon is None:
            return jsonify({"ok": False, "error": "Merge requires shapely. Install shapely in OctoPrint's Python environment."}), 400

        payload = request.get_json(silent=True) or {}
        held_payload = payload.get("held")
        current_payload = payload.get("current")

        if not held_payload:
            return jsonify({"ok": False, "error": "Hold a rosette first."}), 400
        if not current_payload:
            return jsonify({"ok": False, "error": "Create or preview a current rosette first."}), 400

        try:
            held_geometry = self._build_polygon_from_payload(held_payload)
            current_geometry = self._build_polygon_from_payload(current_payload)
            merged_geometry = unary_union([held_geometry, current_geometry])
            if not merged_geometry.is_valid:
                merged_geometry = merged_geometry.buffer(0)
            if merged_geometry.is_empty:
                raise ValueError("Merged geometry is empty")

            docname = str(payload.get("filename") or "RosetteGenerator_merged.svg").strip()
            if not docname.lower().endswith(".svg"):
                docname = "{0}.svg".format(docname)
            svg, path_data = self._build_svg_from_geometry(
                merged_geometry,
                docname=docname,
                mirror_horizontally=True,
            )
            return jsonify({"ok": True, "svg": svg, "path": path_data})
        except Exception as exc:
            return jsonify({"ok": False, "error": str(exc)}), 400


__plugin_name__ = "RosetteGenerator"
__plugin_version__ = "0.1.0"
__plugin_description__ = "Generate decorative rosette curves and export SVG files from OctoPrint."
__plugin_pythoncompat__ = ">=3.8,<4"


def __plugin_load__():
    global __plugin_implementation__
    __plugin_implementation__ = RosetteGeneratorPlugin()
