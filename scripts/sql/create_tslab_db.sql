-- pgAdmin: JEDEN Block einzeln markieren und mit F5 ausfuehren (nicht alles auf einmal)!
-- CREATE DATABASE darf nicht in einer Transaktion laufen.

-- Schritt 1 (zuerst ausfuehren):
CREATE USER tslab WITH PASSWORD 'tslab' LOGIN;

-- Schritt 2 (separat ausfuehren, nur diese eine Zeile markieren):
CREATE DATABASE tslab OWNER tslab;

-- Schritt 3 (nach Schritt 2, separat ausfuehren):
GRANT ALL PRIVILEGES ON DATABASE tslab TO tslab;
