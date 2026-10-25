from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from flask_wtf.csrf import CSRFProtect
from flask_mail import Mail
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_talisman import Talisman
from apscheduler.schedulers.background import BackgroundScheduler

db = SQLAlchemy()
login_manager = LoginManager()
csrf = CSRFProtect()
mail = Mail()
limiter = Limiter(key_func=get_remote_address)
talisman = Talisman()
scheduler = BackgroundScheduler()

# In-memory token blacklist for JWT revocation (logout)
# In production, use Redis or a database-backed blacklist
token_blacklist = set()
