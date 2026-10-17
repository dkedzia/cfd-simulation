CREATE TABLE strategies (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL UNIQUE,
    definition TEXT NOT NULL
);
