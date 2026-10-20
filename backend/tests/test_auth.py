"""Login and per-user isolation. Needs `httpx` for FastAPI's TestClient (python3 -m pip install httpx)."""
import os
import tempfile
import unittest

try:
    from fastapi.testclient import TestClient
except Exception:  # httpx not installed
    TestClient = None

from app import auth, db


@unittest.skipIf(TestClient is None, "pip install httpx to run the login tests")
class Login(unittest.TestCase):
    def setUp(self):
        fd, path = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        self.path = path
        self.old = db.DB_PATH
        db.DB_PATH = type(db.DB_PATH)(path)
        auth._fails.clear()
        from app.main import app
        self.app = app

    def tearDown(self):
        db.DB_PATH = self.old
        os.remove(self.path)

    def client(self):
        c = TestClient(self.app)
        c.__enter__()  # runs startup (creates tables)
        self.addCleanup(c.__exit__, None, None, None)
        return c

    def test_password_hash(self):
        h = auth.hash_password("correct horse")
        self.assertNotIn("correct horse", h)
        self.assertTrue(auth.verify_password("correct horse", h))
        self.assertFalse(auth.verify_password("wrong", h))

    def test_must_log_in(self):
        c = self.client()
        self.assertEqual(c.get("/api/packets").status_code, 401)
        self.assertEqual(c.post("/api/handoff", json={"packet": {}}).status_code, 401)
        self.assertEqual(c.get("/api/health").status_code, 200)

    def test_users_are_separate(self):
        a, b = self.client(), self.client()
        self.assertEqual(a.post("/api/auth/register", json={"username": "asha", "password": "password-a"}).status_code, 200)
        self.assertEqual(b.post("/api/auth/register", json={"username": "ravi", "password": "password-b"}).status_code, 200)
        pa = a.post("/api/packets", json={"title": "Asha's notes"}).json()
        titles_b = [p["title"] for p in b.get("/api/packets").json()]
        self.assertNotIn("Asha's notes", titles_b)
        self.assertEqual(b.get("/api/packets/" + pa["id"]).status_code, 404)
        self.assertEqual(b.put("/api/packets/" + pa["id"], json={"title": "hacked"}).status_code, 404)
        self.assertEqual(b.delete("/api/packets/" + pa["id"]).status_code, 404)
        self.assertEqual(a.get("/api/packets/" + pa["id"]).json()["title"], "Asha's notes")

    def test_unique_username_and_rules(self):
        c = self.client()
        self.assertEqual(c.post("/api/auth/register", json={"username": "Asha", "password": "password-a"}).status_code, 200)
        self.assertEqual(c.post("/api/auth/register", json={"username": "asha", "password": "password-x"}).status_code, 409)
        self.assertEqual(c.post("/api/auth/register", json={"username": "x", "password": "password-x"}).status_code, 400)
        self.assertEqual(c.post("/api/auth/register", json={"username": "neha", "password": "short"}).status_code, 400)

    def test_login_logout_and_lockout(self):
        c = self.client()
        c.post("/api/auth/register", json={"username": "asha", "password": "password-a"})
        c.post("/api/auth/logout")
        self.assertEqual(c.get("/api/auth/me").status_code, 401)
        self.assertEqual(c.post("/api/auth/login", json={"username": "ASHA", "password": "password-a"}).status_code, 200)
        self.assertEqual(c.get("/api/auth/me").json()["username"], "asha")
        for _ in range(auth.MAX_FAILS):
            self.assertEqual(c.post("/api/auth/login", json={"username": "asha", "password": "nope-nope"}).status_code, 401)
        self.assertEqual(c.post("/api/auth/login", json={"username": "asha", "password": "password-a"}).status_code, 429)


if __name__ == "__main__":
    unittest.main()
