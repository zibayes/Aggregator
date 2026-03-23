import pytest
from agregator.processing.utils import clean_path_component, str_is_float, str_is_int


class TestCleanPathComponent:
    def test_clean_path_component_keeps_valid_chars(self):
        """Допустимые символы сохраняются"""
        assert clean_path_component("Тест_1-2,3.4 (5)") == "Тест1-2,3.4 (5)"
        assert clean_path_component("aAяЯ0-9 .") == "aAяЯ0-9"
        assert clean_path_component("Проект 2024 (финал)") == "Проект 2024 (финал)"

    def test_clean_path_component_removes_invalid_chars(self):
        """Недопустимые символы удаляются"""
        assert clean_path_component("test<file>") == "testfile"
        assert clean_path_component("path:with:colons") == "pathwithcolons"
        assert clean_path_component('"quoted"') == "quoted"
        assert clean_path_component("a/b\\c") == "abc"
        assert clean_path_component("file?name*") == "filename"
        assert clean_path_component("<>:\"/\\|?*") == ""

    def test_clean_path_component_removes_leading_trailing_dots_and_spaces(self):
        """Удаляет точки и пробелы в начале и конце"""
        assert clean_path_component("  test  ") == "test"
        assert clean_path_component(".test.") == "test"
        assert clean_path_component(" . test . ") == "test"
        assert clean_path_component("...") == ""

    def test_clean_path_component_empty_string(self):
        assert clean_path_component("") == ""

    def test_clean_path_component_only_invalid_chars(self):
        assert clean_path_component("<>:\"/\\|?*") == ""

    def test_clean_path_component_unicode_handling(self):
        """Кириллица и другие символы должны оставаться"""
        assert clean_path_component("Привет, мир!") == "Привет, мир"
        assert clean_path_component("«Кавычки»") == "«Кавычки»"
        assert clean_path_component("№ 123") == "123"
        assert clean_path_component("©®™") == ""  # не входят в допустимый диапазон


class TestStrIsFloat:
    """Тесты для функции str_is_float"""

    @pytest.mark.parametrize("value", [
        "123", "123.0", "-123", "0.5", ".5", "12e3", "12E-3", "inf", "-inf", "nan",
        " 123 ", "  123.45  ", "  -0.5  ",
    ])
    def test_str_is_float_true(self, value):
        """Строки, которые можно преобразовать в float"""
        assert str_is_float(value) is True

    @pytest.mark.parametrize("value", [
        "abc", "123x", "", " ", "12.34.56", "12,34", "None", "True",
    ])
    def test_str_is_float_false(self, value):
        """Строки, которые нельзя преобразовать в float"""
        assert str_is_float(value) is False


class TestStrIsInt:
    """Тесты для функции str_is_int"""

    @pytest.mark.parametrize("value", [
        "123", "-123", "0", " 42 ", "  -99  ",
    ])
    def test_str_is_int_true(self, value):
        """Строки, которые можно преобразовать в int"""
        assert str_is_int(value) is True

    @pytest.mark.parametrize("value", [
        "123.0", "abc", "12.34", "12e3", " 12.0 ", "", " ", "12,34",
    ])
    def test_str_is_int_false(self, value):
        """Строки, которые нельзя преобразовать в int"""
        assert str_is_int(value) is False
