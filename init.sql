DROP TABLE acts CASCADE;
DROP TABLE tech_reports CASCADE;
DROP TABLE scientific_reports CASCADE;
DROP TABLE open_lists CASCADE;
DROP TABLE user_tasks CASCADE;
DROP TABLE users CASCADE;

-- Пользователи 
CREATE TABLE users
(
    id           SERIAL PRIMARY KEY,
    password     VARCHAR(128)             NOT NULL,
    last_login   TIMESTAMP WITH TIME ZONE NULL,
    is_superuser BOOLEAN                  NOT NULL,
    username     VARCHAR(150)             NOT NULL UNIQUE,
    first_name   VARCHAR(30)              NOT NULL,
    last_name    VARCHAR(150)             NOT NULL,
    email        VARCHAR(254)             NOT NULL UNIQUE,
    is_staff     BOOLEAN                  NOT NULL,
    is_active    BOOLEAN                  NOT NULL,
    date_joined  TIMESTAMP WITH TIME ZONE NOT NULL,
    UNIQUE (username),
    UNIQUE (email),
    avatar       VARCHAR(254)             NULL
);

-- Пользовательские загрузки
CREATE TABLE user_tasks
(
    id             serial PRIMARY KEY,
    user_id        integer REFERENCES users (id),
    task_id        VARCHAR(255),
    files_type     VARCHAR(255) NULL,
    upload_source          json NULL
);

-- Акты
CREATE TABLE acts
(
    id             serial PRIMARY KEY,
    user_id        integer REFERENCES users (id),

    date_uploaded          TIMESTAMP WITH TIME ZONE NULL,
    upload_source          json NULL,
    is_processing          BOOLEAN DEFAULT TRUE,

    year           text NULL,
    finish_date    text NULL,
    type           text NULL,
    name_number    text NULL,
    place          text NULL,
    customer       text NULL,
    area           text NULL,
    expert         text NULL,
    executioner    text NULL,
    open_list      text NULL,
    conclusion     text NULL,
    border_objects text NULL,
    source         json NULL,

    act            text NULL,
    start_date     text NULL,
    end_date       text NULL,
    exp_place      text NULL,
    exp_customer   text NULL,
    exp_expert     text NULL,
    relationship   text NULL,
    goal           text NULL,
    object         text NULL,
    docs           text NULL,
    exp_info       text NULL,
    exp_facts      text NULL,
    literature     text NULL,
    exp_conclusion text NULL,
    supplement     json NULL
);

-- Научные отчёты
CREATE TABLE scientific_reports
(
    id               serial PRIMARY KEY,
    user_id          integer REFERENCES users (id),

    date_uploaded          TIMESTAMP WITH TIME ZONE NULL,
    upload_source          json NULL,
    is_processing          BOOLEAN DEFAULT TRUE,

    name             text NULL,
    organization     text NULL,
    author           text NULL,
    open_list        text NULL,
    writing_date     text NULL,
    introduction     text NULL,
    contractors      text NULL,
    place            text NULL,
    area_info        text NULL,
    research_history text NULL,
    results          text NULL,
    conclusion       text NULL,
    source           json NULL,
    content          json Null,
    supplement       json Null
);

-- Научно-технические отчёты
CREATE TABLE tech_reports
(
    id               serial PRIMARY KEY,
    user_id          integer REFERENCES users (id),

    date_uploaded          TIMESTAMP WITH TIME ZONE NULL,
    upload_source          json NULL,
    is_processing          BOOLEAN DEFAULT TRUE,

    name             text,
    organization     text,
    author           text,
    open_list        text,
    writing_date     text,
    introduction     text,
    contractors      text,
    place            text,
    area_info        text,
    research_history text,
    results          text,
    conclusion       text,
    source           json NULL,
    supplement       json NULL
);

-- Открытые листы
CREATE TABLE open_lists
(
    id         serial PRIMARY KEY,
    user_id    integer REFERENCES users (id),

    origin_filename        VARCHAR(255) NULL,
    date_uploaded          TIMESTAMP WITH TIME ZONE NULL,
    upload_source          json NULL,
    is_processing          BOOLEAN DEFAULT TRUE,

    number     text NULL,
    holder     text NULL,
    object     text NULL,
    works      text NULL,
    start_date text NULL,
    end_date   text NULL,
    source     text NULL
);

-- GRANT ALL PRIVILEGES ON DATABASE postgres TO agregator;
-- GRANT ALL PRIVILEGES ON TABLE users TO agregator;
-- GRANT ALL PRIVILEGES ON TABLE user_tasks TO agregator;
-- GRANT ALL PRIVILEGES ON TABLE scientific_reports TO agregator;
-- GRANT ALL PRIVILEGES ON TABLE tech_reports TO agregator;
-- GRANT ALL PRIVILEGES ON TABLE acts TO agregator;
-- GRANT ALL PRIVILEGES ON TABLE open_lists TO agregator;
-- GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO agregator;