import pytest
from app import app, db
from models import User, Document
from datetime import datetime, timedelta

@pytest.fixture
def client():
    app.config["TESTING"] = True
    app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///:memory:"
    with app.test_client() as client:
        with app.app_context():
            db.create_all()
        yield client
        with app.app_context():
            db.drop_all()

# ----------------------------
# 🧪 BLACK BOX TESTS
# ----------------------------
'''Test Case: User should be able to successfully sign up 
    with a valid email and password.'''

def test_signup_success(client):
    response = client.post("/signup", data={"email": "test@example.com", "password": "1234"})
    assert response.status_code == 201
    assert b"registered" in response.data
    
'''Test Case: Signing up with an already registered email 
    should return an error.'''

def test_signup_existing_email(client):
    client.post("/signup", data={"email": "test@example.com", "password": "1234"})
    response = client.post("/signup", data={"email": "test@example.com", "password": "abcd"})
    assert response.status_code == 400
    assert b"exists" in response.data
'''Test Case: User should be able to log in with correct credentials.'''
def test_login_success(client):
    client.post("/signup", data={"email": "user@example.com", "password": "pass"})
    response = client.post("/login", data={"email": "user@example.com", "password": "pass"})
    assert response.status_code == 200
    assert b"logged in" in response.data
'''Test Case: Login should fail if user provides wrong credentials'''
def test_login_invalid(client):
    client.post("/signup", data={"email": "user@example.com", "password": "pass"})
    response = client.post("/login", data={"email": "user@example.com", "password": "wrong"})
    assert response.status_code == 401
    assert b"invalid credentials" in response.data
    
'''Test Case: Uploading without a file should return an error.'''

def test_upload_without_file(client):
    client.post("/signup", data={"email": "user@example.com", "password": "pass"})
    client.post("/login", data={"email": "user@example.com", "password": "pass"})
    response = client.post("/upload", data={})
    assert response.status_code == 400
    assert b"no file" in response.data
