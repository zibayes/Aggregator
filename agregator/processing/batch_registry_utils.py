import pandas as pd
import os
import re
import logging
from typing import Dict, Optional, Any, Tuple
from rapidfuzz import fuzz
from pathlib import Path

logger = logging.getLogger(__name__)


class RegistryManager:
    """Менеджер для работы с реестром XLSX"""

    def __init__(self, registry_path: str):
        self.registry_path = registry_path
        self.GLOBAL_RESULT = {}
        self.df = None
        self._load_registry()

    def _load_registry(self):
        """Загружает реестр из XLSX файла БЕЗ ПРЕОБРАЗОВАНИЙ ТИПОВ"""
        try:
            if os.path.exists(self.registry_path):
                # ЗАГРУЖАЕМ С ТОЧНЫМИ ТИПАМИ КАК В ТАБЛИЦЕ
                self.df = pd.read_excel(
                    self.registry_path,
                    engine='openpyxl',
                    dtype=str,  # ВСЕ КАК СТРОКИ
                    keep_default_na=False  # НЕ ПРЕОБРАЗОВЫВАТЬ ПУСТЫЕ В NaN
                )
                logger.info(f"Реестр загружен: {len(self.df)} записей")

                if 'Дата окончания проведения ГИКЭ' in self.df.columns:
                    self.df['Дата окончания проведения ГИКЭ'] = self.df['Дата окончания проведения ГИКЭ'].apply(
                        lambda x: self._convert_date_format(x) if x and x != 'nan' else ''
                    )

                logger.info(f"Реестр загружен: {len(self.df)} записей")

            else:
                logger.warning(f"Файл реестра не найден: {self.registry_path}")
                self.df = pd.DataFrame()
        except Exception as e:
            logger.error(f"Ошибка загрузки реестра: {e}")
            self.df = pd.DataFrame()

    def _convert_date_format(self, date_str):
        """Конвертирует дату из '2023-04-29 00:00:00' в '29.04.2023'"""
        try:
            if not date_str or str(date_str).strip() == 'nan':
                return ''

            date_str = str(date_str).strip()

            # Если уже в правильном формате, возвращаем как есть
            if re.match(r'\d{1,2}\.\d{1,2}\.\d{4}', date_str):
                return date_str

            # Конвертируем из '2023-04-29 00:00:00' в '29.04.2023'
            if re.match(r'\d{4}-\d{1,2}-\d{1,2}', date_str):
                parts = date_str.split(' ')[0].split('-')
                if len(parts) == 3:
                    return f"{parts[2]}.{parts[1]}.{parts[0]}"

            return date_str
        except Exception as e:
            logger.warning(f"Ошибка конвертации даты '{date_str}': {e}")
            return date_str

    def find_best_match_by_content(self, extracted_data: Dict, min_similarity: float = 0.5) -> Tuple[
        Optional[Dict], float, int]:
        """
        ПРАКТИЧНЫЙ алгоритм поиска в реестре:
        """
        if self.df is None or self.df.empty:
            logger.warning("Реестр пуст или не загружен")
            return None, 0.0, -1

        year_field = 'ГОД'
        date_field = 'Дата окончания проведения ГИКЭ'
        expert_field = 'Эксперт (физ. или юр.лицо)'

        # Извлекаем год и НОРМАЛИЗУЕМ его для сравнения
        extracted_year_raw = extracted_data.get(year_field, '')
        extracted_year = self._normalize_year(extracted_year_raw)
        extracted_date = str(extracted_data.get(date_field, '')).strip()

        best_match = best_match_idx = sec_best_match_idx = None
        best_similarity = sec_best_similarity = 0.0
        processed_count = 0

        logger.info(f"   Извлеченный год (сырой): '{extracted_year_raw}'")
        logger.info(f"   Извлеченный год (нормализованный): '{extracted_year}'")

        # Считаем количество отсутствующих приоритетных полей для корректировки порога
        missing_priority_fields = 0
        priority_fields = [expert_field]

        for field in priority_fields:
            extracted_val = str(extracted_data.get(field, '')).strip()
            if not extracted_val or extracted_val == 'nan':
                missing_priority_fields += 1
                logger.info(f"   Отсутствует приоритетное поле: {field}")

        # ПЕРЕБИРАЕМ ВСЕ ЗАПИСИ РЕЕСТРА
        for index, registry_record in self.df.iterrows():
            # НОРМАЛИЗУЕМ ГОД ИЗ РЕЕСТРА ДЛЯ СРАВНЕНИЯ
            registry_year_raw = registry_record.get('ГОД', '')
            registry_year = self._normalize_year(registry_year_raw)
            registry_date = str(registry_record.get(date_field, '')).strip()

            # ЕСЛИ ГОД И ДАТА НЕ СОВПАДАЕТ - ПРОПУСКАЕМ
            if (not extracted_year or not registry_year or extracted_year != registry_year) or (
                    not extracted_date or not registry_date or extracted_date != registry_date):
                continue

            processed_count += 1

            similarity = self._calculate_practical_similarity(extracted_data, registry_record)

            if similarity > best_similarity:
                sec_best_match_idx = best_match_idx
                sec_best_similarity = best_similarity
                best_similarity = similarity
                best_match = registry_record.to_dict()
                best_match_idx = index
                logger.info(f"   🎯 НОВОЕ ЛУЧШЕЕ СОВПАДЕНИЕ: {similarity:.2%} (запись {best_match_idx})")

        logger.info(f"   Обработано записей с совпадающим годом: {processed_count}")

        if best_match and best_similarity >= min_similarity:
            if abs(sec_best_similarity - best_similarity) < 1:
                logger.info(
                    f"✅❌ НАЙДЕНО СОВПАДЕНИЕ В РЕЕСТРЕ: {best_similarity:.2%}, (строка №{best_match_idx + 2}) / Ближайший конкурент - {sec_best_similarity:.2%}, (строка №{sec_best_match_idx + 2 if sec_best_match_idx else -1})")
                logger.info(f"❌ ОДНАКО РАЗНИЦА МЕЖДУ КОНКУРЕНТАМИ НЕБОЛЬШАЯ! ЛУЧШЕ ПРОПУСТИМ!")
                return None, 0.0, -1
            else:
                logger.info(
                    f"✅ НАЙДЕНО СОВПАДЕНИЕ В РЕЕСТРЕ: {best_similarity:.2%}, (строка №{best_match_idx + 2}) / Ближайший конкурент - {sec_best_similarity:.2%}, (строка №{sec_best_match_idx + 2 if sec_best_match_idx else -1})")
                logger.info(f"   Номер акта: {best_match.get('Номер (если имеется) и наименование Акта ГИКЭ', 'N/A')}")
                logger.info(f"   Дата: {best_match.get('Дата окончания проведения ГИКЭ', 'N/A')}")
                logger.info(f"   Эксперт: {best_match.get('Эксперт (физ. или юр.лицо)', 'N/A')}")
                return best_match, best_similarity, best_match_idx
        else:
            if best_match:
                logger.warning(
                    f"❌ Совпадение не достигло порога. Лучшая схожесть: {best_similarity:.2%} (требуется: {min_similarity:.0%})")
            else:
                logger.warning("❌ Не найдено ни одного подходящего совпадения")
            return None, 0.0, -1

    def _normalize_year(self, year_value) -> str:
        """
        Нормализует год для сравнения:
        - float(2023.0) → "2023"
        - "2023" → "2023"
        - "" → ""
        """
        if pd.isna(year_value) or year_value == '':
            return ''

        # Если это float, преобразуем в int и затем в строку
        if isinstance(year_value, float):
            try:
                return str(int(year_value))
            except (ValueError, TypeError):
                return str(year_value).split('.')[0]  # Берем часть до точки

        # Если это строка, убираем .0 если есть
        year_str = str(year_value).strip()
        if year_str.endswith('.0'):
            year_str = year_str[:-2]

        return year_str

    def _calculate_field_similarity(self, str1: str, str2: str) -> float:
        """
        Рассчитывает схожесть двух строк для одного поля (аналогично логике в _calculate_practical_similarity).
        Возвращает значение от 0.0 до 1.0.
        """
        normalized_str1 = str(str1).strip().lower()
        normalized_str2 = str(str2).strip().lower()

        if not normalized_str1 or normalized_str1 == 'nan' or not normalized_str2 or normalized_str2 == 'nan':
            return 0.0

        return fuzz.token_set_ratio(normalized_str1, normalized_str2) / 100

    def _calculate_practical_similarity(self, extracted_data: Dict, registry_record: pd.Series) -> float:
        """
        ПРАКТИЧНОЕ вычисление схожести с ДЕТАЛЬНЫМ ЛОГИРОВАНИЕМ
        """
        total_similarity = 0.0
        total_weight = 0.0

        # МАППИНГ ПОЛЕЙ
        field_mapping = {
            'Дата окончания проведения ГИКЭ': ('Дата окончания проведения ГИКЭ', 0.3),
            'Эксперт (физ. или юр.лицо)': ('Эксперт (физ. или юр.лицо)', 0.3),
            'Номер (если имеется) и наименование Акта ГИКЭ': ('Номер (если имеется) и наименование Акта ГИКЭ', 0.1),
            'Место проведения экспертизы': ('Муниципальный район, Муниципальный округ (в т.ч. с 15.05.2025)', 0.1),
            'Заказчик работ (*если не указан, то заказчик экспертизы)': (
                'Заказчик работ (*если не указан, то заказчик экспертизы)', 0.1),
            'Площадь, протяжённость и/или др. параменты объекта': (
                'Площадь, линейная протяжённость и/или др. параменты объекта', 0.1),
            'Исполнитель полевых работ (юр. лицо)': ('Исполнитель полевых работ (юр. лицо)', 0.1),
            'ОЛ': ('Открытый лист', 0.1),
            'Заключение. Выявленые объекты.': ('Заключение. Выявленые объекты.', 0.1),
            'Объекты расположенные в непосредственной близости. Для границ': (
                'Объекты расположенные в непосредственной близости. Для границ', 0.1)
        }

        field_details = []

        # Обрабатываем все поля согласно маппингу
        for extracted_field, (_, cur_weight) in field_mapping.items():
            extracted_value = str(extracted_data.get(extracted_field, '')).strip().lower()
            if not extracted_value or extracted_field in ('Эксперт (физ. или юр.лицо)',
                                                          'Номер (если имеется) и наименование Акта ГИКЭ'):  #

                continue

            best_field_sim = 0.0
            reg_val = None
            for _, (registry_field, _) in field_mapping.items():
                registry_value = str(registry_record.get(registry_field, '')).strip().lower()
                if not registry_value:
                    continue
                sim = fuzz.token_set_ratio(extracted_value, registry_value)
                if sim > best_field_sim:
                    best_field_sim = sim
                    reg_val = registry_value
            '''
            print(f'extracted_value = {extracted_value}')
            print(f'reg_val = {reg_val}')
            print(f'best_field_sim = {best_field_sim}')
            print(f'*'*50)
            '''

            weighted_similarity = best_field_sim * cur_weight
            total_similarity += weighted_similarity
            total_weight += cur_weight

            # Сохраняем детали для логирования
            field_details.append({
                'field': extracted_field,
                'similarity': best_field_sim,
                'weighted': weighted_similarity,
                'extracted': extracted_value,
                'registry': reg_val
            })

        # ДЕТАЛЬНОЕ ЛОГИРОВАНИЕ ВСЕХ ПОЛЕЙ С СХОЖЕСТЬЮ > 0.3
        '''
        if field_details:
            logger.debug(f"   ДЕТАЛИ СХОЖЕСТИ:")
            for detail in field_details:
                if detail['similarity'] > 0.3:
                    logger.debug(f"      {detail['field']}: {detail['similarity']:.2%} "
                                 f"(вклад: {detail['weighted']:.2%})")
                    logger.debug(f"        Из PDF: '{detail['extracted']}'")
                    logger.debug(f"        Реестр: '{detail['registry']}'")
        '''

        # Если ни одно поле не совпало
        if total_weight == 0:
            return 0.0

        final_similarity = total_similarity / total_weight
        # logger.debug(f"   ИТОГОВАЯ СХОЖЕСТЬ: {final_similarity:.2%}")

        return final_similarity / 100

    def enrich_from_registry(self, table_info: Dict, filename: str) -> Dict:
        """
        ОБОГАЩАЕТ данные из реестра на основе ПРАКТИЧНОГО СХОДСТВА
        """
        # ДОПОЛНИТЕЛЬНОЕ ИЗВЛЕЧЕНИЕ ИЗ НАЗВАНИЯ ФАЙЛА
        self._enrich_from_filename(table_info, filename)

        if self.df is None or self.df.empty:
            logger.warning("Реестр не загружен, пропускаем обогащение")
            return table_info

        logger.info(f"🔍 ПОИСК В РЕЕСТРЕ ДЛЯ ФАЙЛА: {filename}")

        # Логируем все извлеченные данные
        logger.info(f"   ИЗВЛЕЧЕННЫЕ ДАННЫЕ:")
        for key, value in table_info.items():
            if value and str(value).strip() and str(value).strip() != 'nan':
                logger.info(f"     {key}: '{value}'")

        best_match, similarity, best_match_idx = self.find_best_match_by_content(table_info)
        self.GLOBAL_RESULT[filename] = best_match_idx

        if best_match and best_match.get('ГОД') == table_info.get('ГОД') and best_match.get(
                'Дата окончания проведения ГИКЭ') == table_info.get('Дата окончания проведения ГИКЭ'):
            logger.info(f"🎯 ЗАМЕНЯЕМ ДАННЫЕ НА ДОСТОВЕРНЫЕ ИЗ РЕЕСТРА (схожесть: {similarity:.2%})")

            # ОБРАТНЫЙ МАППИНГ
            reverse_field_mapping = {
                'ГОД': 'ГОД',
                'Дата окончания проведения ГИКЭ': 'Дата окончания проведения ГИКЭ',
                'Вид ГИКЭ': 'Вид ГИКЭ',
                'Номер (если имеется) и наименование Акта ГИКЭ': 'Номер (если имеется) и наименование Акта ГИКЭ',
                'Муниципальный район, Муниципальный округ (в т.ч. с 15.05.2025)': 'Место проведения экспертизы',
                'Заказчик работ (*если не указан, то заказчик экспертизы)': 'Заказчик работ (*если не указан, то заказчик экспертизы)',
                'Площадь, линейная протяжённость и/или др. параменты объекта': 'Площадь, протяжённость и/или др. параменты объекта',
                'Эксперт (физ. или юр.лицо)': 'Эксперт (физ. или юр.лицо)',
                'Исполнитель полевых работ (юр. лицо)': 'Исполнитель полевых работ (юр. лицо)',
                'Открытый лист': 'ОЛ',
                'Заключение. Выявленые объекты.': 'Заключение. Выявленые объекты.',
                'Объекты расположенные в непосредственной близости. Для границ': 'Объекты расположенные в непосредственной близости. Для границ'
            }

            replaced_fields = []
            for registry_field, table_field in reverse_field_mapping.items():
                if registry_field in best_match and best_match[registry_field]:
                    if pd.notna(best_match[registry_field]):
                        old_value = table_info.get(table_field, '')
                        new_value = best_match[registry_field]

                        # ЗАМЕНЯЕМ ВСЕГДА
                        table_info[table_field] = new_value
                        replaced_fields.append(table_field)

                        # Логируем все замены
                        logger.info(f"   🔄 ЗАМЕНЕНО: '{table_field}': '{old_value}' → '{new_value}'")

            logger.info(f"   ВСЕГО ЗАМЕНЕНО ПОЛЕЙ: {len(replaced_fields)}")

            # Логируем итоговые данные
            logger.info(f"   ИТОГОВЫЕ ДАННЫЕ:")
            for key, value in table_info.items():
                if value and str(value).strip() and str(value).strip() != 'nan':
                    logger.info(f"     {key}: '{value}'")
        else:
            logger.info(f"   ИСПОЛЬЗУЕМ ОРИГИНАЛЬНЫЕ ДАННЫЕ ИЗ PDF (схожесть: {similarity:.2%})")

        return table_info

    def _enrich_from_filename(self, table_info: Dict, filename: str):
        """Дополняет данные из названия файла"""
        try:
            # Убираем расширение и путь
            clean_name = Path(filename).stem
            logger.info(f"📁 АНАЛИЗ НАЗВАНИЯ ФАЙЛА: {clean_name}")

            if re.search(r'\+?Акт\s+\d{1,2}\.\d{1,2}\.\d{2,4}\s+.{0,10}?[А-ЯЁ][а-яё]*', clean_name):
                # Извлекаем дату (формат: dd.mm.yyyy)
                date_match = re.search(r'(\d{1,2}\.\d{1,2}\.\d{4})', clean_name)
                if date_match:
                    extracted_date = date_match.group(1)
                    year = re.search(r'\d{4}', extracted_date)
                    if year:
                        year = year.group(0)
                    else:
                        year = None
                    current_date = table_info.get('Дата окончания проведения ГИКЭ', '')

                    # Если дата не заполнена или заполнена некорректно
                    if not current_date or str(current_date).strip() in ['', 'nan'] or str(
                            current_date).strip() != extracted_date:
                        table_info['Дата окончания проведения ГИКЭ'] = extracted_date
                        if year:
                            table_info['ГОД'] = year
                        logger.info(f"   📅 ИЗВЛЕЧЕНА ДАТА ИЗ ФАЙЛА: {extracted_date}")

                # Извлекаем фамилию эксперта (после даты, до запятой)
                # Паттерн: дата пробел фамилия запятая
                expert_match = re.search(r'\d{1,2}\.\d{1,2}\.\d{4}\s+([^,]+),', clean_name)
                if expert_match:
                    extracted_expert = expert_match.group(1).strip()
                    current_expert = table_info.get('Эксперт (физ. или юр.лицо)', '')

                    # Если эксперт не заполнен
                    if not current_expert or str(current_expert).strip() in ['', 'nan']:
                        table_info['Эксперт (физ. или юр.лицо)'] = extracted_expert
                        logger.info(f"   👤 ИЗВЛЕЧЕН ЭКСПЕРТ ИЗ ФАЙЛА: {extracted_expert}")

                # Извлекаем место проведения (после запятой, до точки или конца)
                location_match = re.search(r',\s*(.+?)(?:\.pdf|\.kmz|$)', clean_name)
                if location_match:
                    extracted_location = location_match.group(1).strip()
                    current_location = table_info.get('Место проведения экспертизы', '')

                    # Если место не заполнено
                    if not current_location or str(current_location).strip() in ['', 'nan']:
                        table_info['Место проведения экспертизы'] = extracted_location
                        logger.info(f"   📍 ИЗВЛЕЧЕНО МЕСТО ИЗ ФАЙЛА: {extracted_location}")

                # Извлекаем тип ГИКЭ по ключевым словам
                if not table_info.get('Вид ГИКЭ', '').strip():
                    if 'ЗУ' in clean_name.upper():
                        table_info['Вид ГИКЭ'] = 'ЗУ'
                        logger.info(f"   🏷️ ОПРЕДЕЛЕН ВИД ГИКЭ: ЗУ")
                    elif 'НПД' in clean_name.upper():
                        table_info['Вид ГИКЭ'] = 'НПД'
                        logger.info(f"   🏷️ ОПРЕДЕЛЕН ВИД ГИКЭ: НПД")
                    elif 'док-я' in clean_name.lower():
                        table_info['Вид ГИКЭ'] = 'Док-я'
                        logger.info(f"   🏷️ ОПРЕДЕЛЕН ВИД ГИКЭ: Док-я")
                    elif 'границы' in clean_name.lower():
                        table_info['Вид ГИКЭ'] = 'Границы'
                        logger.info(f"   🏷️ ОПРЕДЕЛЕН ВИД ГИКЭ: Границы")

        except Exception as e:
            logger.warning(f"Ошибка при извлечении данных из названия файла: {e}")
