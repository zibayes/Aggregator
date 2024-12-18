-- DROP TABLE  acts CASCADE;
-- DROP TABLE  users CASCADE;

-- Пользователи 
CREATE TABLE users
(
    user_id serial PRIMARY KEY,
    email text UNIQUE NOT NULL,
    username text UNIQUE NOT NULL,
    avatar bytea NULL,
    password text -- NOT NULL
);

-- Акты
CREATE TABLE acts
(
    act_id serial PRIMARY KEY,
	user_id integer REFERENCES users(user_id),
	supplement_id integer REFERENCES supplements(supplement_id),
    object text,
    place text,
    area text,
    pits text,
    coordinates text,
    expert text,
    customer text,
    open_list text,
    conclusion text
);

-- Научные отчёты
CREATE TABLE scientific_reports
(
    report_id serial PRIMARY KEY,
	user_id integer REFERENCES users(user_id),
	supplement_id integer REFERENCES supplements(supplement_id),
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
    conclusion text
);

-- Научно-технические отчёты
CREATE TABLE tech_reports
(
    report_id serial PRIMARY KEY,
	user_id integer REFERENCES users(user_id),
	supplement_id integer REFERENCES supplements(supplement_id),
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
    conclusion text
);

-- Приложения
CREATE TABLE supplements
(
    supplement_id serial PRIMARY KEY,
    maps text,
    object_fotos text,
    pits_fotos text,
	plans text,
    material_fotos text,
    heritage_info text
);


CREATE TABLE roles(
    role_id serial PRIMARY KEY,
    name text
);

CREATE TABLE users_roles(
    ur_id serial PRIMARY KEY,
    user_id int REFERENCES users(user_id),
    role_id int REFERENCES roles(role_id)
);

-- ROLES
INSERT INTO roles(name) VALUES ('admin');