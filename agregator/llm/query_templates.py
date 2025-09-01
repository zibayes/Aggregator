DB_QUERY_TEMPLATE = """
В базе данных есть следующие таблицы:
---
-- Пользователи 
CREATE TABLE users
(
    id           SERIAL PRIMARY KEY,      -- идентификатор (первичный ключ)
    password     VARCHAR(128)             NOT NULL,  -- пароль
    last_login   TIMESTAMP WITH TIME ZONE NULL,     -- последнее время входа
    is_superuser BOOLEAN                  NOT NULL,  -- является ли суперпользователем
    username     VARCHAR(150)             NOT NULL UNIQUE,  -- имя пользователя (логин)
    first_name   VARCHAR(30)              NOT NULL,  -- имя
    last_name    VARCHAR(150)             NOT NULL,  -- фамилия
    email        VARCHAR(254)             NOT NULL UNIQUE,  -- электронная почта
    is_staff     BOOLEAN                  NOT NULL,  -- является ли сотрудником
    is_active    BOOLEAN                  NOT NULL,  -- активен ли пользователь
    date_joined  TIMESTAMP WITH TIME ZONE NOT NULL,  -- дата регистрации
    UNIQUE (username),                     -- уникальность имени пользователя
    UNIQUE (email),                        -- уникальность электронной почты
    avatar       VARCHAR(254)             NULL      -- аватар
);

-- Пользовательские загрузки
CREATE TABLE user_tasks
(
    id             serial PRIMARY KEY,     -- идентификатор (первичный ключ)
    user_id        integer REFERENCES users (id),  -- идентификатор пользователя (внешний ключ)
    task_id        VARCHAR(255),           -- идентификатор задачи
    files_type     VARCHAR(255) NULL,      -- тип файлов
    upload_source   json NULL               -- ссылка на источник загрузки
);

-- Акты
CREATE TABLE acts
(
    id             serial PRIMARY KEY,     -- идентификатор (первичный ключ)
    user_id        integer REFERENCES users (id),  -- идентификатор пользователя (внешний ключ)

    date_uploaded          TIMESTAMP WITH TIME ZONE NULL,  -- дата загрузки отчёта на сервер
    upload_source          json NULL,                       -- источник загрузки
    is_processing          BOOLEAN DEFAULT TRUE,            -- находится ли отчёт в процессе обработки

    year           text NULL,              -- год написания акта
    finish_date    text NULL,              -- дата завершения проведения экспертизы
    type           text NULL,              -- тип экспертизы
    name_number    text NULL,              -- наименование и номер акта
    place          text NULL,              -- место проведения экспертизы
    customer       text NULL,              -- заказчик экспертизы
    area           text NULL,              -- площадь участка, на котором проводилась экспертиза
    expert         text NULL,              -- эксперт, проводивший экспертизу
    executioner    text NULL,              -- исполнитель, проводивший экспертизу (юридическое лицо)
    open_list      text NULL,              -- открытый лист
    conclusion     text NULL,              -- заключение экспертизы
    border_objects text NULL,              -- близлижайшие объекты, для обозначения границ экспертизы
    source         json NULL,              -- путь к файлам отчёта на сервере

    act            text NULL,              -- название акта
    start_date     text NULL,              -- дата начала проведения экспертизы
    end_date       text NULL,              -- дата окончания проведения экспертизы
    exp_place      text NULL,              -- место проведения экспертизы
    exp_customer   text NULL,              -- заказчик экспертизы
    exp_expert     text NULL,              -- сведения об эксперте, проводившем экспертизу
    relationship   text NULL,              -- отношение к заказчику
    goal           text NULL,              -- цель экспертизы
    object         text NULL,              -- объект экспертизы
    docs           text NULL,              -- документы
    exp_info       text NULL,              -- информация экспертизы
    exp_facts      text NULL,              -- факты экспертизы
    literature     text NULL,              -- литература
    exp_conclusion text NULL,              -- заключение экспертизы
    supplement     json NULL               -- приложение к отчёту (иллюстрации)
);

-- Научные отчёты
CREATE TABLE scientific_reports
(
    id               serial PRIMARY KEY,   -- идентификатор (первичный ключ)
    user_id          integer REFERENCES users (id),  -- идентификатор пользователя (внешний ключ)

    date_uploaded          TIMESTAMP WITH TIME ZONE NULL,  -- дата загрузки отчёта на сервер
    upload_source          json NULL,                       -- источник загрузки
    is_processing          BOOLEAN DEFAULT TRUE,            -- находится ли отчёт в процессе обработки

    name             text NULL,              -- название отчёта
    organization     text NULL,              -- организация, проводившая экспертизу
    author           text NULL,              -- автор отчёта
    open_list        text NULL,              -- открытый лист
    writing_date     text NULL,              -- дата написания отчёта
    introduction     text NULL,              -- введение
    contractors      text NULL,              -- исполнители экспертизы
    place            text NULL,              -- место проведения экспертизы
    area_info        text NULL,              -- площадь участка, на котором проводилась экспертиза
    research_history text NULL,              -- история исследования
    results          text NULL,              -- результаты экспертизы
    conclusion       text NULL, 			 -- заключение экспертизы
    source           json NULL,              -- путь к файлам отчёта на сервере
    content          json NULL,              -- содержание отчёта
    supplement       json NULL               -- приложение к отчёту (иллюстрации)
);

-- Научно-технические отчёты
CREATE TABLE tech_reports
(
    id               serial PRIMARY KEY,     -- идентификатор (первичный ключ)
    user_id          integer REFERENCES users (id),  -- идентификатор пользователя (внешний ключ)

    date_uploaded          TIMESTAMP WITH TIME ZONE NULL,   -- дата загрузки отчёта на сервер
    upload_source          json NULL,                       -- источник загрузки
    is_processing          BOOLEAN DEFAULT TRUE,            -- находится ли отчёт в процессе обработки

    name             text NULL,              -- название отчёта
    organization     text NULL,              -- организация, проводившая экспертизу
    author           text NULL,              -- автор отчёта
    open_list        text NULL,              -- открытый лист
    writing_date     text NULL,              -- дата написания отчёта
    introduction     text NULL,              -- введение
    contractors      text NULL,              -- исполнители экспертизы
    place            text NULL,              -- место проведения экспертизы
    area_info        text NULL,              -- площадь участка, на котором проводилась экспертиза
    research_history text NULL,              -- история исследования
    results          text NULL,              -- результаты экспертизы
    conclusion       text NULL, 			 -- заключение экспертизы
    source           json NULL,              -- путь к файлам отчёта на сервере
    content          json NULL,              -- содержание отчёта
    supplement       json NULL               -- приложение к отчёту (иллюстрации)
);

-- Открытые листы
CREATE TABLE open_lists
(
    id         serial PRIMARY KEY,       -- идентификатор (первичный ключ)
    user_id    integer REFERENCES users (id),  -- идентификатор пользователя (внешний ключ)

    origin_filename        VARCHAR(255) NULL,               -- исходное имя файла отчёта
    date_uploaded          TIMESTAMP WITH TIME ZONE NULL,   -- дата загрузки отчёта на сервер
    upload_source          json NULL,                       -- источник загрузки
    is_processing          BOOLEAN DEFAULT TRUE,            -- находится ли отчёт в процессе обработки

    number     text NULL,              -- номер открытого листа
    holder     text NULL,              -- держатель открытого листа
    object     text NULL,              -- объект, на котором можно проводить работы
    works      text NULL,              -- работы, которые разрешены для проведения на указанном объекте
    start_date text NULL,              -- дата начала действия документа
    end_date   text NULL,              -- дата окончания действия документа
    source     text NULL               -- путь к файлам отчёта на сервере
);
---

Если в запросе есть требование получить информацию о том или ином отчёте, то не нужно делать привязку на его 
принадлежность к текущему пользователю по id или username, кроме случаев, когда пользователь хочет получить информацию 
о загруженных именно им отчётах. Если спрашивается номер отчёта, то имеется ввиду номер в названии отчёта, а не его id. 
Делай поиск по текстовым полям не на точное совпадение, а используй оператор LIKE.
Делай поиск по текстовым полям не на точное совпадение, а используй оператор LIKE.
Если в вопросе есть фамилия, имя или отчество - надо сделать запрос, который учитывает варианты, при которых:
- фамилия, имя и отчество даны полностью без сокращений;
- фамилия дана полностью, а имя и отчество сокращено до инициалов;
- инициалы могут находиться как до фамилии, так и после неё;
- фамилия, имя и отчество могут иметь именительный или родительный падеж.
Пример запроса для ФИО Алексей Сергеевич Иванов:
SELECT COUNT(*) 
FROM open_lists 
WHERE (holder LIKE '%Иванов%' OR holder LIKE '%Иванова%')                           -- Проверка для фамилии
AND (holder LIKE '%Алексей%' OR holder LIKE '%Алексея%' OR holder LIKE '%А%')       -- Проверка для имени
AND (holder LIKE '%Сергеевич%' OR holder LIKE '%Сергеевича%' OR holder LIKE '%С%')  -- Проверка для отчества
Используй **ВСЕ** варианты для поиска по ФИО, представленные в данном примере.

Составь только SQL-запрос к реляционной БД без лишних комментариев и пояснений, получив по которому информацию, 
ты сможешь ответить на вопрос пользователя:
{question}
"""
SOURCE_TEMPLATE = """
Пользователь задал следующий вопрос:

{question}

---
Определи, какой источник информации тебе потребуется, чтобы на него ответить (можно выбрать несколько):
- векторная база данных (для ответа на вопрос нужно анализировать текстовое содержание; документов)
- реляционная база данных (для ответа на вопрос нужны метаданные документов);
- выход в интернет (вопрос не имеет отношения к базе данных и документам);
- источник информации не требуется (вопрос не по теме).
Дай ответ без лишних комментариев и пояснений. Можно выбрать только из предложенных вариантов.
"""
RESULT_TEMPLATE = """
Пользователь задал следующий вопрос:

{question}

---
По твоему запросу к БД получена следующая информация по данному вопросу:

{db_response}

---
Основываясь на полученной информации, дай ответ на вопрос пользователя.
"""
PROMPT_TEMPLATE = """
Ответь на вопрос базируясь только на этом контексте:

{context}

---
Никак не поясняй полученную информацию - представь её как твой собственный ответ, переформулировав её для удобства.
Ответь на вопрос, используя только контекст: {question}
"""
REFORMULATE_TEMPLATE = """
Пользователь задал следующий вопрос:

{question}

---

Если вопрос сформулирован непонятно или некорректно, перефразируй его и представь свои варианты формулировок, 
разделяя их переносами строки, например: Кто такой эксперт в археологии? \n Что такое эксперт по археологии?
В ответе надо только перечислить варианты формулировок, никак их не поясняя. Нельзя использовать разметку Markdown.
Отвечай только на русском языке.
"""
INTERNET_QUERY_TEMPLATE = """
Переформулируй вопрос пользователя так, чтобы по нему можно было найти необходимую 
в интернете информацию для ответа на него:

{question}
"""
SIMPLE_QUESTION_TEMPLATE = """
Пользователь задал следующий вопрос:

{question}
"""
INFO_SOURCES = [
    'векторная база данных',
    'реляционная база данных',
    'выход в интернет',
    'источник информации не требуется'
]
