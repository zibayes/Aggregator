DROP TABLE  acts CASCADE;
DROP TABLE  tech_reports CASCADE;
DROP TABLE  scientific_reports CASCADE;
DROP TABLE  supplements CASCADE;
DROP TABLE  users CASCADE;

-- Пользователи 
CREATE TABLE users
(
    id SERIAL PRIMARY KEY,
    password VARCHAR(128) NOT NULL,
    last_login TIMESTAMP WITH TIME ZONE NULL,
    is_superuser BOOLEAN NOT NULL,
    username VARCHAR(150) NOT NULL UNIQUE,
    first_name VARCHAR(30) NOT NULL,
    last_name VARCHAR(150) NOT NULL,
    email VARCHAR(254) NOT NULL UNIQUE,
    is_staff BOOLEAN NOT NULL,
    is_active BOOLEAN NOT NULL,
    date_joined TIMESTAMP WITH TIME ZONE NOT NULL,
    UNIQUE (username),
    UNIQUE (email),
    avatar VARCHAR(254) NULL
);

-- Приложения
CREATE TABLE supplements
(
    id serial PRIMARY KEY,
    maps text NULL,
    object_fotos text NULL,
    pits_fotos text NULL,
	plans text NULL,
    material_fotos text NULL,
    heritage_info text NULL
);

-- Акты
CREATE TABLE acts
(
    id serial PRIMARY KEY,
	user_id integer REFERENCES users(id),
	supplement_id integer REFERENCES supplements(id),

    year text NULL,
    finish_date text NULL,
    type text NULL,
    name_number text NULL,
    place text NULL,
    customer text NULL,
    area text NULL,
    expert text NULL,
    executioner text NULL,
    open_list text NULL,
    conclusion text NULL,
    border_objects text NULL,
    source text NULL,

    act text NULL,
    start_date text NULL,
    end_date text NULL,
    exp_place text NULL,
    exp_customer text NULL,
    exp_expert text NULL,
    relationship text NULL,
    goal text NULL,
    object text NULL,
    docs text NULL,
    exp_info text NULL,
    exp_facts text NULL,
    literature text NULL,
    exp_conclusion text NULL
);

-- Научные отчёты
CREATE TABLE scientific_reports
(
    id serial PRIMARY KEY,
	user_id integer REFERENCES users(id),
	supplement_id integer REFERENCES supplements(id),
    name text NULL,
    organization text NULL,
    author text NULL,
	open_list text NULL,
    writing_date text NULL,
    introduction text NULL,
    contractors text NULL,
    place text NULL,
    area_info text NULL,
    research_history text NULL,
    results text NULL,
    conclusion text NULL,
	source text NULL
);

-- Научно-технические отчёты
CREATE TABLE tech_reports
(
    id serial PRIMARY KEY,
	user_id integer REFERENCES users(id),
	supplement_id integer REFERENCES supplements(id),
    name text,
    organization text,
    author text,
	open_list text,
    writing_date text,
    introduction text,
    contractors text,
    place text,
    area_info text,
    research_history text,
    results text,
    conclusion text,
    source text NULL
);

-- Открытые листы
CREATE TABLE open_lists
(
    id serial PRIMARY KEY,
	user_id integer REFERENCES users(id),
    number text NULL,
    holder text NULL,
    object text NULL,
	works text NULL,
    start_date text NULL,
    end_date text NULL,
	source text NULL
);

GRANT ALL PRIVILEGES ON DATABASE postgres TO agregator;
GRANT ALL PRIVILEGES ON TABLE users TO agregator;
GRANT ALL PRIVILEGES ON TABLE supplements TO agregator;
GRANT ALL PRIVILEGES ON TABLE scientific_reports TO agregator;
GRANT ALL PRIVILEGES ON TABLE tech_reports TO agregator;
GRANT ALL PRIVILEGES ON TABLE acts TO agregator;
GRANT ALL PRIVILEGES ON TABLE open_lists TO agregator;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO agregator;