DROP TABLE IF EXISTS users;
DROP TABLE IF EXISTS lists;
DROP TABLE IF EXISTS entries;
DROP TABLE IF EXISTS entryPartOf;
DROP TABLE IF EXISTS memberOf;
DROP TABLE IF EXISTS ownerOf;

-- Users
CREATE TABLE users (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  username TEXT UNIQUE NOT NULL,
  password TEXT NOT NULL,
  inv_code TEXT
);

--Global, private, shared
CREATE TABLE lists (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  type TEXT NOT NULL,
  title TEXT NOT NULL
);

-- Individual inter entry ("user1:reason")
CREATE TABLE entries (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  author_id INTEGER,
  username TEXT NOT NULL,
  reason TEXT NOT NULL,
  FOREIGN KEY (author_id) REFERENCES users (id)
);

-- Connect each entry with a list
CREATE TABLE entryPartOf (
  entry_id INTEGER REFERENCES entries (id),
  list_id INTEGER REFERENCES lists (id),
  PRIMARY KEY (entry_id, list_id)
);

-- Connect a user with a shared list (incoming)
CREATE TABLE memberOf (
  u_id INTEGER REFERENCES users (id),
  list_id INTEGER REFERENCES lists (id),
  PRIMARY KEY (u_id, list_id)
);

-- Connect a user with a shared list (outgoing)
CREATE TABLE ownerOf (
  u_id INTEGER REFERENCES users (id),
  list_id INTEGER REFERENCES lists (id),
  PRIMARY KEY (u_id, list_id)
);

--Add Base Entries
INSERT INTO lists (type, title)
VALUES ('global', 'Global');