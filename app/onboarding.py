from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user
from .extensions import db
from .models import Group, GroupMember

bp = Blueprint("onboarding", __name__, url_prefix="/onboarding")


def get_primary_membership(user_id: int):
    return GroupMember.query.filter_by(user_id=user_id).first()


@bp.get("")
@login_required
def start():
    return render_template("onboarding.html")


@bp.post("/submit")
@login_required
def submit():
    role = request.form.get("role")  # patient / caregiver
    mode = request.form.get("mode")  # create / join
    invite_code = (request.form.get("invite_code") or "").strip().upper()
    family_name = (request.form.get("family_name") or "").strip() or "My Family"

    if role not in ("patient", "caregiver"):
        flash("請選擇身分")
        return redirect(url_for("onboarding.start"))

    # 先檢查使用者是否已經加入過家庭
    existing_membership = get_primary_membership(current_user.id)
    if existing_membership:
        flash("你已經加入家庭，無法再次建立或加入其他家庭")
        return redirect(url_for("onboarding.route_after_login"))

    if mode == "create":
        group = Group(
            name=family_name,
            invite_code=Group.new_invite_code()
        )
        db.session.add(group)
        db.session.flush()

        m = GroupMember(
            group_id=group.id,
            user_id=current_user.id,
            role=role
        )
        db.session.add(m)

        current_user.onboarding_done = True
        db.session.commit()

        flash(f"家庭建立成功，你的邀請碼是：{group.invite_code}")
        return redirect(url_for("onboarding.route_after_login"))

    elif mode == "join":
        if not invite_code:
            flash("請輸入邀請碼")
            return redirect(url_for("onboarding.start"))

        group = Group.query.filter_by(invite_code=invite_code).first()
        if not group:
            flash("邀請碼不存在，請確認後再試一次")
            return redirect(url_for("onboarding.start"))

        m = GroupMember(
            group_id=group.id,
            user_id=current_user.id,
            role=role
        )
        db.session.add(m)

        current_user.onboarding_done = True
        db.session.commit()

        flash(f"已成功加入家庭：{group.name}")
        return redirect(url_for("onboarding.route_after_login"))

    else:
        flash("請選擇建立或加入家庭")
        return redirect(url_for("onboarding.start"))


@bp.get("/route")
@login_required
def route_after_login():
    return redirect(url_for("patient.farm"))