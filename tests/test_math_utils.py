import pytest

from math_utils import fib, factorial


@pytest.mark.parametrize(
    "n,expected",
    [
        (0, 0),
        (1, 1),
        (2, 1),
        (3, 2),
        (5, 5),
        (10, 55),
    ],
)
def test_fib_normal_cases(n, expected):
    """Test typical Fibonacci values including edge cases n=0 and n=1."""
    assert fib(n) == expected


@pytest.mark.parametrize(
    "n",
    [-1, -5, -10],
)
def test_fib_negative_input_raises(n):
    """fib should raise ValueError for negative inputs."""
    with pytest.raises(ValueError):
        fib(n)


@pytest.mark.parametrize(
    "n,expected",
    [
        (0, 1),
        (1, 1),
        (2, 2),
        (3, 6),
        (5, 120),
        (10, 3628800),
    ],
)
def test_factorial_normal_cases(n, expected):
    """Test typical factorial values including edge cases n=0 and n=1."""
    assert factorial(n) == expected


@pytest.mark.parametrize(
    "n",
    [-1, -3, -20],
)
def test_factorial_negative_input_raises(n):
    """factorial should raise ValueError for negative inputs."""
    with pytest.raises(ValueError):
        factorial(n)
