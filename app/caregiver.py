from flask import Blueprint, render_template, redirect, url_for
from flask_login import login_required, current_user
from .models import GroupMember

bp = Blueprint("caregiver", __name__, url_prefix="/caregiver")

def my_role():
    m = GroupMember.query.filter_by(user_id=current_user.id).first()
    return m.role if m else None

@bp.get("/tasks")
@login_required
def tasks():
    if my_role() != "caregiver":
        return redirect(url_for("patient.farm"))
    return render_template("caregiver_tasks.html")