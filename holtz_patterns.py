"""
 * Holtzapffel Rosettes - code borrowed from Bill Ooms - CornLathe project.
 *
 * @author Bill Ooms. Copyright 2015 Studio of Bill Ooms. All rights reserved.
 * 
 * This program is free software: you can redistribute it and/or modify
 * it under the terms of the GNU General Public License as published by
 * the Free Software Foundation, either version 3 of the License, or
 * (at your option) any later version.
 * 
 * This program is distributed in the hope that it will be useful,
 * but WITHOUT ANY WARRANTY; without even the implied warranty of
 * MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
 * GNU General Public License for more details.
 * 
 * You should have received a copy of the GNU General Public License
 * along with this program.  If not, see <http://www.gnu.org/licenses/>.
 

Python equivalents of Holtzapffel rosette style formulas (A-S).

Each function returns a normalized value in the range 0.0 to 1.0 for a
normalized input ``n``.
"""

from __future__ import annotations

import math


def _wrap_01(n: float) -> float:
    if n > 1.0 or n < 0.0:
        return n - math.floor(n)
    return n


def holtz_a(n: float) -> float:
    return 0.5 - 0.5 * math.cos(n * 2.0 * math.pi)


def holtz_b(n: float) -> float:
    nn = _wrap_01(n)
    z = 0.0
    if nn < 2.0 / 3.0:
        z = holtz_a(nn * 3.0)
    return z


def holtz_c(n: float, r: int) -> float:
    nn = _wrap_01(n)
    rr = max(r, 3)
    alpha_rad = math.pi / rr
    tan_theta = math.tan((nn * 2.0 - 1.0) * alpha_rad)
    s = 1.0 - math.cos(alpha_rad)
    x = math.cos(alpha_rad)
    y = x * tan_theta
    z = 1.0 - math.sqrt(x * x + y * y)
    z = z / s
    return z


def holtz_d(n: float, r: int) -> float:
    nn = _wrap_01(n)
    rr = max(r, 3)
    return 1.0 - holtz_c(nn, rr)


def holtz_e(n: float, r: int, n2: int, a2: float) -> float:
    nn = _wrap_01(n)
    nn2 = max(n2, 3)
    if nn < 0.5:
        a = 2.0 * nn
    else:
        a = 2.0 * (1.0 - nn)
    return a * holtz_a(nn * nn2)


def holtz_f(n: float) -> float:
    nn = _wrap_01(n)
    nn = 2.0 * nn
    if nn > 1.0:
        nn = 2.0 - nn

    z = math.sin(nn * 2.0 * math.pi)
    if nn >= 0.75:
        z = z + 1.0
    elif nn > 0.25:
        z = z + (1.0 - math.sin(nn * 2.0 * math.pi)) / 2.0
    return z


def holtz_g(n: float) -> float:
    nn = _wrap_01(n)
    z = 0.0
    if nn < 0.5:
        z = holtz_a(nn * 2.0)
    return z


def holtz_h(n: float, r: int, n2: int, a2: float) -> float:
    nn = _wrap_01(n)
    nn2 = max(n2, 3)
    ampl2 = a2
    if ampl2 < 0.0 or ampl2 > 1.0:
        ampl2 = 0.5

    division = 2.0 / float(nn2)
    if nn < division:
        a = 1.0
    else:
        a = ampl2
    return a * holtz_a(nn * nn2)


def holtz_i(n: float, r: int, n2: int, a2: float) -> float:
    nn = _wrap_01(n)
    rr = max(r, 3)
    nn2 = max(n2, 3)
    ampl2 = a2
    if ampl2 < 0.0 or ampl2 > 1.0:
        ampl2 = 0.1

    s = ampl2 * holtz_a(nn * nn2)
    outline = (1.0 - ampl2) * holtz_c(nn, rr)
    return outline + s


def holtz_j(n: float, r: int, n2: int, a2: float) -> float:
    nn = _wrap_01(n)
    rr = max(r, 3)
    nn2 = max(n2, 3)
    ampl2 = a2
    if ampl2 < 0.0 or ampl2 > 1.0:
        ampl2 = 0.1

    dead_zone = 0.3 / rr
    if nn < dead_zone or nn > (1.0 - dead_zone):
        return holtz_j(dead_zone, r, n2, a2)

    s = ampl2 * holtz_a(nn * nn2)
    outline = (1.0 - ampl2) * holtz_d(nn, rr)
    return outline + s


def holtz_k(n: float) -> float:
    nn = _wrap_01(n)
    division = 0.25
    scale = 1.0 / (1.0 - division)
    if nn < division:
        return holtz_a(nn * 8.0)
    return holtz_f((nn - division) * scale)


def _holtz_alt_small_big(n: float, r: int, total: int, nsmall: int, min_repeat: int) -> float:
    nn = _wrap_01(n)
    rr = max(r, min_repeat)

    big = total - nsmall
    division = float(nsmall) / float(total)
    scale = 1.0 / (1.0 - division)

    if nn < division:
        return holtz_d(nn * float(total), rr * total)
    return holtz_d((nn - division) * scale, rr * total // big)


def holtz_l(n: float, r: int) -> float:
    return _holtz_alt_small_big(n, r, total=3, nsmall=1, min_repeat=2)


def holtz_m(n: float, r: int) -> float:
    return _holtz_alt_small_big(n, r, total=6, nsmall=3, min_repeat=2)


def holtz_n(n: float, r: int) -> float:
    return _holtz_alt_small_big(n, r, total=6, nsmall=4, min_repeat=1)


def holtz_o(n: float, r: int) -> float:
    return _holtz_alt_small_big(n, r, total=8, nsmall=5, min_repeat=2)


def holtz_p(n: float) -> float:
    nn = _wrap_01(n)
    z = 0.0
    if nn < 2.0 / 3.0:
        z = holtz_a(nn * 6.0)
    return z


def holtz_q(n: float, r: int, n2: int, a2: float) -> float:
    nn = _wrap_01(n)
    rr = max(r, 3)
    nn2 = max(n2, 3)
    ampl2 = a2
    if ampl2 < 0.0 or ampl2 > 1.0:
        ampl2 = 0.1

    f = ampl2 * holtz_d(nn * nn2, rr * nn2)
    outline = (1.0 - ampl2) * holtz_c(nn, rr)
    return outline + f


def holtz_r(n: float, r: int) -> float:
    return _holtz_alt_small_big(n, r, total=4, nsmall=2, min_repeat=2)


def holtz_s(n: float, r: int, n2: int, a2: float) -> float:
    nn = _wrap_01(n)
    nn2 = max(n2, 3)
    ampl2 = a2
    if ampl2 < 0.0 or ampl2 > 1.0:
        ampl2 = 0.1

    f = ampl2 * holtz_d(nn * nn2, r * nn2)
    outline = (1.0 - ampl2) * holtz_f(nn)
    return outline + f


HOLTZ_FUNCTIONS = {
    "HoltzA": holtz_a,
    "HoltzB": holtz_b,
    "HoltzC": holtz_c,
    "HoltzD": holtz_d,
    "HoltzE": holtz_e,
    "HoltzF": holtz_f,
    "HoltzG": holtz_g,
    "HoltzH": holtz_h,
    "HoltzI": holtz_i,
    "HoltzJ": holtz_j,
    "HoltzK": holtz_k,
    "HoltzL": holtz_l,
    "HoltzM": holtz_m,
    "HoltzN": holtz_n,
    "HoltzO": holtz_o,
    "HoltzP": holtz_p,
    "HoltzQ": holtz_q,
    "HoltzR": holtz_r,
    "HoltzS": holtz_s,
}


__all__ = [
    "holtz_a",
    "holtz_b",
    "holtz_c",
    "holtz_d",
    "holtz_e",
    "holtz_f",
    "holtz_g",
    "holtz_h",
    "holtz_i",
    "holtz_j",
    "holtz_k",
    "holtz_l",
    "holtz_m",
    "holtz_n",
    "holtz_o",
    "holtz_p",
    "holtz_q",
    "holtz_r",
    "holtz_s",
    "HOLTZ_FUNCTIONS",
]
