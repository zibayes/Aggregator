DROP TABLE archaeological_heritage_sites CASCADE;
DROP TABLE identified_archaeological_heritage_sites CASCADE;
DROP TABLE object_account_cards CASCADE;
DROP TABLE acts CASCADE;
DROP TABLE tech_reports CASCADE;
DROP TABLE scientific_reports CASCADE;
DROP TABLE open_lists CASCADE;
DROP TABLE user_tasks CASCADE;
DROP TABLE users CASCADE;

-- Пользователи 
CREATE TABLE users
(
    id           SERIAL PRIMARY KEY,                       -- идентификатор (первичный ключ)
    password     VARCHAR(128)             NOT NULL,        -- пароль
    last_login   TIMESTAMP WITH TIME ZONE NULL,            -- последнее время входа
    is_superuser BOOLEAN                  NOT NULL,        -- является ли суперпользователем
    username     VARCHAR(150)             NOT NULL UNIQUE, -- имя пользователя (логин)
    first_name   VARCHAR(30)              NOT NULL,        -- имя
    last_name    VARCHAR(150)             NOT NULL,        -- фамилия
    email        VARCHAR(254)             NOT NULL UNIQUE, -- электронная почта
    is_staff     BOOLEAN                  NOT NULL,        -- является ли сотрудником
    is_active    BOOLEAN                  NOT NULL,        -- активен ли пользователь
    date_joined  TIMESTAMP WITH TIME ZONE NOT NULL,        -- дата регистрации
    UNIQUE (username),                                     -- уникальность имени пользователя
    UNIQUE (email),                                        -- уникальность электронной почты
    avatar       VARCHAR(254)             NULL             -- аватар
);

-- Пользовательские загрузки
CREATE TABLE user_tasks
(
    id            serial PRIMARY KEY,            -- идентификатор (первичный ключ)
    user_id       integer REFERENCES users (id), -- идентификатор пользователя (внешний ключ)
    task_id       VARCHAR(255),                  -- идентификатор задачи
    files_type    VARCHAR(255) NULL,             -- тип файлов
    upload_source json         NULL              -- ссылка на источник загрузки
);

-- Акты
CREATE TABLE acts
(
    id             serial PRIMARY KEY,            -- идентификатор (первичный ключ)
    user_id        integer REFERENCES users (id), -- идентификатор пользователя (внешний ключ)

    date_uploaded  TIMESTAMP WITH TIME ZONE NULL, -- дата загрузки отчёта на сервер
    upload_source  json                     NULL, -- источник загрузки
    is_processing  BOOLEAN DEFAULT TRUE,          -- находится ли отчёт в процессе обработки
    is_public      BOOLEAN DEFAULT TRUE,          -- находится ли отчёт в открытом доступе

    year           text                     NULL, -- год написания акта
    finish_date    text                     NULL, -- дата завершения проведения экспертизы
    type           text                     NULL, -- тип экспертизы
    name_number    text                     NULL, -- наименование и номер акта
    place          text                     NULL, -- место проведения экспертизы
    customer       text                     NULL, -- заказчик экспертизы
    area           text                     NULL, -- площадь участка, на котором проводилась экспертиза
    expert         text                     NULL, -- эксперт, проводивший экспертизу
    executioner    text                     NULL, -- исполнитель, проводивший экспертизу (юридическое лицо)
    open_list      text                     NULL, -- открытый лист
    conclusion     text                     NULL, -- заключение экспертизы
    border_objects text                     NULL, -- близлижайшие объекты, для обозначения границ экспертизы
    source         json                     NULL, -- путь к файлам отчёта на сервере

    act            text                     NULL, -- название акта
    start_date     text                     NULL, -- дата начала проведения экспертизы
    end_date       text                     NULL, -- дата окончания проведения экспертизы
    exp_place      text                     NULL, -- место проведения экспертизы
    exp_customer   text                     NULL, -- заказчик экспертизы
    exp_expert     text                     NULL, -- сведения об эксперте, проводившем экспертизу
    relationship   text                     NULL, -- отношение к заказчику
    goal           text                     NULL, -- цель экспертизы
    object         text                     NULL, -- объект экспертизы
    docs           text                     NULL, -- документы
    exp_info       text                     NULL, -- информация экспертизы
    exp_facts      text                     NULL, -- факты экспертизы
    literature     text                     NULL, -- литература
    exp_conclusion text                     NULL, -- заключение экспертизы
    supplement     json                     NULL, -- приложение к отчёту (иллюстрации)
    coordinates    json                     NULL  -- координаты точек фотофиксации, шурфов, каталога и выписок из ЕГРН
);

-- Научные отчёты
CREATE TABLE scientific_reports
(
    id               serial PRIMARY KEY,            -- идентификатор (первичный ключ)
    user_id          integer REFERENCES users (id), -- идентификатор пользователя (внешний ключ)

    date_uploaded    TIMESTAMP WITH TIME ZONE NULL, -- дата загрузки отчёта на сервер
    upload_source    json                     NULL, -- источник загрузки
    is_processing    BOOLEAN DEFAULT TRUE,          -- находится ли отчёт в процессе обработки
    is_public        BOOLEAN DEFAULT TRUE,          -- находится ли отчёт в открытом доступе

    name             text                     NULL, -- название отчёта
    organization     text                     NULL, -- организация, проводившая экспертизу
    author           text                     NULL, -- автор отчёта
    open_list        text                     NULL, -- открытый лист
    writing_date     text                     NULL, -- год написания отчёта
    introduction     text                     NULL, -- введение
    contractors      text                     NULL, -- исполнители экспертизы
    place            text                     NULL, -- место проведения экспертизы
    area_info        text                     NULL, -- площадь участка, на котором проводилась экспертиза
    research_history text                     NULL, -- история исследования
    results          text                     NULL, -- результаты экспертизы
    conclusion       text                     NULL, -- заключение экспертизы
    source           json                     NULL, -- путь к файлам отчёта на сервере
    content          json                     NULL, -- содержание отчёта
    supplement       json                     NULL, -- приложение к отчёту (иллюстрации)
    coordinates      json                     NULL  -- координаты точек фотофиксации, шурфов, каталога и выписок из ЕГРН
);

-- Научно-технические отчёты
CREATE TABLE tech_reports
(
    id               serial PRIMARY KEY,            -- идентификатор (первичный ключ)
    user_id          integer REFERENCES users (id), -- идентификатор пользователя (внешний ключ)

    date_uploaded    TIMESTAMP WITH TIME ZONE NULL, -- дата загрузки отчёта на сервер
    upload_source    json                     NULL, -- источник загрузки
    is_processing    BOOLEAN DEFAULT TRUE,          -- находится ли отчёт в процессе обработки
    is_public        BOOLEAN DEFAULT TRUE,          -- находится ли отчёт в открытом доступе

    name             text                     NULL, -- название отчёта
    organization     text                     NULL, -- организация, проводившая экспертизу
    author           text                     NULL, -- автор отчёта
    open_list        text                     NULL, -- открытый лист
    writing_date     text                     NULL, -- год написания отчёта
    introduction     text                     NULL, -- введение
    contractors      text                     NULL, -- исполнители экспертизы
    place            text                     NULL, -- место проведения экспертизы
    area_info        text                     NULL, -- площадь участка, на котором проводилась экспертиза
    research_history text                     NULL, -- история исследования
    results          text                     NULL, -- результаты экспертизы
    conclusion       text                     NULL, -- заключение экспертизы
    source           json                     NULL, -- путь к файлам отчёта на сервере
    content          json                     NULL, -- содержание отчёта
    supplement       json                     NULL, -- приложение к отчёту (иллюстрации)
    coordinates      json                     NULL  -- координаты точек фотофиксации, шурфов, каталога и выписок из ЕГРН
);

-- Открытые листы
CREATE TABLE open_lists
(
    id              serial PRIMARY KEY,            -- идентификатор (первичный ключ)
    user_id         integer REFERENCES users (id), -- идентификатор пользователя (внешний ключ)

    origin_filename VARCHAR(255)             NULL, -- исходное имя файла отчёта
    date_uploaded   TIMESTAMP WITH TIME ZONE NULL, -- дата загрузки отчёта на сервер
    upload_source   json                     NULL, -- источник загрузки
    is_processing   BOOLEAN DEFAULT TRUE,          -- находится ли отчёт в процессе обработки
    is_public       BOOLEAN DEFAULT TRUE,          -- находится ли отчёт в открытом доступе

    number          text                     NULL, -- номер открытого листа
    holder          text                     NULL, -- держатель открытого листа
    object          text                     NULL, -- объект, на котором можно проводить работы
    works           text                     NULL, -- работы, которые разрешены для проведения на указанном объекте
    start_date      text                     NULL, -- дата начала действия документа
    end_date        text                     NULL, -- дата окончания действия документа
    source          text                     NULL  -- путь к файлам открытого листа на сервере
);

-- Учётные карты
CREATE TABLE object_account_cards
(
    id                     serial PRIMARY KEY,            -- идентификатор (первичный ключ)
    user_id                integer REFERENCES users (id), -- идентификатор пользователя (внешний ключ)

    date_uploaded          TIMESTAMP WITH TIME ZONE NULL, -- дата загрузки учётной карты на сервер
    upload_source          json                     NULL, -- источник загрузки
    is_processing          BOOLEAN DEFAULT TRUE,          -- находится ли учётная карта в процессе обработки
    is_public              BOOLEAN DEFAULT TRUE,          -- находится ли учётная карта в открытом доступе
    origin_filename        VARCHAR(255)             NULL, -- исходное имя файла учётной карты

    name                   text                     NULL, -- I. Наименование объекта
    creation_time          text                     NULL, -- II. Время создания (возникновения) объекта
    address                text                     NULL, -- III. Адрес (местонахождение) объекта
    object_type            text                     NULL, -- IV. Вид объекта
    general_classification text                     NULL, -- V. Общая видовая принадлежность объекта
    description            text                     NULL, -- VI. Общее описание объекта и вывод о его историко-культурной ценности
    usage                  text                     NULL, -- VII. Использование объекта культурного наследия или пользователь
    discovery_info         text                     NULL, -- VIII. Сведения о дате и обстоятельствах выявления (обнаружения) объекта
    compiler               text                     NULL, -- Составитель учетной карты
    supplement             json                     NULL, -- приложение к учётной карте (иллюстрации)
    coordinates            json                     NULL, -- каталог координат
    source                 text                     NULL  -- путь к файлам учётной карты а на сервере
);

-- ПАМЯТНИКИ

-- Перечень объектов археологического наследия
CREATE TABLE archaeological_heritage_sites
(
    id              serial PRIMARY KEY,                           -- идентификатор (первичный ключ)
    account_card_id integer REFERENCES object_account_cards (id), -- идентификатор учётной карты (внешний ключ)

    date_uploaded   TIMESTAMP WITH TIME ZONE NULL,                -- дата загрузки на сервер

    doc_name        text                     NULL,                -- Наименование объекта согласно документу о постановке на государственную охрану, датировка объекта
    district        text                     NULL,                -- Район местонахождения
    document        text                     NULL,                -- Документ о постановке на государственную охрану
    register_num    text                     NULL,                -- Регистрационный номер в едином государственном реестре объектов культурного наследия с реквизитами приказа Министерства культуры РФ о регистрации объекта, вид объекта (памятник, ансамбль)
    is_excluded     BOOLEAN DEFAULT FALSE                         -- Является ли объект исключенным из списка
);

-- Перечень выявленных объектов культурного наследия
CREATE TABLE identified_archaeological_heritage_sites
(
    id              serial PRIMARY KEY,                           -- идентификатор (первичный ключ)
    account_card_id integer REFERENCES object_account_cards (id), -- идентификатор учётной карты (внешний ключ)

    date_uploaded   TIMESTAMP WITH TIME ZONE NULL,                -- дата загрузки на сервер

    name            text                     NULL,                -- Наименование выявленного объекта культурного наследия
    address         text                     NULL,                -- Адрес объекта (или описание местоположения объекта)
    obj_info        text                     NULL,                -- Сведения об историко-культурной ценности объекта
    document        text                     NULL,                -- Документ о включении в перечень выявленных объектов
    is_excluded     BOOLEAN DEFAULT FALSE                         -- Является ли объект исключенным из списка
);

-- GRANT ALL PRIVILEGES ON DATABASE postgres TO agregator;
-- GRANT ALL PRIVILEGES ON TABLE users TO agregator;
-- GRANT ALL PRIVILEGES ON TABLE user_tasks TO agregator;
-- GRANT ALL PRIVILEGES ON TABLE scientific_reports TO agregator;
-- GRANT ALL PRIVILEGES ON TABLE tech_reports TO agregator;
-- GRANT ALL PRIVILEGES ON TABLE acts TO agregator;
-- GRANT ALL PRIVILEGES ON TABLE open_lists TO agregator;
-- GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO agregator;


-- Список исторических поселений
-- CREATE TABLE historical_settlements
-- (
--     id            serial PRIMARY KEY,            -- идентификатор (первичный ключ)

--     date_uploaded TIMESTAMP WITH TIME ZONE NULL, -- дата загрузки на сервер

--     doc_address   text                     NULL, -- Адрес объекта в соответствии с документом о принятии на государственную охрану
--     name          text                     NULL, -- Наименование
--     category      text                     NULL, -- Категория историко-культурного значения
--     document      text                     NULL, -- Документ об утверждении  перечня исторических поселений
--     security_obj  text                     NULL, -- Предмет охраны
--     borders       text                     NULL, -- Границы территории
--     requirements  text                     NULL, -- Требования к градостроительным регламентам
--     notes         text                     NULL, -- Примечания
--     is_excluded   BOOLEAN DEFAULT FALSE          -- Является ли поселение исключенным из списка
-- );

-- Перечень объектов культурного наследия
-- CREATE TABLE cultural_heritage_sites
-- (
--     id            serial PRIMARY KEY,            -- идентификатор (первичный ключ)

--     date_uploaded TIMESTAMP WITH TIME ZONE NULL, -- дата загрузки на сервер

--     doc_address   text                     NULL, -- Адрес объекта в соответствии с документом о принятии на государственную охрану
--     exact_address text                     NULL, -- Уточненный адрес объекта (местоположение)
--     object_name   text                     NULL, -- Наименование объекта в соответствии с документом о принятии на государственную охрану, датировка объекта
--     document      text                     NULL, -- Документ о принятии на государственную охрану, регистрационный номер в ЕГРОКН с реквизитами приказа, вид объекта (памятник, ансамбль, достопримечательное место)
--     category      text                     NULL, -- Категория историко-культурного значения
--     notes         text                     NULL, -- Примечания
--     is_excluded   BOOLEAN DEFAULT FALSE          -- Является ли поселение исключенным из списка
-- );