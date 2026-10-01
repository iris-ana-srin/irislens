#database.py
"""
Embeddings are persisted in a SQLite database (data/faces.db).
The FAISS index is rebuilt in memory from the DB on startup.

CREATE TABLE embeddings (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    username       TEXT    NOT NULL,
    password_enc   BLOB    NOT NULL,   -- Fernet-encrypted password (reversible;
                                        -- needed so the plaintext can be sent
                                        -- back out over MQTT after a match)
    embedding      BLOB    NOT NULL    -- float32 array, raw bytes
);

A local key file (faces.key) is generated next to the DB on first run and
used to encrypt/decrypt the password column. Keep that file safe — anyone
with it (and DB access) can recover the stored passwords.
"""

import sqlite3
import os

import faiss
import numpy as np
from cryptography.fernet import Fernet

from config import EMBEDDING_DIM, DATA_DIR


DB_FILE  = os.path.join(DATA_DIR, "faces.db")
KEY_FILE = os.path.join(DATA_DIR, "faces.key")


class FaceDatabase:
    def __init__(self, db_file: str = DB_FILE, dim: int = EMBEDDING_DIM, key_file: str = KEY_FILE):
        self.db_file  = db_file
        self.dim      = dim
        self.key_file = key_file
        os.makedirs(os.path.dirname(os.path.abspath(db_file)), exist_ok=True)

        self._fernet = Fernet(self._load_or_create_key())

        self.index:      faiss.IndexFlatIP = faiss.IndexFlatIP(dim)
        self.id_map:     list[str]         = []  #usernames, one entry per stored embedding
        self.pass_map:   list[str]         = []  #decrypted passwords, aligned with id_map
        self._init_db()
        self._load_from_db()  #always resets then populates from DB

    def _load_or_create_key(self) -> bytes:
        if os.path.exists(self.key_file):
            with open(self.key_file, "rb") as f:
                return f.read()
        key = Fernet.generate_key()
        with open(self.key_file, "wb") as f:
            f.write(key)
        try:
            os.chmod(self.key_file, 0o600)
        except OSError:
            pass
        print(f"[FaceDatabase] Generated new encryption key at {self.key_file}")
        return key

    def _encrypt(self, password: str) -> bytes:
        return self._fernet.encrypt(password.encode("utf-8"))

    def _decrypt(self, blob: bytes) -> str:
        return self._fernet.decrypt(blob).decode("utf-8")

    def _init_db(self):
        with self._connect() as conn:
            table_exists = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='embeddings'").fetchone() is not None
            if not table_exists:
                conn.execute("""
                                CREATE TABLE embeddings (
                                    id           INTEGER PRIMARY KEY AUTOINCREMENT,
                                    username     TEXT    NOT NULL,
                                    password_enc BLOB    NOT NULL,
                                    embedding    BLOB    NOT NULL
                                )
                            """)
                return

            existing = {row[1] for row in conn.execute("PRAGMA table_info(embeddings)")}

            legacy_person_id = "person_id" in existing
            wrong_shape = legacy_person_id or "username" not in existing or "password_enc" not in existing

            if not wrong_shape:
                return  

            #full rebuild 
            print("[FaceDatabase] Legacy schema detected — rebuilding embeddings table…")

            has_username = "username" in existing
            has_password = "password_enc" in existing

            username_expr = "username" if has_username else ("person_id" if legacy_person_id else "'unknown'")
            blank_pw = self._encrypt("")
            password_expr = "password_enc" if has_password else "?"

            conn.execute("ALTER TABLE embeddings RENAME TO embeddings_old")
            conn.execute("""
                            CREATE TABLE embeddings (
                                id           INTEGER PRIMARY KEY AUTOINCREMENT,
                                username     TEXT    NOT NULL,
                                password_enc BLOB    NOT NULL,
                                embedding    BLOB    NOT NULL
                            )
                        """)
            params = () if has_password else (blank_pw,)
            conn.execute(f"""INSERT INTO embeddings (id, username, password_enc, embedding) SELECT id, {username_expr}, {password_expr}, embedding FROM embeddings_old""", params)
            conn.execute("DROP TABLE embeddings_old")
            print("[FaceDatabase] Migration complete — re-enroll users to set passwords if they had none.")

    def add_embedding(self, embedding: np.ndarray, username:  str, password:  str,):
        vec = embedding.astype("float32")
        blob = vec.tobytes()
        pw_enc = self._encrypt(password)

        with self._connect() as conn:
            conn.execute("""INSERT INTO embeddings (username, password_enc, embedding) VALUES (?, ?, ?)""", (username, pw_enc, blob))

        vec_norm = vec.reshape(1, -1).copy()
        faiss.normalize_L2(vec_norm)
        self.index.add(vec_norm)
        self.id_map.append(username)
        self.pass_map.append(password)

    def search(self, embedding: np.ndarray, k: int = 1) -> tuple:
        if self.index.ntotal == 0:
            return None, None, None
        vec = embedding.astype("float32").reshape(1, -1).copy()
        faiss.normalize_L2(vec)
        D, I = self.index.search(vec, k)
        idx = I[0][0]
        return (float(D[0][0]), self.id_map[idx], self.pass_map[idx])

    def delete_person(self, username: str) -> int:
        with self._connect() as conn:
            cur = conn.execute("DELETE FROM embeddings WHERE username = ?", (username,))
            deleted = cur.rowcount
        if deleted:
            self._rebuild_index()
        return deleted

    def list_people(self) -> list[dict]:
        with self._connect() as conn:
            rows = conn.execute("""SELECT username, COUNT(*) as sample_count FROM embeddings GROUP BY username ORDER BY username""").fetchall()
        return [{"username": r[0], "sample_count": r[1]} for r in rows]

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self.db_file)

    def _load_from_db(self):
        self.index    = faiss.IndexFlatIP(self.dim)
        self.id_map   = []
        self.pass_map = []

        with self._connect() as conn:
            rows = conn.execute("""SELECT username, password_enc, embedding FROM embeddings ORDER BY id""").fetchall()
        if not rows:
            return
        vectors = []
        for username, pw_enc, blob in rows:
            vec = np.frombuffer(blob, dtype="float32").copy()
            vectors.append(vec)
            self.id_map.append(username)
            try:
                self.pass_map.append(self._decrypt(pw_enc))
            except Exception:
                # Row predates encryption / key mismatch — surface as empty
                # rather than crashing the whole DB load.
                self.pass_map.append("")
        matrix = np.stack(vectors).astype("float32")
        faiss.normalize_L2(matrix)
        self.index.add(matrix)
        print(f"[FaceDatabase] Loaded {len(rows)} embeddings from {self.db_file}")

    def _rebuild_index(self):
        self._load_from_db()