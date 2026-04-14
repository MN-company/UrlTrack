import queue

from flask_caching import Cache
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_login import LoginManager
from flask_migrate import Migrate
from flask_sqlalchemy import SQLAlchemy
from flask_wtf.csrf import CSRFProtect


db = SQLAlchemy()
cache = Cache()
migrate = Migrate()
login_manager = LoginManager()
limiter = Limiter(key_func=get_remote_address, storage_uri="memory://")
csrf = CSRFProtect()
log_queue = queue.Queue()
