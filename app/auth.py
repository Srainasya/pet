from flask import Blueprint, redirect, url_for, current_app, session
from flask_login import login_user, logout_user, current_user
from authlib.integrations.flask_client import OAuth
from .extensions import db
from .models import User

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
    # 直接走 Google
    redirect_uri = current_app.config.get("OAUTH_REDIRECT_URL") or url_for("auth.google_callback", _external=True)
    # 🌟 新增 prompt="select_account"，強制要求選擇帳號，不要自動登入
    return google.authorize_redirect(redirect_uri, prompt="select_account")

@bp.get("/google/callback")
def google_callback():
    token = google.authorize_access_token()
    userinfo = token.get("userinfo")
    if not userinfo:
        # fallback: fetch userinfo endpoint
        userinfo = google.parse_id_token(token)

    google_sub = userinfo.get("sub")
    email = userinfo.get("email")
    name = userinfo.get("name")
    avatar = userinfo.get("picture")

    user = User.query.filter_by(google_sub=google_sub).first()
    if not user:
        user = User(google_sub=google_sub, email=email, name=name, avatar_url=avatar)
        db.session.add(user)
    else:
        # 更新 profile
        user.email = email
        user.name = name
        user.avatar_url = avatar

    db.session.commit()
    login_user(user)

    # onboarding 未完成 → onboarding
    if not user.onboarding_done:
        return redirect(url_for("onboarding.start"))

    # ✅ 不分角色，一律進入農場主頁
    return redirect(url_for("patient.farm"))

@bp.get("/logout")
def logout():
    logout_user()
    return redirect("/")