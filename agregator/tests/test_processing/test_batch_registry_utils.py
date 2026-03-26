import pytest
import pandas as pd
import os
import tempfile
from unittest.mock import patch, MagicMock
from pathlib import Path
from agregator.processing.batch_registry_utils import RegistryManager


@pytest.fixture
def sample_registry_data():
    """Создает тестовые данные реестра"""
    return pd.DataFrame({
        'ГОД': ['2023', '2023', '2024'],
        'Дата окончания проведения ГИКЭ': ['2023-05-15 00:00:00', '2023-06-20 00:00:00', '2024-01-10 00:00:00'],
        'Номер (если имеется) и наименование Акта ГИКЭ': ['Акт №1', 'Акт №2', 'Акт №3'],
        'Эксперт (физ. или юр.лицо)': ['Иванов И.И.', 'Петров П.П.', 'Сидоров С.С.'],
        'Муниципальный район, Муниципальный округ (в т.ч. с 15.05.2025)': ['Район1', 'Район2', 'Район3'],
        'Заказчик работ (*если не указан, то заказчик экспертизы)': ['Заказчик1', 'Заказчик2', 'Заказчик3'],
        'Площадь, линейная протяжённость и/или др. параменты объекта': ['100 га', '200 га', '300 га'],
        'Исполнитель полевых работ (юр. лицо)': ['ООО "А"', 'ООО "Б"', 'ООО "В"'],
        'Открытый лист': ['ОЛ1', 'ОЛ2', 'ОЛ3'],
        'Заключение. Выявленые объекты.': ['Заключение1', 'Заключение2', 'Заключение3'],
        'Объекты расположенные в непосредственной близости. Для границ': ['Объекты1', 'Объекты2', 'Объекты3']
    })


@pytest.fixture
def temp_registry_file(sample_registry_data):
    """Создает временный файл реестра XLSX"""
    with tempfile.NamedTemporaryFile(suffix='.xlsx', delete=False) as tmp:
        tmp_path = tmp.name
    sample_registry_data.to_excel(tmp_path, index=False, engine='openpyxl')
    yield tmp_path
    os.unlink(tmp_path)


class TestRegistryManager:

    # ---- Инициализация и загрузка реестра ----
    def test_init_loads_registry(self, temp_registry_file):
        manager = RegistryManager(temp_registry_file)
        assert manager.df is not None
        assert len(manager.df) == 3
        assert 'ГОД' in manager.df.columns

    def test_init_missing_registry(self):
        manager = RegistryManager('/nonexistent/path.xlsx')
        assert manager.df is not None
        assert manager.df.empty

    def test_init_loading_error(self, temp_registry_file):
        with patch('pandas.read_excel', side_effect=Exception("Read error")):
            manager = RegistryManager(temp_registry_file)
            assert manager.df is not None
            assert manager.df.empty

    # ---- _convert_date_format ----
    def test_convert_date_format_valid(self, temp_registry_file):
        manager = RegistryManager(temp_registry_file)
        assert manager._convert_date_format('2023-04-29 00:00:00') == '29.04.2023'
        assert manager._convert_date_format('2023-04-29') == '29.04.2023'
        assert manager._convert_date_format('29.04.2023') == '29.04.2023'
        assert manager._convert_date_format('') == ''
        assert manager._convert_date_format('nan') == ''

    def test_convert_date_format_exception(self, temp_registry_file):
        manager = RegistryManager(temp_registry_file)
        with patch('re.match', side_effect=Exception("Regex error")):
            result = manager._convert_date_format('2023-04-29')
            assert result == '2023-04-29'  # Возвращает исходное значение при ошибке

    # ---- _normalize_year ----
    def test_normalize_year(self, temp_registry_file):
        manager = RegistryManager(temp_registry_file)
        assert manager._normalize_year(2023.0) == '2023'
        assert manager._normalize_year('2023') == '2023'
        assert manager._normalize_year('2023.0') == '2023'
        assert manager._normalize_year('') == ''
        assert manager._normalize_year(pd.NA) == ''

    # ---- _calculate_field_similarity ----
    def test_calculate_field_similarity(self, temp_registry_file):
        manager = RegistryManager(temp_registry_file)
        assert manager._calculate_field_similarity('Иванов И.И.', 'Иванов И.И.') == 1.0
        assert manager._calculate_field_similarity('Иванов И.И.', 'Петров П.П.') < 0.5
        assert manager._calculate_field_similarity('', 'Иванов И.И.') == 0.0
        assert manager._calculate_field_similarity('nan', 'Иванов И.И.') == 0.0

    # ---- _calculate_practical_similarity ----
    def test_calculate_practical_similarity(self, temp_registry_file, sample_registry_data):
        manager = RegistryManager(temp_registry_file)
        # Идеальное совпадение по всем полям
        extracted = {
            'Дата окончания проведения ГИКЭ': '15.05.2023',
            'Эксперт (физ. или юр.лицо)': 'Иванов И.И.',
            'Номер (если имеется) и наименование Акта ГИКЭ': 'Акт №1',
            'Место проведения экспертизы': 'Район1',
            'Заказчик работ (*если не указан, то заказчик экспертизы)': 'Заказчик1',
            'Площадь, протяжённость и/или др. параменты объекта': '100 га',
            'Исполнитель полевых работ (юр. лицо)': 'ООО "А"',
            'ОЛ': 'ОЛ1',
            'Заключение. Выявленые объекты.': 'Заключение1',
            'Объекты расположенные в непосредственной близости. Для границ': 'Объекты1'
        }
        similarity = manager._calculate_practical_similarity(extracted, sample_registry_data.iloc[0])
        assert similarity > 0.8

    def test_calculate_practical_similarity_no_fields(self, temp_registry_file, sample_registry_data):
        manager = RegistryManager(temp_registry_file)
        extracted = {}
        similarity = manager._calculate_practical_similarity(extracted, sample_registry_data.iloc[0])
        assert similarity == 0.0

    # ---- find_best_match_by_content ----
    def test_find_best_match_by_content_success(self, temp_registry_file):
        manager = RegistryManager(temp_registry_file)
        extracted = {
            'ГОД': '2023',
            'Дата окончания проведения ГИКЭ': '15.05.2023',
            'Эксперт (физ. или юр.лицо)': 'Иванов И.И.',
            'Номер (если имеется) и наименование Акта ГИКЭ': 'Акт №1',
            'Место проведения экспертизы': 'Район1',
            'Заказчик работ (*если не указан, то заказчик экспертизы)': 'Заказчик1',
            'Площадь, протяжённость и/или др. параменты объекта': '100 га',
            'Исполнитель полевых работ (юр. лицо)': 'ООО "А"',
            'ОЛ': 'ОЛ1',
            'Заключение. Выявленые объекты.': 'Заключение1',
            'Объекты расположенные в непосредственной близости. Для границ': 'Объекты1'
        }
        match, similarity = manager.find_best_match_by_content(extracted)
        assert match is not None
        assert similarity >= 0.8
        assert match['Номер (если имеется) и наименование Акта ГИКЭ'] == 'Акт №1'

    def test_find_best_match_by_content_year_mismatch(self, temp_registry_file):
        manager = RegistryManager(temp_registry_file)
        extracted = {
            'ГОД': '2025',  # года нет в реестре
            'Дата окончания проведения ГИКЭ': '15.05.2023',
            'Эксперт (физ. или юр.лицо)': 'Иванов И.И.'
        }
        match, similarity = manager.find_best_match_by_content(extracted)
        assert match is None
        assert similarity == 0.0

    def test_find_best_match_by_content_low_similarity(self, temp_registry_file):
        manager = RegistryManager(temp_registry_file)
        extracted = {
            'ГОД': '2023',
            'Дата окончания проведения ГИКЭ': '01.01.2000',
            'Эксперт (физ. или юр.лицо)': 'Совсем другой эксперт'
        }
        match, similarity = manager.find_best_match_by_content(extracted, min_similarity=0.9)
        assert similarity < 0.9

    def test_find_best_match_by_content_empty_registry(self):
        manager = RegistryManager('/nonexistent.xlsx')
        extracted = {'ГОД': '2023'}
        match, similarity = manager.find_best_match_by_content(extracted)
        assert match is None
        assert similarity == 0.0

    # ---- _enrich_from_filename ----
    def test_enrich_from_filename_date(self, temp_registry_file):
        manager = RegistryManager(temp_registry_file)
        table_info = {}
        manager._enrich_from_filename(table_info, "15.05.2023_Акт.pdf")
        assert table_info['Дата окончания проведения ГИКЭ'] == '15.05.2023'
        assert table_info['ГОД'] == '2023'

    def test_enrich_from_filename_expert(self, temp_registry_file):
        manager = RegistryManager(temp_registry_file)
        table_info = {}
        manager._enrich_from_filename(table_info, "15.05.2023 Иванов И.И., test.pdf")
        assert table_info['Эксперт (физ. или юр.лицо)'] == 'Иванов И.И.'

    def test_enrich_from_filename_location(self, temp_registry_file):
        manager = RegistryManager(temp_registry_file)
        table_info = {}
        manager._enrich_from_filename(table_info, "15.05.2023 Иванов И.И., г.Москва.pdf")
        assert table_info['Место проведения экспертизы'] == 'г.Москва'

    def test_enrich_from_filename_type_zu(self, temp_registry_file):
        manager = RegistryManager(temp_registry_file)
        table_info = {}
        manager._enrich_from_filename(table_info, "ЗУ_акт.pdf")
        assert table_info['Вид ГИКЭ'] == 'ЗУ'

    def test_enrich_from_filename_type_npd(self, temp_registry_file):
        manager = RegistryManager(temp_registry_file)
        table_info = {}
        manager._enrich_from_filename(table_info, "НПД_акт.pdf")
        assert table_info['Вид ГИКЭ'] == 'НПД'

    def test_enrich_from_filename_no_overwrite(self, temp_registry_file):
        manager = RegistryManager(temp_registry_file)
        table_info = {'Дата окончания проведения ГИКЭ': '01.01.2024'}
        manager._enrich_from_filename(table_info, "15.05.2023_акт.pdf")
        # не должно перезаписать, так как поле уже заполнено
        assert table_info['Дата окончания проведения ГИКЭ'] == '01.01.2024'

    def test_enrich_from_filename_exception(self, temp_registry_file):
        manager = RegistryManager(temp_registry_file)
        with patch('re.search', side_effect=Exception("Regex error")):
            # функция должна перехватить исключение и ничего не изменить
            table_info = {}
            manager._enrich_from_filename(table_info, "test.pdf")
            assert table_info == {}

    # ---- enrich_from_registry ----
    def test_enrich_from_registry_success(self, temp_registry_file):
        manager = RegistryManager(temp_registry_file)
        table_info = {
            'ГОД': '2023',
            'Дата окончания проведения ГИКЭ': '15.05.2023',
            'Эксперт (физ. или юр.лицо)': 'Иванов И.И.',
            'Номер (если имеется) и наименование Акта ГИКЭ': 'Акт №1',
            'Место проведения экспертизы': 'Район1',
            'Заказчик работ (*если не указан, то заказчик экспертизы)': 'Заказчик1',
            'Площадь, протяжённость и/или др. параменты объекта': '100 га',
            'Исполнитель полевых работ (юр. лицо)': 'ООО "А"',
            'ОЛ': 'ОЛ1',
            'Заключение. Выявленые объекты.': 'Заключение1',
            'Объекты расположенные в непосредственной близости. Для границ': 'Объекты1'
        }
        filename = "15.05.2023_акт.pdf"
        result = manager.enrich_from_registry(table_info, filename)
        # Дата должна быть извлечена из файла, но затем заменена из реестра (преобразована в формат dd.mm.yyyy)
        assert result['Дата окончания проведения ГИКЭ'] == '15.05.2023'  # из реестра
        assert result['ГОД'] == '2023'
        assert result['Эксперт (физ. или юр.лицо)'] == 'Иванов И.И.'
        # Проверяем, что другие поля заменились
        assert result['Номер (если имеется) и наименование Акта ГИКЭ'] == 'Акт №1'
        assert result['Место проведения экспертизы'] == 'Район1'

    def test_enrich_from_registry_no_match(self, temp_registry_file):
        manager = RegistryManager(temp_registry_file)
        table_info = {
            'ГОД': '2025',
            'Дата окончания проведения ГИКЭ': '01.01.2025',
            'Эксперт (физ. или юр.лицо)': 'Неизвестный'
        }
        filename = "test.pdf"
        result = manager.enrich_from_registry(table_info, filename)
        # Данные не должны измениться
        assert result == table_info

    def test_enrich_from_registry_empty(self):
        manager = RegistryManager('/nonexistent.xlsx')
        table_info = {'ГОД': '2023'}
        result = manager.enrich_from_registry(table_info, "test.pdf")
        assert result == table_info
