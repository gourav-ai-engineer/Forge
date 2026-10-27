from calculator import add


def test_add_two_integers() -> None:
    assert add(2, 3) == 5


def test_add_negative_and_positive() -> None:
    assert add(-2, 5) == 3
