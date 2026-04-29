from flask import Flask, redirect, url_for
from flask_login import current_user
from .config import Config
from .extensions import db, login_manager   # ✅ 拿掉 migrate
from .models import User

def create_app():
    app = Flask(__name__, static_folder="static", template_folder="templates")
    app.config.from_object(Config)

    # ✅ SQLite 開發模式：初始化 DB + 自動建表（不用 migrations）
    db.init_app(app)
    login_manager.init_app(app)

    with app.app_context():
        db.create_all()

    from .auth import bp as auth_bp
    from .onboarding import bp as onboarding_bp
    from .patient import bp as patient_bp
    from .caregiver import bp as caregiver_bp
    from .api import bp as api_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(onboarding_bp)
    app.register_blueprint(patient_bp)
    app.register_blueprint(caregiver_bp)
    app.register_blueprint(api_bp)

    @app.get("/")
    def index():
        if not current_user.is_authenticated:
            return redirect(url_for("auth.login"))
        if not getattr(current_user, "onboarding_done", False):
            return redirect(url_for("onboarding.start"))
        return redirect(url_for("patient.farm"))

    @login_manager.user_loader
    def load_user(user_id: str):
        # SQLAlchemy 2.x 建議用 db.session.get
        return db.session.get(User, int(user_id))

    return app