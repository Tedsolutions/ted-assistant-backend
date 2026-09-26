"""
Base de données minimale (SQLite) pour stocker les demandes de contact
et de rendez-vous laissées par les visiteurs via le chatbot.

SQLite suffit largement pour démarrer (gratuit, aucun serveur à gérer).
Si le volume grossit plus tard, on pourra migrer vers Postgres (ex. Supabase)
sans changer la logique de l'app, juste cette couche.
"""

import sqlite3
from datetime import datetime

DB_PATH = "ted_assistant.db"


def get_connection():
    return sqlite3.connect(DB_PATH)


def init_db():
    conn = get_connection()
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS contacts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nom TEXT,
            email TEXT,
            telephone TEXT,
            besoin TEXT,
            creneau_souhaite TEXT,
            date_creation TEXT
        )
        """
    )
    conn.commit()
    conn.close()


def save_contact(nom, email, telephone, besoin, creneau_souhaite):
    conn = get_connection()
    conn.execute(
        """
        INSERT INTO contacts (nom, email, telephone, besoin, creneau_souhaite, date_creation)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (nom, email, telephone, besoin, creneau_souhaite, datetime.utcnow().isoformat()),
    )
    conn.commit()
    conn.close()


def list_contacts():
    conn = get_connection()
    cur = conn.execute("SELECT * FROM contacts ORDER BY date_creation DESC")
    rows = cur.fetchall()
    conn.close()
    return rows
