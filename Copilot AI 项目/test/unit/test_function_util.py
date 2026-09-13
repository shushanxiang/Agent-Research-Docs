"""测试 function_util.py — timing_decorator"""

import pytest


class TestTimingDecorator:
    """计时装饰器"""

    def test_decorator_returns_result(self):
        from utils.function_util import timing_decorator

        @timing_decorator
        def add(a, b):
            return a + b

        result = add(1, 2)
        assert result == 3

    def test_decorator_preserves_multiple_args(self):
        from utils.function_util import timing_decorator

        @timing_decorator
        def concat(a, b, c):
            return f"{a}{b}{c}"

        result = concat("x", "y", "z")
        assert result == "xyz"

    def test_decorator_preserves_kwargs(self):
        from utils.function_util import timing_decorator

        @timing_decorator
        def greet(name, greeting="Hello"):
            return f"{greeting} {name}"

        result = greet("World", greeting="Hi")
        assert result == "Hi World"

    def test_decorator_with_exception(self):
        from utils.function_util import timing_decorator

        @timing_decorator
        def fail():
            raise ValueError("test error")

        with pytest.raises(ValueError, match="test error"):
            fail()

    def test_decorator_with_none_result(self):
        from utils.function_util import timing_decorator

        @timing_decorator
        def return_none():
            return None

        result = return_none()
        assert result is None
