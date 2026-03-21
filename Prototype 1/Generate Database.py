import sqlite3


def create_database():
    conn = sqlite3.connect('Browser_Data.db')
    c = conn.cursor()

    c.execute('''CREATE TABLE IF NOT EXISTS users
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  username TEXT NOT NULL,
                  password TEXT NOT NULL)''')

    c.execute('''CREATE TABLE IF NOT EXISTS items
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  name TEXT NOT NULL,
                  description TEXT,
                  price REAL NOT NULL)''')

    conn.commit()
    conn.close()