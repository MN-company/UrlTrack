from . import create_app
from .extensions import db

def main():
    app = create_app()
    print("Initializing Database...")
    with app.app_context():
        db.create_all()
        print("Database initialized successfully.")


if __name__ == '__main__':
    main()
