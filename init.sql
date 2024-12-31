DROP TABLE  users_roles CASCADE;
DROP TABLE  roles CASCADE;
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
    maps text,
    object_fotos text,
    pits_fotos text,
	plans text,
    material_fotos text,
    heritage_info text
);

-- Акты
CREATE TABLE acts
(
    id serial PRIMARY KEY,
	user_id integer REFERENCES users(id),
	supplement_id integer REFERENCES supplements(id),
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
    conclusion text
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
    conclusion text
);


CREATE TABLE roles(
    id serial PRIMARY KEY,
    name text
);

CREATE TABLE users_roles(
    id serial PRIMARY KEY,
    user_id int REFERENCES users(id),
    role_id int REFERENCES roles(id)
);

-- ROLES
INSERT INTO roles(name) VALUES ('admin');

GRANT ALL PRIVILEGES ON DATABASE postgres TO agregator;
GRANT ALL PRIVILEGES ON TABLE users TO agregator;
GRANT ALL PRIVILEGES ON TABLE supplements TO agregator;
GRANT ALL PRIVILEGES ON TABLE scientific_reports TO agregator;
GRANT ALL PRIVILEGES ON TABLE tech_reports TO agregator;
GRANT ALL PRIVILEGES ON TABLE acts TO agregator;
GRANT ALL PRIVILEGES ON TABLE roles TO agregator;
GRANT ALL PRIVILEGES ON TABLE users_roles TO agregator;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO agregator;