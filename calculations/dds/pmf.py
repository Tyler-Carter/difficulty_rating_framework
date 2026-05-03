"""Closed-form PMF for Nd6 sums and expectation helpers used by AAC and EDPR.

All values are computed from the inclusion-exclusion closed form
(docs/outline.md Appendix C):

    p_N(s) = (1 / f^N) * sum_{k=0}^{floor((s-N)/f)} (-1)^k * C(N,k) * C(s-fk-1, N-1)

Cached on (n, sp, faces). Inputs are tiny integers (N up to 8, SP up to 18,
faces typically 6) so an unbounded LRU is fine.
"""

from __future__ import annotations

from functools import lru_cache
from math import comb


@lru_cache(maxsize=None)
def pmf(n: int, s: int, faces: int = 6) -> float:
    """P(Nd{faces} = s) via the inclusion-exclusion closed form.

    Returns 0 outside the support [n, n*faces].
    """
    if s < n or s > n * faces:
        return 0.0
    total = 0
    k = 0
    while faces * k <= s - n:
        total += (-1) ** k * comb(n, k) * comb(s - faces * k - 1, n - 1)
        k += 1
    return total / faces ** n


@lru_cache(maxsize=None)
def pmf_table(n: int, faces: int = 6) -> tuple[tuple[int, float], ...]:
    """Full PMF as an immutable ((s, p), ...) tuple, ordered by s."""
    return tuple((s, pmf(n, s, faces)) for s in range(n, n * faces + 1))


@lru_cache(maxsize=None)
def p_exceeds(n: int, sp: int, faces: int = 6) -> float:
    """P(Nd{faces} > sp) — the Appendix E penetration probability."""
    if sp >= n * faces:
        return 0.0
    if sp < n:
        return 1.0
    return sum(p for s, p in pmf_table(n, faces) if s > sp)


@lru_cache(maxsize=None)
def e_net(n: int, sp: int, faces: int = 6) -> float:
    """E[max(0, Nd{faces} - sp)] — expected net HP damage per attack."""
    return sum((s - sp) * p for s, p in pmf_table(n, faces) if s > sp)


@lru_cache(maxsize=None)
def e_pen(n: int, sp: int, faces: int = 6) -> float:
    """E[Nd{faces} - sp | Nd{faces} > sp] — expected net HP damage per
    penetrating attack. Undefined when p_exceeds == 0; raises ZeroDivisionError
    in that case so callers must guard with p_exceeds first."""
    pi = p_exceeds(n, sp, faces)
    if pi == 0.0:
        raise ZeroDivisionError(
            f"e_pen({n}, {sp}, {faces}) undefined: P(Nd{faces} > {sp}) = 0"
        )
    return e_net(n, sp, faces) / pi


@lru_cache(maxsize=None)
def e_abs(n: int, sp: int, faces: int = 6) -> float:
    """E[min(Nd{faces}, sp)] — expected armor absorption per attack at SP=sp.

    Penetrating attacks absorb exactly sp; non-penetrating attacks absorb the
    full damage roll.
    """
    return sum(min(s, sp) * p for s, p in pmf_table(n, faces))
