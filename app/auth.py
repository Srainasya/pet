from flask import Blueprint, redirect, url_for, current_app, session
from flask_login import login_user, logout_user, current_user
from authlib.integrations.flask_client import OAuth
from .extensions import db
from .models import User, LoginLog
from datetime import date as _date


bp = Blueprint("auth", __name__, url_prefix="/auth")

oauth = OAuth()
google = None

@bp.before_app_request
def setup_oauth():
    global google
    if google is not None:
        return
    oauth.init_app(current_app)
    google = oauth.register(
        name="google",
        client_id=current_app.config["GOOGLE_CLIENT_ID"],
        client_secret=current_app.config["GOOGLE_CLIENT_SECRET"],
        server_metadata_url="https://accounts.google.com/.well-known/openid-configuration",
        client_kwargs={"scope": "openid email profile"},
    )

@bp.get("/login")
def login():
    redirect_uri = current_app.config.get("OAUTH_REDIRECT_URL") or url_for("auth.google_callback", _external=True)
    return google.authorize_redirect(redirect_uri)

@bp.get("/google/callback")
def google_callback():
    token = google.authorize_access_token()
    userinfo = token.get("userinfo")
    if not userinfo:
        userinfo = google.parse_id_token(token)

    google_sub = userinfo.get("sub")
    email      = userinfo.get("email")
    name       = userinfo.get("name")
    avatar     = userinfo.get("picture")

    user = User.query.filter_by(google_sub=google_sub).first()
    if not user:
        user = User(google_sub=google_sub, email=email, name=name, avatar_url=avatar)
        db.session.add(user)
    else:
        user.email     = email
        user.name      = name
        user.avatar_url = avatar

    # ── 連續登入 & 陪伴天數 ──
    today = _date.today()
    if user.last_login_date is None:
        user.streak_days    = 1
        user.companion_days = 1
    elif user.last_login_date == today:
        pass  # 今天已登入過，不重算
    elif (today - user.last_login_date).days == 1:
        user.streak_days    += 1
        user.companion_days += 1
    else:
        user.streak_days    = 1
        user.companion_days += 1
    user.last_login_date = today

    # ── LoginLog（每天只寫一次，供 heatmap 使用）──
    # user.id 在 flush 後才有值（新用戶），所以先 flush
    db.session.flush()
    existing_log = LoginLog.query.filter_by(user_id=user.id, login_date=today).first()
    if not existing_log:
        db.session.add(LoginLog(user_id=user.id, login_date=today))

    db.session.commit()
    login_user(user)

    if not user.onboarding_done:
        return redirect(url_for("onboarding.start"))

    return redirect(url_for("patient.farm"))

@bp.get("/logout")
def logout():
    logout_user()
    session.clear()
    response = redirect("/auth/login")
    response.delete_cookie("session")
    return response