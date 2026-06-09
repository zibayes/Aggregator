import math
import re
import regex
import pdfplumber

act_parts = ['Акт', r'(\d\.\s*)?Дата начала\s*(проведения)?\s*(экспертизы)?[\s:\-–-]*',
             r'(\d\.\s*)?Дата окончания\s*(проведения)?\s*(экспертизы)?[\s:\-–-]*',  # проведения экспертизы
             r'(\d\.\s*)?Место проведения (экспертизы)?[\s:\-–-]*',
             r'(\d\.\s*)?Заказчик экспертизы[\s:\-–-]*',
             r'(\d\.\s*)?(Сведения об)? эксперт[еах]+[\s:\-–-]*',
             r'(\d\.\s*)?Отношени[яе]+ к заказчику', r'(\d\.\s*)?Цель экспертизы[\s:\-–-]*',
             r'(\d\.\s*)?Объект .*?(экспертизы)?[\s:\-–-]*',  # Объект экспертизы:*
             r'Перечень документов, представленных\s*(на)?\s*(экспертизу)?[\s:\-–-]*',
             r'Сведения о проведенных исследованиях',
             r'Факты и сведения, выявленные .*\n*.*исследований',
             # 'Факты и сведения, выявленные и установленные в результате проведенных исследований', 'Координаты',
             r'Перечень[а-яА-ЯёЁ \n,]*литературы',
             # 'Перечень документов и материалов, собранных и полученных при проведении '
             #              'экспертизы, а также использованной для нее специальной, технической и '
             #              'справочной литературы', 'Обоснования вывода экспертизы',
             'Вывод экспертизы', 'Перечень приложений']
act_sub_parts = ['Характеристика объекта']
act_parts_info = {i: '' for i in act_parts}
object_info = ''
place_info = ''
table_columns = ['ГОД', 'Дата окончания проведения ГИКЭ', 'Вид ГИКЭ',
                 'Номер (если имеется) и наименование Акта ГИКЭ',
                 'Место проведения экспертизы',  # 'Муниципальный район или муниципальный округ'
                 'Заказчик работ (*если не указан, то заказчик экспертизы)',
                 'Площадь, протяжённость и/или др. параменты объекта', 'Эксперт (физ. или юр.лицо)',
                 'Исполнитель полевых работ (юр. лицо)', 'ОЛ', 'Заключение. Выявленые объекты.',
                 'Объекты расположенные в непосредственной близости. Для границ']
months = {'января': '01', 'февраля': '02', 'марта': '03', 'апреля': '04', 'мая': '05', 'июня': '06',
          'июля': '07',
          'августа': '08', 'сентября': '09', 'октября': '10', 'ноября': '11', 'декабря': '12', }

RE_ACT_HEADER = re.compile(r'А\s*К\s*Т *(?!.*государственной)№? *[\S\d\/\-– ]*',
                           re.I)  # А *К *Т *№* *\d*/*\d*(?!.*подписан).*
RE_ACT_SECTION = re.compile(r'Акт', re.I)
RE_ACT_NAST = re.compile(r'Настоящий Акт', re.I)
RE_ACT_OBJECT = re.compile(r'«[\s\S]+?»', re.I)


def extract_act_name(text, current_section_idx, text_file, page_number, table_info, exploration_object):
    act = RE_ACT_HEADER.search(text)
    # А *К *Т *№* *\d*/*\d*\n*(?!.*подписан).*\n*.*
    # А *К *Т № \d+/*\d*\n*.*
    text_to_write = ''
    if act:
        text_to_write = act.group(0)
        obj = RE_ACT_OBJECT.search(text)
        if obj:
            exploration_object = True
            text_to_write += obj.group(0)
    else:
        start = RE_ACT_SECTION.search(text)
        end = RE_ACT_NAST.search(text)
        if start and end:
            text_to_write = text[start.start():end.start()]
    text_file.write(
        f"--- АКТ --- (стр. {page_number + 1}):\n{text_to_write}\n")
    current_section_idx += 1
    if '№' not in text_to_write:
        text_to_write += " б/н"
    table_info['Номер (если имеется) и наименование Акта ГИКЭ'] = text_to_write
    return current_section_idx, exploration_object


FULL_TIME_INTERVAL_PATTERN_VAR_1 = re.compile(r'период с \d{2}.\d{2}.\d{4}\s+[г.\s]*по\s+(\d{2}.\d{2}.\d{4})\s*[г\.]*',
                                              re.IGNORECASE)
FULL_TIME_INTERVAL_PATTERN_VAR_2 = re.compile(
    r'период с «*\d+»* [А-Яа-яёЁ]+ \d+ г\.*.*\s+по\s+(«*\d+»*\s*[А-Яа-яёЁ]+\s*\d+)[\sг\.]*', re.IGNORECASE)


def extract_start_date(text_to_write):
    full_time_interval = FULL_TIME_INTERVAL_PATTERN_VAR_1.search(text_to_write)
    # период с \d+.\d+.\d+\s+г.\s+по\s+\d+.\d+.\d+\s+г.
    if not full_time_interval:
        full_time_interval = FULL_TIME_INTERVAL_PATTERN_VAR_2.search(text_to_write)
        interval_type = 'words'
    else:
        interval_type = 'dots'
    return full_time_interval, interval_type


DATE_DOTS_PATTERN = re.compile(r'\d+\s*\d+\s*\.\d{2}\s*\d*\.\d{4}\s*\d* *г*', re.IGNORECASE)
DATE_WORDS2_PATTERN = re.compile(r'«?\d+»?\s*[А-Яа-яёЁ]+\s*\d+\s*г\.*', re.IGNORECASE)
MONTH_PATTERN = re.compile(r'[а-яА-ЯёЁ]+')
YEAR_PATTERN = re.compile(r'(\d+)\s*г\.*', re.IGNORECASE)
DATE_WORDS_PATTERN = re.compile(r'«*\d+»*\s*[А-Яа-яёЁ]+\s*\d+\s*г\.*', re.IGNORECASE)


def extract_end_date(text, pattern, text_to_write, full_time_interval, interval_type, current_part, table_info):
    is_continue = False
    start_date = pattern.search(text)  # Дата начала
    if start_date:
        text_to_write = text[start_date.end():]
    if full_time_interval and interval_type == 'dots':
        date = full_time_interval
        current_part += 2
        if date:
            date = date.group(1)
    else:
        date = DATE_DOTS_PATTERN.findall(text_to_write)
        if date:
            if len(date) > 1:
                date = date[1]
            else:
                date = date[0]
        date_words = DATE_WORDS_PATTERN.findall(text_to_write)  # TODO: rework?
        if date_words:
            if len(date_words) > 1:
                date_words = date_words[1]
            else:
                date_words = date_words[0]
        if date and date_words and (text_to_write.find(date) > text_to_write.find(
                date_words) or 'Постнов' in text_to_write):  # TODO: people style?
            date = None
    if date and interval_type != 'words':
        date = date.replace('по ', '').replace(' ', '')
        year = date[date.rfind('.') + 1:]
        if 'г' in year:
            year = year[:year.rfind('г')]
        table_info['ГОД'] = year
        index = date.rfind(' ')
        table_info['Дата окончания проведения ГИКЭ'] = date[
                                                       :index if index != -1 else len(
                                                           date)].replace(
            'г', '')
        if full_time_interval:
            is_continue = True
    else:
        date = FULL_TIME_INTERVAL_PATTERN_VAR_2.search(text_to_write)
        if date:
            current_part += 2
            text_to_write = date.group(1)

        year = YEAR_PATTERN.search(text_to_write)
        if year:
            year = year.group(1)
        elif interval_type != 'words':
            text_to_write = text
            year = YEAR_PATTERN.search(text_to_write)
            if year:
                year = year.group(1)
        else:
            year = YEAR_PATTERN.search(text_to_write)
            if year:
                year = year.group(1)
        table_info['ГОД'] = year
        date = DATE_WORDS2_PATTERN.findall(text_to_write)
        if date:
            if len(date) > 1:
                date = date[1]
            else:
                date = date[0]
        else:
            date = DATE_WORDS_PATTERN.findall(text, re.IGNORECASE)
            if len(date) > 1:
                date = date[1].replace('  ', ' ')
            elif len(date) > 0:
                date = date[0].replace('  ', ' ')
            else:
                return current_part, is_continue
        date = date.replace('«', '').replace('»', '')
        date = date[:date.rfind(' ')]
        month = MONTH_PATTERN.search(date)
        if month:
            month = month.group(0)
        else:
            month = ''
        date = date.replace(month, '').replace('  ', '.' + months[month] + '.')
        day = date[:date.find('.')]
        if len(day) < 2:
            date = '0' + date
        table_info['Дата окончания проведения ГИКЭ'] = date
        if full_time_interval:
            is_continue = True
        else:
            pass
    return current_part, is_continue


DATE_PATTERN = re.compile(r'«*\d+»*\s+[А-Яа-яёЁ]+\s+\d+ г\.* *\n.[^0-9]+\n', re.IGNORECASE)
NEWLINE_PATTERN = re.compile(r'\n.[^0-9]+?(?=\n)', re.IGNORECASE)


def extract_place_info(place_info, text, text_to_write, table_info, broken_structure):
    place_info += text_to_write
    if not text_to_write.strip() or DATE_PATTERN.search(text_to_write):
        text_to_write = DATE_PATTERN.search(text)
        if text_to_write:
            text_to_write = text_to_write.group(0)
            text_to_write = NEWLINE_PATTERN.search(text_to_write)
            if text_to_write:
                text_to_write = text_to_write.group(0)
                broken_structure = True
        if not text_to_write:
            text_to_write = ''
    table_info['Место проведения экспертизы'] = text_to_write.replace('–', '').replace(':',
                                                                                       '').replace(
        '\n', '')
    return broken_structure, place_info


PATTERN_CUSTOMER_END1 = re.compile(r'Фамилия,\s*имя[,и\s]*отчество.*(эксперта)?', re.IGNORECASE)
PATTERN_CUSTOMER_END2 = re.compile(r'[А-ЯЁ][а-яё]+ [А-ЯЁ][а-яё]+ [А-ЯЁ][а-яё]+')
PATTERN_CUSTOMER_END3 = re.compile(r'[А-ЯЁ]\.\s*[А-ЯЁ]\. [А-ЯЁ][а-яё]+')
PATTERN_CUSTOMER_END4 = re.compile(r'[А-ЯЁ][а-яё]+ [А-ЯЁ]\.\s*[А-ЯЁ]\.')


def extract_customer(broken_structure, pattern, table_info, text, text_to_write):
    if broken_structure:
        start = re.search(
            table_info['Место проведения экспертизы'],
            text,
            re.IGNORECASE)
        if not start:
            return
        cropped_text = text[start.end():]
        end = pattern.search(cropped_text)
        if not end or end.start():
            end = PATTERN_CUSTOMER_END1.search(cropped_text)
        if not end or end.start():
            end = PATTERN_CUSTOMER_END2.search(cropped_text)
            if not end:
                end = PATTERN_CUSTOMER_END3.search(cropped_text)
            if not end:
                end = PATTERN_CUSTOMER_END4.search(cropped_text)
        if start and end:
            text_to_write = cropped_text[:end.start()].strip()
        else:
            text_to_write = ''
    table_info[
        'Заказчик работ (*если не указан, то заказчик экспертизы)'] = text_to_write.replace(
        '–',
        '').replace(
        ':', '')


RE_EXPERT_MULTI_START = re.compile(r'Эксперты,\s+состоящие\s+в\s+трудовых', re.IGNORECASE)
RE_EXPERT_SHORT_NAME = re.compile(r'[А-ЯЁ]+[а-яё]+\s+[А-Яа-яёЁ]+\.\s*[А-Яа-яёЁ]+\.\s+-*–*\s*образование')
RE_EXPERT_FULL_NAME = re.compile(r'[А-ЯЁ]+[а-яё]+\s+[А-ЯЁ]+[а-яё]+\s+[А-ЯЁ]+[а-яё]+\s+-*–*\s*образование')
RE_EXPERT_FIO_TEMPLATE = re.compile(r'Фамилия,\s*имя[,и\s]*отчество.*(эксперта)?.*\n.*\n', re.IGNORECASE)
RE_EXPERT_NAME_BEFORE_VYSSHEE = re.compile(r'[А-Яа-яёЁ]+\s*[А-Яа-яёЁ]+\s*[А-Яа-яёЁ]+\s*?(?=\nвысшее)', re.IGNORECASE)
RE_EXPERT_FIO_PREFIX = re.compile(r'Фамилия,\s*имя[,и\s]*отчество.?[эксперта]*:*', re.IGNORECASE)
RE_EXPERT_NAME_BEFORE_SEMICOLON = re.compile(r'[А-Яа-яёЁ]+\s+[А-Яа-яёЁ]+\s+[А-Яа-яёЁ]+\s*?(?=;)', re.IGNORECASE)
RE_EXPERT_NAME_BEFORE_OBRAZ = re.compile(r'[А-Яа-яёЁ]+\s+[А-Яа-яёЁ]+\s+[А-Яа-яёЁ]+\s*?(?=Образование)', re.IGNORECASE)
RE_EXPERT_FIO_SHORT = re.compile(r'ФИО эксперта.*\n.*\n', re.IGNORECASE)
RE_EXPERT_FIO_SHORT_PREFIX = re.compile(r'ФИО эксперта.*\n', re.IGNORECASE)
RE_EXPERT_NAME_BEFORE_COMMA_EDU = re.compile(r'[А-Яа-яёЁ]+\s*[А-Яа-яёЁ]+\s*[А-Яа-яёЁ]+\s*?(?=, образование)',
                                             re.IGNORECASE)


def extract_expert(text_to_write, several_experts, full_name, table_info, pdf, page_number):
    if RE_EXPERT_MULTI_START.search(text_to_write) or several_experts:
        names = []
        if not full_name:
            names = RE_EXPERT_SHORT_NAME.findall(text_to_write)
        if not names or several_experts and full_name:
            names = RE_EXPERT_FULL_NAME.findall(text_to_write)
            full_name = True
        if names:
            names = list(
                map(lambda x: x.replace('\n', '').replace(' образование', '').replace(' -',
                                                                                      '').replace(
                    ' –', ''), names))
            if several_experts:
                table_info['Эксперт (физ. или юр.лицо)'] += ',\n' + ',\n'.join(names)
            else:
                table_info['Эксперт (физ. или юр.лицо)'] = ',\n'.join(names)
        several_experts = True
    else:
        name = RE_EXPERT_FIO_TEMPLATE.search(text_to_write)
        if name:
            name = name.group(0)
            if 'Образование' in name and 'высшее' not in name:
                name = RE_EXPERT_NAME_BEFORE_VYSSHEE.search(text_to_write)
                if name:
                    name = name.group(0)
                    broken_structure = True
            else:
                name = name[RE_EXPERT_FIO_PREFIX.search(name).end():].replace('\n', '')
                if 'образование' in name.lower():
                    find_name = RE_EXPERT_NAME_BEFORE_SEMICOLON.search(name)
                    if not find_name:
                        name = RE_EXPERT_NAME_BEFORE_OBRAZ.search(name)
                        if name:
                            name = name.group(0)
                    else:
                        name = find_name.group(0)
            table_info['Эксперт (физ. или юр.лицо)'] = name
        else:
            name = RE_EXPERT_FIO_SHORT.search(text_to_write)
            if name:
                name = name.group(0)
                name = name[RE_EXPERT_FIO_SHORT_PREFIX.search(name).end():].replace('\n', '')
                table_info['Эксперт (физ. или юр.лицо)'] = name
            else:
                name = RE_EXPERT_NAME_BEFORE_COMMA_EDU.search(text_to_write)
                if name:
                    name = name.group(0)
                    table_info['Эксперт (физ. или юр.лицо)'] = name
                else:
                    page_tables = pdf.pages[page_number].extract_tables()
                    if page_tables and len(page_tables[0]) >= 5 and page_tables[0][4][
                        0] == 'ФИО эксперта':
                        table_info['Эксперт (физ. или юр.лицо)'] = page_tables[0][4][1]
    return several_experts, full_name


RE_OBJECT_ZEMLI = re.compile(r'земли', re.IGNORECASE)
RE_OBJECT_ZEMELNY = re.compile(r'земельны', re.IGNORECASE)
RE_OBJECT_RAZDEL = re.compile(r'раздел', re.IGNORECASE)
RE_OBJECT_DOC = re.compile(r'документация', re.IGNORECASE)
# Паттерн для поиска объекта в кавычках до цифры с точкой
RE_OBJECT_QUOTES_TILL_NUM = re.compile(r'«[/\\А-Яа-яёЁa-zA-Z \n,.0-9:«»-–-()#№+]+?(?=\n\d\.)', re.IGNORECASE)
# Паттерн для поиска объекта в кавычках без ограничения
RE_OBJECT_QUOTES_GREEDY = re.compile(r'«[/\\А-Яа-яёЁa-zA-Z \n,.0-9:«»-–-()#№+]+', re.IGNORECASE)


def extract_object(object_info, exploration_object, text, text_to_write, table_info, SQUARE_RESERVE):
    object_info += text_to_write
    if RE_OBJECT_ZEMLI.search(text_to_write) or RE_OBJECT_ZEMELNY.search(text_to_write):
        table_info['Вид ГИКЭ'] = 'ЗУ'
    elif RE_OBJECT_RAZDEL.search(text_to_write):
        table_info['Вид ГИКЭ'] = 'НПД'
    elif RE_OBJECT_DOC.search(text_to_write):
        table_info['Вид ГИКЭ'] = 'Док-я'
    else:
        text_to_write = text
        if RE_OBJECT_ZEMLI.search(text) or RE_OBJECT_ZEMELNY.search(text):
            table_info['Вид ГИКЭ'] = 'ЗУ'
        elif RE_OBJECT_RAZDEL.search(text):
            table_info['Вид ГИКЭ'] = 'НПД'
        elif RE_OBJECT_DOC.search(text):
            table_info['Вид ГИКЭ'] = 'Док-я'
    get_gike_object_size(text_to_write, table_info, SQUARE_RESERVE)
    exp_object = RE_OBJECT_QUOTES_TILL_NUM.search(text_to_write)
    if not exp_object:
        exp_object = RE_OBJECT_QUOTES_GREEDY.search(text_to_write)
    if exp_object and 'Номер (если имеется) и наименование Акта ГИКЭ' in table_info and not exploration_object:
        table_info['Номер (если имеется) и наименование Акта ГИКЭ'] += ' ' + exp_object.group(0)
        exploration_object = True
    return object_info, exploration_object


RE_SQUARE_OBSCHEE = re.compile(r'Общ.+\s+площадь\s*.*\s*\d* *\d+[,\.]*\d*\s+[га]*[кв. м]*', re.IGNORECASE)
RE_SQUARE_PLAIN = re.compile(r'площадь\s*\S*\s*(составляет)?\s*.*\s*\d* *\d+[,\.]*\d*\s+[га]*[кв. м]*', re.IGNORECASE)
RE_SQUARE_VALUE = re.compile(r'\d* *\d+[,\.]*\d*\s+[га]*[кв. м]*', re.IGNORECASE)
RE_SQUARE_HAS_UNITS = re.compile(r'[А-Яа-я.]+', re.IGNORECASE)  # для проверки наличия букв
RE_LENGTH = re.compile(r'протяж.*\d* *\d+[,]*\d*\s+[а-яА-ЯёЁ]+', re.IGNORECASE)
RE_LENGTH_VALUE = re.compile(r'\d* *\d+[,]*\d*\s+[а-яА-ЯёЁ]+', re.IGNORECASE)
RE_SQUARE_LINE = re.compile(r'площ[а-яА-ЯёЁ]+\s+лин.*\d* *\d+[,]*\d*\s+[а-яА-ЯёЁ]+', re.IGNORECASE)


def get_gike_object_size(text_to_write: str, table_info: dict, SQUARE_RESERVE: list) -> None:
    attr_filled = 'Площадь, протяжённость и/или др. параменты объекта' in table_info.keys()
    if not attr_filled or attr_filled and 'Общ. S' not in table_info[
        'Площадь, протяжённость и/или др. параменты объекта']:
        square = RE_SQUARE_OBSCHEE.search(text_to_write)
        if not square:
            square = RE_SQUARE_PLAIN.search(text_to_write)
        if square:
            square = RE_SQUARE_VALUE.search(square.group(0)).group(0)
            if 'га ' in square:
                square = square.strip()[:square.rfind('га ') + 2]
            if 'кв. м' in square or not RE_SQUARE_HAS_UNITS.search(square):
                SQUARE_RESERVE.append(square)
            else:
                table_info['Площадь, протяжённость и/или др. параменты объекта'] = 'Общ. S = ' + square
    if not attr_filled or attr_filled and 'протяж.' not in table_info[
        'Площадь, протяжённость и/или др. параменты объекта']:
        length = RE_LENGTH.search(text_to_write)
        if length:
            length = RE_LENGTH_VALUE.search(length.group(0)).group(0)
            if 'Площадь, протяжённость и/или др. параменты объекта' not in table_info.keys():
                table_info['Площадь, протяжённость и/или др. параменты объекта'] = 'протяж. ' + length
            else:
                table_info[
                    'Площадь, протяжённость и/или др. параменты объекта'] += '\nпротяж. ' + length
    if not attr_filled or attr_filled and 'S лин.' not in table_info[
        'Площадь, протяжённость и/или др. параменты объекта']:
        square_line = RE_SQUARE_LINE.search(text_to_write)
        if square_line:
            square_line = RE_LENGTH_VALUE.search(square_line.group(0)).group(0)
            table_info['Площадь, протяжённость и/или др. параменты объекта'] += ' (S лин. ЗУ = ' + square_line + ')'


RE_EXP_FACTS_OBJECT = re.compile(r'«[/\\А-Яа-яёЁa-zA-Z \n,.0-9:«»-–-()#№+]+?(?=Краткая\s+физико-географическая)',
                                 re.IGNORECASE)
RE_SECTORS_START = re.compile(r'Участок\s+№\d+', re.IGNORECASE)
RE_SECTORS_BLOCK = re.compile(r'Участок\s+№\d+[А-Яа-яёЁA-Za-z \n,.0-9:;"/()«»\\–-]+Документация', re.IGNORECASE)
RE_SECTOR_AREA = re.compile(r'площадь\s*.*\s*\d* *\d+[,]*\d*\s+[га]*[кв. м]*', re.IGNORECASE)
RE_SECTOR_NUMBER = re.compile(r'\d+[,]*\d*', re.IGNORECASE)
RE_TOTAL_SQUARE = re.compile(r'\d+[,]*\d*', re.IGNORECASE)
RE_PERSPECTIVE = re.compile(
    r'перспект[А-Яа-яёЁA-Za-z \n,.0-9:;"()«»\\–-]+?площадь\s*.*\s*\d* *\d+[,]*\d*\s+[га]*[кв. м]*', re.IGNORECASE)
RE_NON_PERSPECTIVE = re.compile(
    r'неперспект[А-Яа-яёЁA-Za-z \n,.0-9:;"()«»\\–-]+?площадь\s*.*\s*\d* *\d+[,]*\d*\s+[га]*[кв. м]*', re.IGNORECASE)
RE_SMALL_PERSPECTIVE = re.compile(
    r'малоперспект[А-Яа-яёЁA-Za-z \n,.0-9:;"()«»\\–-]+?площадь\s*.*\s*\d* *\d+[,]*\d*\s+[га]*[кв. м]*', re.IGNORECASE)
RE_VALUE_UNIT = re.compile(r'\d* *\d+[,]*\d*\s+[а-яА-ЯёЁ]+', re.IGNORECASE)
RE_SQUARE_OBJECT = re.compile(r'Площадной\s+объект', re.IGNORECASE)
RE_LINE_OBJECT = re.compile(r'Линейный\s+объект', re.IGNORECASE)
RE_SQUARE_OBJECT_BLOCK = re.compile(
    r'Площадной\s+объект[А-Яа-яёЁA-Za-z№# \n,.0-9:;"()«»\\/–-]+?площадь\s*.*\s*\d* *\d+[,]*\d*\s+[га]*[кв. м]*',
    re.IGNORECASE)
RE_LINE_OBJECT_BLOCK = re.compile(
    r'Линейный\s+объект[А-Яа-яёЁA-Za-z№# \n,.0-9:;"()«»\\/–-]+?площадь\s*.*\s*\d* *\d+[,]*\d*\s+[га]*[кв. м]*',
    re.IGNORECASE)
RE_AREA_VALUE = re.compile(r'площадь\s*.*\s*\d* *\d+[,]*\d*\s+[а-яА-ЯёЁ]+', re.IGNORECASE)


def extract_exp_facts(exploration_object, text_to_write, text, table_info, SQUARE_RESERVE, sectors_square,
                      text_reserve):
    if not exploration_object:
        exp_object = RE_EXP_FACTS_OBJECT.search(text_to_write)
        if exp_object:
            table_info[
                'Номер (если имеется) и наименование Акта ГИКЭ'] += ' ' + exp_object.group(0)
    get_gike_object_size(text_to_write, table_info, SQUARE_RESERVE)
    sectors = RE_SECTORS_START.search(text)
    if sectors and 'Площадь, протяжённость и/или др. параменты объекта' in table_info.keys():
        sectors = RE_SECTORS_BLOCK.findall(text)
        for sector in sectors:
            sector = RE_SECTOR_AREA.search(sector)
            if sector:
                sector = RE_SECTOR_NUMBER.search(sector.group(0))
                if sector:
                    sector = sector.group(0)
                    sectors_square.append(sector)
        total_square = RE_TOTAL_SQUARE.search(
            table_info['Площадь, протяжённость и/или др. параменты объекта'])
        if total_square:
            total_square = float(total_square.group(0).replace(',', '.'))
        if total_square and math.isclose(total_square,
                                         sum([float(i.replace(',', '.')) for i in
                                              sectors_square])):
            sectors_len = len(sectors_square)
            table_info[
                'Площадь, протяжённость и/или др. параменты объекта'] += ': всего ' + str(
                sectors_len) + ' уч-в - '
            for i in range(sectors_len):
                if i < sectors_len - 1:
                    table_info['Площадь, протяжённость и/или др. параменты объекта'] += str(
                        sectors_square[i]).replace('.', ',') + ' + '
                else:
                    table_info['Площадь, протяжённость и/или др. параменты объекта'] += str(
                        sectors_square[i]).replace('.', ',')
                    if 'га' in table_info['Площадь, протяжённость и/или др. параменты объекта']:
                        table_info[
                            'Площадь, протяжённость и/или др. параменты объекта'] += ' га'
                    elif 'кв. м' in table_info[
                        'Площадь, протяжённость и/или др. параменты объекта']:
                        table_info[
                            'Площадь, протяжённость и/или др. параменты объекта'] += 'кв. м'
    if 'Площадь, протяжённость и/или др. параменты объекта' in table_info.keys():
        perspective = RE_PERSPECTIVE.search(text)
        if perspective:
            enter_reserve = False
            non_perspective = None
            small_perspective = None
            if text_reserve:
                text_reserve += text
                text = text_reserve.replace(
                    '--- Факты и сведения, выявленные .*\n*.*исследований --- ', '')
                text_reserve = None
                enter_reserve = True
            else:
                non_perspective = RE_NON_PERSPECTIVE.search(text)
                small_perspective = RE_SMALL_PERSPECTIVE.search(text)
                if non_perspective and not small_perspective or not non_perspective and small_perspective:
                    text_reserve = text
            if non_perspective and small_perspective or enter_reserve:
                if non_perspective and 'неперспект' not in table_info[
                    'Площадь, протяжённость и/или др. параменты объекта']:
                    non_perspective = RE_NON_PERSPECTIVE.search(text)
                    non_perspective = RE_VALUE_UNIT.search(non_perspective.group(0))
                    if non_perspective:
                        non_perspective = non_perspective.group(0)
                    if 'из них' not in table_info[
                        'Площадь, протяжённость и/или др. параменты объекта']:
                        table_info[
                            'Площадь, протяжённость и/или др. параменты объекта'] += ' (из них к неперспект. отнесено ' + non_perspective + ', '
                    else:
                        table_info[
                            'Площадь, протяжённость и/или др. параменты объекта'] += ' к неперспект. - ' + non_perspective + ')'

                if small_perspective and 'малоперсп' not in table_info[
                    'Площадь, протяжённость и/или др. параменты объекта']:
                    small_perspective = RE_SMALL_PERSPECTIVE.search(text)
                    small_perspective = RE_VALUE_UNIT.search(small_perspective.group(0))
                    if small_perspective:
                        small_perspective = small_perspective.group(0)
                    if 'из них' not in table_info[
                        'Площадь, протяжённость и/или др. параменты объекта']:
                        table_info[
                            'Площадь, протяжённость и/или др. параменты объекта'] += ' (из них к малоперсп. отнесено ' + small_perspective + ', '
                    else:
                        table_info[
                            'Площадь, протяжённость и/или др. параменты объекта'] += ' к малоперсп. - ' + small_perspective + ')'
        if 'из них' not in table_info['Площадь, протяжённость и/или др. параменты объекта']:
            enter_reserve = False
            square_object = None
            line_object = None
            if text_reserve:
                text_reserve += text
                text = text_reserve.replace(
                    '--- Факты и сведения, выявленные .*\n*.*исследований --- ',
                    '')
                text_reserve = None
                enter_reserve = True
            else:
                square_object = RE_SQUARE_OBJECT.search(text)
                line_object = RE_LINE_OBJECT.search(text)
                if square_object and not line_object or not square_object and line_object:
                    text_reserve = text
            if enter_reserve or line_object and square_object:
                square_object = RE_SQUARE_OBJECT_BLOCK.search(text)
                line_object = RE_LINE_OBJECT_BLOCK.search(text)
                if square_object and line_object:
                    if 'площ.' not in table_info[
                        'Площадь, протяжённость и/или др. параменты объекта']:
                        square_object = RE_AREA_VALUE.search(square_object.group(0))
                        if square_object:
                            square_object = square_object.group(0)
                            square_object = RE_VALUE_UNIT.search(square_object)
                            if square_object:
                                square_object = square_object.group(0)
                        if 'лин.' not in table_info[
                            'Площадь, протяжённость и/или др. параменты объекта']:
                            table_info[
                                'Площадь, протяжённость и/или др. параменты объекта'] += ' (площ. об. =  ' + square_object + '; '
                        else:
                            table_info[
                                'Площадь, протяжённость и/или др. параменты объекта'] += 'площ. об. = ' + square_object + ')'
                    if 'лин.' not in table_info[
                        'Площадь, протяжённость и/или др. параменты объекта']:
                        line_object = RE_AREA_VALUE.search(line_object.group(0))
                        if line_object:
                            line_object = line_object.group(0)
                            line_object = RE_VALUE_UNIT.search(line_object)
                            if line_object:
                                line_object = line_object.group(0)
                        if 'площ.' not in table_info[
                            'Площадь, протяжённость и/или др. параменты объекта']:
                            table_info[
                                'Площадь, протяжённость и/или др. параменты объекта'] += ' (лин. об. = ' + line_object + '; '
                        else:
                            table_info[
                                'Площадь, протяжённость и/или др. параменты объекта'] += 'лин. об. = ' + line_object + ')'

        table_info['Площадь, протяжённость и/или др. параменты объекта'] = table_info[
            'Площадь, протяжённость и/или др. параменты объекта'].replace('  ', ' ')
    return text_reserve


CONCLUSION_PATTERN = regex.compile(r"(\(\S+ельное\s+заключение){e<=3}\)")  # r'\(\S+ельное\s+заключение\)'
RE_CONCLUSION_SIMPLE = re.compile(r'\(\S+ельное\s+заключение\)', re.IGNORECASE)
RE_CONCLUSION_EXPERT = re.compile(r'Заключение\s*экспертизы\s*.+', re.IGNORECASE)


def extract_conclusion(text_to_write, table_info, voan_reserve):
    conclusion = RE_CONCLUSION_SIMPLE.search(text_to_write)
    if conclusion:
        table_info['Заключение. Выявленые объекты.'] = conclusion.group(0).replace('(',
                                                                                   '').replace(
            ')',
            '')
    else:
        conclusion = CONCLUSION_PATTERN.search(text_to_write, regex.IGNORECASE | regex.UNICODE)
        if conclusion:
            table_info['Заключение. Выявленые объекты.'] = conclusion.group(0).replace('(',
                                                                                       '').replace(
                ')',
                '')
        else:
            conclusion = RE_CONCLUSION_EXPERT.search(text_to_write)
            if conclusion:
                conclusion = conclusion.group(0)
                if 'положит' in conclusion.lower() or 'отриц' in conclusion.lower():
                    table_info['Заключение. Выявленые объекты.'] = conclusion.replace('.',
                                                                                      '').replace(
                        'Заключение экспертизы ', '') + ' заключение'
                if voan_reserve and 'ВОАН' not in table_info[
                    'Заключение. Выявленые объекты.'] and \
                        'отрицательное' in table_info['Заключение. Выявленые объекты.'].lower():
                    table_info['Заключение. Выявленые объекты.'] += voan_reserve


RE_OPENLIST_TYPE1 = re.compile(
    r'Министерство\s+культуры\s+Российской\s+Федерации\s+Настоящий\s+открытый\s+лист\s+выдан', re.IGNORECASE)
RE_OPENLIST_HOLDER = re.compile(r'На\s+основании\s+открытого\s+листа\s+([А-Яа-яёЁ]+\s[А-Яа-яёЁ]+\s[А-Яа-яёЁ]+)',
                                re.IGNORECASE)
RE_OPENLIST_NUMBER = re.compile(r'№\s*\S*[:\-–-]*\d+', re.IGNORECASE)
RE_OPENLIST_DATE_WORDS = re.compile(r'«*\d+»* [А-Яа-яёЁ]+ \d{4}', re.IGNORECASE)
RE_OPENLIST_MONTH = re.compile(r'[а-яА-ЯёЁ]+')
RE_OPENLIST_TYPE2 = re.compile(
    r'[А-Яа-яёЁ]+\.*\s*[А-Яа-яёЁ]+\.*\s+[А-ЯЁ]+[а-яё]+\s*.*\s*Открыт.*\s*лист.*\s*[а-яА-ЯёЁ \n0-9.]*№\s*\S*[:\-–-]*\d+[а-яА-ЯёЁ \n\d.,(-«»]*',
    re.IGNORECASE)
RE_OPENLIST_TYPE3 = re.compile(
    r'[А-ЯЁ]+[а-яё]+\s+[А-Яа-яёЁ]+\.*\s*[А-Яа-яёЁ]+\.*\s*.*\s*Открыт.*\s*лист.*\s*[а-яА-ЯёЁ \n0-9.]*№\s*\S*[:\-–-]*\d+[а-яА-ЯёЁ \n\d.,(-«»]*',
    re.IGNORECASE)
RE_OPENLIST_TYPE4 = re.compile(r'Открытый\s*лист\s*[а-яА-ЯёЁ \n0-9.]*№\s*\S*[:\-–-]*\d+[а-яА-ЯёЁ \n\d.,(-«»]*?(?=Прил)',
                               re.IGNORECASE)
RE_OPENLIST_TYPE5 = re.compile(r'Открыт.*\s*лист.*\s*[а-яА-ЯёЁ \n0-9.]*№\s*\S*[:\-–-]*\d+[а-яА-ЯёЁ \n\d.,(-«»]*',
                               re.IGNORECASE)
RE_OPENLIST_HOLDER2 = re.compile(r'[А-ЯЁ]+[а-яё]+\s+[А-Яа-яёЁ]+\.\s*[А-Яа-яёЁ]+\.')
RE_OPENLIST_HOLDER3 = re.compile(r'[А-Яа-яёЁ]+\.\s*[А-Яа-яёЁ]+\.\s+[А-ЯЁ]+[а-яё]+')
RE_OPENLIST_HOLDER4 = re.compile(r'[А-ЯЁ]+[а-яё]+\s+[А-ЯЁ]+[а-яё]+\s+[А-ЯЁ]+[а-яё]+')
RE_OPENLIST_DATE_DOT = re.compile(r'\d{2}\.\d{2}\.\d{4}', re.IGNORECASE)


def extract_open_list(text_to_write, table_info):
    open_list = RE_OPENLIST_TYPE1.search(text_to_write)
    if open_list:
        list_holder = RE_OPENLIST_HOLDER.search(text_to_write)
        if list_holder:
            list_holder = list_holder.group(1)
        else:
            list_holder = ''
        list_number = RE_OPENLIST_NUMBER.search(text_to_write)
        if list_number:
            list_number = ' ' + list_number.group(0).strip()
        else:
            list_number = ''
        list_dates = RE_OPENLIST_DATE_WORDS.findall(text_to_write)
        print(f'list_dates = {list_dates}')
        list_dates_corrected = []
        months_global = months  # предполагается, что months определён выше
        for list_date in list_dates:
            list_date = list_date.replace('«', '').replace('»', '')
            list_month = RE_OPENLIST_MONTH.search(list_date)
            if list_month:
                list_month = list_month.group(0)
            list_date = list_date.replace(list_month, '').replace('  ',
                                                                  '.' + months_global[
                                                                      list_month] + '.')
            list_day = list_date[:list_date.find('.')]
            if len(list_day) < 2:
                list_date = '0' + list_date
            list_dates_corrected.append(list_date)
        list_date = last_date = ''
        print(f'list_dates_corrected = {list_dates_corrected}')
        if len(list_dates_corrected) > 0:
            if len(list_dates_corrected) > 1:
                if [int(x) for x in list_dates_corrected[0].split('.')[::-1]] > [int(x) for x in
                                                                                 list_dates_corrected[
                                                                                     1].split(
                                                                                     '.')[
                                                                                 ::-1]]:
                    list_dates_corrected[0], list_dates_corrected[1] = list_dates_corrected[1], \
                        list_dates_corrected[0]
                last_date = ' сроком до ' + list_dates_corrected[1]
            list_date = ' от ' + list_dates_corrected[0]
        print(f'list_date = {list_date}')
        print(f'last_date = {last_date}')
        table_info['ОЛ'] = list_holder + list_date + list_number + last_date
    else:
        open_list = RE_OPENLIST_TYPE2.search(text_to_write)
        if not open_list:
            open_list = RE_OPENLIST_TYPE3.search(text_to_write)
        if not open_list:
            open_list = RE_OPENLIST_TYPE4.search(text_to_write)
        if not open_list:
            open_list = RE_OPENLIST_TYPE5.search(text_to_write)
        if open_list:
            open_list = open_list.group(0)
            list_holder = RE_OPENLIST_HOLDER2.search(open_list)
            if list_holder:
                list_holder = list_holder.group(0)
            if not list_holder:
                list_holder = RE_OPENLIST_HOLDER3.search(open_list)
                if list_holder:
                    list_holder = list_holder.group(0)
            if not list_holder:
                list_holder = RE_OPENLIST_HOLDER4.search(open_list)
                if list_holder:
                    list_holder = list_holder.group(0)
            if not list_holder:
                list_holder = ''
            list_number = RE_OPENLIST_NUMBER.search(open_list)
            if list_number:
                list_number = list_number.group(0)
            else:
                list_number = ''
            list_date = RE_OPENLIST_DATE_DOT.search(open_list)
            if list_date:
                list_date = list_date.group(0)
            if not list_date:
                list_date = RE_OPENLIST_DATE_WORDS.search(open_list)
                if list_date:
                    list_date = list_date.group(0).replace('«', '').replace('»', '')
                    list_month = RE_OPENLIST_MONTH.search(list_date).group(0)
                    list_date = list_date.replace(list_month, '').replace('  ',
                                                                          '.' + months[
                                                                              list_month] + '.')
                    list_day = list_date[:list_date.find('.')]
                    if len(list_day) < 2:
                        list_date = '0' + list_date
            if list_date:
                list_date = ' от ' + list_date
            else:
                list_date = ''
            table_info['ОЛ'] = list_holder + list_date + ' ' + list_number


RE_VOAN1 = re.compile(r'выявлен[\n ]+объект[\n ]+археологического[\n ]+наследия[\n ]+.*«.*»', re.IGNORECASE)
RE_VOAN2 = re.compile(r'выявлен[\n ]+объект[\n ]+археологического[\n ]+наследия[\n ]+.*".*"', re.IGNORECASE)
RE_VOAN3 = re.compile(r'ВОАН\s+.*«.*»', re.IGNORECASE)


def extract_voan(text, table_info):
    voan = RE_VOAN1.search(text)
    if not voan:
        voan = RE_VOAN2.search(text)
    if not voan:
        voan = RE_VOAN3.search(text)
    if voan:
        voan = voan.group(0)
        voan = ' ВОАН ' + voan[voan.find('«') - 1:]
        if 'Заключение. Выявленые объекты.' in table_info.keys() and 'ВОАН' not in table_info[
            'Заключение. Выявленые объекты.'] and \
                'отрицательное' in table_info['Заключение. Выявленые объекты.'].lower():
            table_info['Заключение. Выявленые объекты.'] += voan
        else:
            voan_reserve = voan
            return voan_reserve
    return None


RE_EXECUTOR_DIRECTOR = re.compile(r'Директор [а-яА-ЯёЁa-zA-Z\n«»" -]+.{1}\..{1}\..+', re.IGNORECASE)
RE_EXECUTOR_EXPERT_CHECK = re.compile(r'Эксперт', re.IGNORECASE)
RE_EXECUTOR_INITIALS = re.compile(r'.{1}\..{1}\..+', re.IGNORECASE)
RE_EXECUTOR_ORG = re.compile(
    r'Полное\s*и\s*сокращенное\s*наименование\s*организации[а-яА-ЯёЁa-zA-Z\n«»" -()]+?(?=Организационно)',
    re.IGNORECASE)
RE_EXECUTOR_ORG_PREFIX = re.compile(r'Полное\s*и\s*сокращенное\s*наименование\s*организации\s*', re.IGNORECASE)


def extract_executor(text, table_info):
    executor = RE_EXECUTOR_DIRECTOR.search(text)
    if executor and RE_EXECUTOR_EXPERT_CHECK.search(text):
        executor = executor.group(0).replace('Директор ', '').replace('директор ', '')
        executor = executor[:RE_EXECUTOR_INITIALS.search(executor).start()]
        table_info['Исполнитель полевых работ (юр. лицо)'] = executor
    else:
        executor = RE_EXECUTOR_ORG.search(text)
        if executor:
            res = executor.group(0)
            executor = res[RE_EXECUTOR_ORG_PREFIX.search(res).end():]
            table_info['Исполнитель полевых работ (юр. лицо)'] = executor
