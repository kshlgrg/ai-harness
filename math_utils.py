"""Utility functions for basic mathematics.

This module provides iterative implementations of the Fibonacci sequence
and factorial calculation, complete with type hints, input validation,
and comprehensive docstrings.
"""

from __future__ import annotations

__all__: list[str] = ["fib", "factorial"]


def fib(n: int) -> int:
    """Return the *n*th Fibonacci number using an iterative algorithm.

    The sequence is defined as ``fib(0) = 0`` and ``fib(1) = 1`` with each
    subsequent number being the sum of the two preceding ones.

    Args:
        n: A non‑negative integer representing the position in the Fibonacci
           sequence.

    Returns:
        The *n*th Fibonacci number.

    Raises:
        ValueError: If ``n`` is negative.
    """
    if n < 0:
        raise ValueError("n must be a non‑negative integer")
    if n == 0:
        return 0
    a, b = 0, 1
    for _ in range(1, n):
        a, b = b, a + b
    return b


def factorial(n: int) -> int:
    """Return the factorial of ``n`` using an iterative algorithm.

    The factorial of a non‑negative integer ``n`` is the product of all
    positive integers less than or equal to ``n``. By definition, ``0!`` is ``1``.

    Args:
        n: A non‑negative integer.

    Returns:
        The factorial of ``n``.

    Raises:
        ValueError: If ``n`` is negative.
    """
    if n < 0:
        raise ValueError("n must be a non‑negative integer")
    result = 1
    for i in range(2, n + 1):
        result *= i
    return result
