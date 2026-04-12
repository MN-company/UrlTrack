import getpass

from werkzeug.security import check_password_hash, generate_password_hash

from server import create_app
from server.extensions import db
from server.models import SetupState, User
from server.utils import generate_secret_code


def _setup_state():
    state = db.session.get(SetupState, 1)
    if state is None:
        state = SetupState(id=1, setup_completed=False)
        db.session.add(state)
        db.session.commit()
    return state


def _prompt_password():
    while True:
        password = getpass.getpass("Password (min 12 chars): ")
        if len(password) < 12:
            print("Password must be at least 12 characters long.")
            continue
        confirm = getpass.getpass("Confirm password: ")
        if password != confirm:
            print("Passwords do not match.")
            continue
        return password


def main():
    app = create_app()
    with app.app_context():
        state = _setup_state()
        email = input("Admin email: ").strip().lower()
        username = input("Display name (optional): ").strip()
        password = _prompt_password()

        if User.query.count() == 0:
            secret_code = generate_secret_code()
            state.setup_completed = True
            state.admin_secret_hash = generate_password_hash(secret_code)
            user = User(
                email=email,
                username=username or email.split("@", 1)[0],
                password_hash=generate_password_hash(password),
            )
            db.session.add(user)
            db.session.commit()
            print("First admin created successfully.")
            print("Store this server secret code securely:")
            print(secret_code)
            return

        if not state.admin_secret_hash:
            print("No admin secret is configured. Use the web bootstrap first.")
            return

        secret_code = getpass.getpass("Server secret code: ")
        if not check_password_hash(state.admin_secret_hash, secret_code):
            print("Invalid server secret code.")
            return

        if User.query.filter_by(email=email).first():
            print("An admin with that email already exists.")
            return

        user = User(
            email=email,
            username=username or email.split("@", 1)[0],
            password_hash=generate_password_hash(password),
        )
        db.session.add(user)
        db.session.commit()
        print("Admin created successfully.")


if __name__ == "__main__":
    main()
