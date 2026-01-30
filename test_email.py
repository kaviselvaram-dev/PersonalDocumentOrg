# test_email.py
from utils import send_email

if __name__ == "__main__":
    print("Running standalone email test...")
    ok = send_email("ramkavi1905@gmail.com", "Flyvia Docs SMTP test", "Hello — this proves SMTP is working.")
    print("Result:", ok)
