import datetime as dt
import random
import os
from flask import Blueprint, jsonify, request, current_app, url_for
from flask_login import login_required, current_user

from .extensions import db
from .models import GroupMember, DailyRecord, MoodEntry, Photo, UserDailyProgress, QAEntry, DailyTask, User
from flask import send_file
from werkzeug.exceptions import NotFound, Forbidden
from werkzeug.utils import secure_filename
import hashlib
from datetime import timezone, timedelta

TW = timezone(timedelta(hours=8))

def now_tw():
    return dt.datetime.now(TW).replace(tzinfo=None)

bp = Blueprint("api", __name__, url_prefix="/api")

TASK_POOL = [
    "陪失智者打電話 10 分鐘",
    "陪失智者出門散步 15 分鐘",
    "陪失智者拼拼圖 10 分鐘",
    "陪失智者看過往照片/影片回憶 10 分鐘",
]


# ───────────────────────── helpers ─────────────────────────

def pick_task_for_today():
    return random.choice(TASK_POOL)


def _is_role(role: str) -> bool:
    m = GroupMember.query.filter_by(user_id=current_user.id).first()
    return bool(m and m.role == role)


def _pick_task_for(group_id: int, date: dt.date, caregiver_user_id: int) -> str:
    key = f"{group_id}:{date.isoformat()}:{caregiver_user_id}".encode("utf-8")
    h = hashlib.sha256(key).hexdigest()
    idx = int(h[:8], 16) % len(TASK_POOL)
    return TASK_POOL[idx]


def get_group_id_for_user():
    m = GroupMember.query.filter_by(user_id=current_user.id).first()
    return m.group_id if m else None


def get_my_member():
    return GroupMember.query.filter_by(user_id=current_user.id).first()


def get_or_create_daily_record(group_id: int, date: dt.date) -> DailyRecord:
    dr = DailyRecord.query.filter_by(group_id=group_id, date=date).first()
    if not dr:
        dr = DailyRecord(group_id=group_id, date=date)
        db.session.add(dr)
        db.session.commit()
    return dr


def get_or_create_user_progress(daily_record_id: int, user_id: int) -> UserDailyProgress:
    p = UserDailyProgress.query.filter_by(daily_record_id=daily_record_id, user_id=user_id).first()
    if not p:
        p = UserDailyProgress(daily_record_id=daily_record_id, user_id=user_id)
        db.session.add(p)
        db.session.commit()
    return p


def get_or_create_daily_task(daily_record_id: int, caregiver_user_id: int, group_id: int, date: dt.date) -> DailyTask:
    t = DailyTask.query.filter_by(daily_record_id=daily_record_id, caregiver_user_id=caregiver_user_id).first()
    if not t:
        t = DailyTask(
            daily_record_id=daily_record_id,
            caregiver_user_id=caregiver_user_id,
            task_text=_pick_task_for(group_id, date, caregiver_user_id),
        )
        db.session.add(t)
        db.session.commit()
    return t


# ───────────────────────── tasks ─────────────────────────

@bp.get("/tasks/today")
@login_required
def tasks_today():
    group_id = get_group_id_for_user()
    if not group_id:
        return jsonify({"error": "no_group"}), 400

    today = dt.date.today()
    dr = get_or_create_daily_record(group_id, today)

    m = GroupMember.query.filter_by(user_id=current_user.id).first()
    role = m.role if m else None
    if role != "caregiver":
        return jsonify({"error": "forbidden"}), 403

    t = DailyTask.query.filter_by(
        daily_record_id=dr.id,
        caregiver_user_id=current_user.id
    ).first()

    if not t:
        t = DailyTask(
            daily_record_id=dr.id,
            caregiver_user_id=current_user.id,
            task_text=pick_task_for_today(),
            caregiver_done=False,
            patient_confirmed=False,
        )
        db.session.add(t)
        db.session.commit()

    completed = bool(t.caregiver_done and t.patient_confirmed)
    ts = t.updated_at or t.created_at

    return jsonify({
        "task_id":              t.id,
        "task_text":            t.task_text,
        "caregiver_done":       bool(t.caregiver_done),
        "patient_confirmed":    bool(t.patient_confirmed),
        "completed":            completed,
        "updated_at": ts.isoformat() if ts else None,
        "caregiver_done_at":    t.caregiver_done_at.isoformat()    if t.caregiver_done_at    else None,
        "patient_confirmed_at": t.patient_confirmed_at.isoformat() if t.patient_confirmed_at else None,
    })


@bp.post("/tasks/complete")
@login_required
def tasks_complete():
    if not _is_role("caregiver"):
        return jsonify({"error": "forbidden"}), 403

    group_id = get_group_id_for_user()
    if not group_id:
        return jsonify({"error": "no_group"}), 400

    today = dt.date.today()
    dr = get_or_create_daily_record(group_id, today)
    task = get_or_create_daily_task(dr.id, current_user.id, group_id, today)

    task.caregiver_done    = True
    task.caregiver_done_at = now_tw()
    db.session.commit()

    return jsonify({"ok": True, "caregiver_done": True})


@bp.get("/tasks/pending_confirmations")
@login_required
def tasks_pending_confirmations():
    m = get_my_member()
    if not m:
        return jsonify({"error": "no_group"}), 400

    if m.role != "patient":
        return jsonify({"error": "forbidden"}), 403

    today = dt.date.today()
    dr = DailyRecord.query.filter_by(group_id=m.group_id, date=today).first()
    if not dr:
        return jsonify({"items": []})

    tasks = (
        DailyTask.query
        .filter_by(daily_record_id=dr.id)
        .filter(DailyTask.caregiver_done == True)
        .filter(DailyTask.patient_confirmed == False)
        .order_by(DailyTask.updated_at.desc())
        .all()
    )

    items = []
    for t in tasks:
        caregiver = User.query.get(t.caregiver_user_id)
        ts = t.updated_at or t.created_at
        items.append({
            "task_id":           t.id,
            "task_text":         t.task_text,
            "caregiver_user_id": t.caregiver_user_id,
            "caregiver_name":    caregiver.name if caregiver else f"User {t.caregiver_user_id}",
            "avatar_url":        caregiver.avatar_url if caregiver else None,
            "updated_at": ts.isoformat() if ts else None,
        })

    return jsonify({"items": items})


@bp.post("/tasks/confirm")
@login_required
def tasks_confirm():
    if not _is_role("patient"):
        return jsonify({"error": "forbidden"}), 403

    data = request.get_json(force=True)
    task_id = int(data.get("task_id") or 0)
    if task_id <= 0:
        return jsonify({"error": "invalid_task_id"}), 400

    group_id = get_group_id_for_user()
    if not group_id:
        return jsonify({"error": "no_group"}), 400

    task = DailyTask.query.get(task_id)
    if not task:
        return jsonify({"error": "not_found"}), 404

    dr = DailyRecord.query.get(task.daily_record_id)
    if not dr or dr.group_id != group_id:
        return jsonify({"error": "forbidden"}), 403

    if not task.caregiver_done:
        return jsonify({"error": "caregiver_not_done"}), 400

    task.patient_confirmed    = True
    task.patient_confirmed_at = now_tw()
    db.session.commit()
    return jsonify({"ok": True, "patient_confirmed": True})


# ───────────────────────── today_status ─────────────────────────

@bp.get("/patient/today_status")
@login_required
def patient_today_status():
    group_id = get_group_id_for_user()
    if not group_id:
        return jsonify({"error": "no_group"}), 400

    today = dt.date.today()
    dr = get_or_create_daily_record(group_id, today)

    gm = GroupMember.query.filter_by(user_id=current_user.id).first()
    role = gm.role if gm else None

    photo_done = Photo.query.filter_by(daily_record_id=dr.id).count() > 0
    qa_done = QAEntry.query.filter_by(daily_record_id=dr.id, user_id=current_user.id).first() is not None

    progress = get_or_create_user_progress(dr.id, current_user.id)

    mood = MoodEntry.query.filter_by(daily_record_id=dr.id, user_id=current_user.id).first()
    mood_done = mood is not None

    if role == "caregiver":
        t = DailyTask.query.filter_by(
            daily_record_id=dr.id,
            caregiver_user_id=current_user.id
        ).first()
        task_done = bool(t and t.caregiver_done and t.patient_confirmed)
    else:
        task_done = True

    if not mood_done:
        next_action = "mood"
    elif not photo_done:
        next_action = "photos"
    elif not qa_done:
        next_action = "qa"
    elif not task_done:
        next_action = "tasks"
    else:
        next_action = "pet"

    done = int(photo_done) + int(mood_done) + int(qa_done) + int(task_done)

    return jsonify({
        "photo_done":       photo_done,
        "qa_done":          qa_done,
        "role":             role,
        "mood_done":        mood_done,
        "mood":             mood.mood if mood else None,
        "task_done":        task_done,
        "pet_xp":           progress.pet_xp,
        "pet_level":        progress.pet_level,
        "farm_state":       progress.farm_state,
        "streak_days":      current_user.streak_days    or 0,
        "companion_days":   current_user.companion_days or 0,
        "today_progress":   done,
        "next_action":      next_action,
        "vapid_public_key": current_app.config.get("VAPID_PUBLIC_KEY", ""),
    })


# ───────────────────────── pet xp ─────────────────────────

@bp.post("/pet/add_xp")
@login_required
def pet_add_xp():
    data = request.get_json(force=True)
    add = int(data.get("xp") or 0)

    group_id = get_group_id_for_user()
    if not group_id:
        return jsonify({"error": "no_group"}), 400

    today = dt.date.today()
    dr = get_or_create_daily_record(group_id, today)
    progress = get_or_create_user_progress(dr.id, current_user.id)

    progress.pet_xp = max(0, progress.pet_xp + add)
    db.session.commit()
    return jsonify({"ok": True, "pet_xp": progress.pet_xp, "pet_level": progress.pet_level})


# ───────────────────────── mood ─────────────────────────

@bp.post("/mood")
@login_required
def post_mood():
    data = request.get_json(force=True)
    mood = (data.get("mood") or "").strip().lower()

    allowed = {"happy", "neutral", "sad", "angry"}
    if mood not in allowed:
        return jsonify({"error": "invalid_mood"}), 400

    group_id = get_group_id_for_user()
    if not group_id:
        return jsonify({"error": "no_group"}), 400

    today = dt.date.today()
    dr = get_or_create_daily_record(group_id, today)

    me = MoodEntry.query.filter_by(daily_record_id=dr.id, user_id=current_user.id).first()
    if not me:
        me = MoodEntry(daily_record_id=dr.id, user_id=current_user.id, mood=mood)
        db.session.add(me)
    else:
        me.mood = mood

    db.session.commit()
    return jsonify({"ok": True, "mood": mood})


# ───────────────────────── push ─────────────────────────

_SUBS = {}

@bp.post("/push/subscribe")
@login_required
def push_subscribe():
    sub = request.get_json(force=True)
    _SUBS[current_user.id] = sub
    return jsonify({"ok": True})


@bp.get("/push/debug_sub")
@login_required
def push_debug_sub():
    return jsonify({"has": current_user.id in _SUBS})


# ───────────────────────── photos ─────────────────────────

@bp.get("/photos")
@login_required
def list_photos():
    group_id = get_group_id_for_user()
    if not group_id:
        return jsonify({"error": "no_group"}), 400

    date_str = request.args.get("date")
    if date_str:
        try:
            target_date = dt.date.fromisoformat(date_str)
        except ValueError:
            return jsonify({"error": "invalid_date"}), 400
    else:
        target_date = dt.date.today()

    dr = get_or_create_daily_record(group_id, target_date)

    photos = (Photo.query
              .filter_by(daily_record_id=dr.id)
              .order_by(Photo.created_at.desc())
              .all())

    items = []
    for p in photos:
        items.append({
            "id":               p.id,
            "url":              url_for("api.photo_file", photo_id=p.id),
            "original_name":    p.original_name,
            "uploader_user_id": p.uploader_user_id,
            "created_at":       p.created_at.isoformat(),
        })

    return jsonify({"date": target_date.isoformat(), "items": items})


@bp.get("/photos/<int:photo_id>/file")
@login_required
def photo_file(photo_id: int):
    group_id = get_group_id_for_user()
    if not group_id:
        raise Forbidden()

    p = Photo.query.get(photo_id)
    if not p:
        raise NotFound()

    if p.group_id != group_id:
        raise Forbidden()

    return send_file(p.stored_path)


@bp.post("/photos/upload")
@login_required
def upload_photo():
    group_id = get_group_id_for_user()
    if not group_id:
        return jsonify({"error": "no_group"}), 400

    f = request.files.get("file")
    if not f:
        return jsonify({"error": "no_file"}), 400

    date_str = request.form.get("date")
    if date_str:
        try:
            target_date = dt.date.fromisoformat(date_str)
        except ValueError:
            return jsonify({"error": "invalid_date"}), 400
    else:
        target_date = dt.date.today()

    dr = get_or_create_daily_record(group_id, target_date)

    # 🛠️ 修正 1：指定存到 static/uploads 資料夾
    upload_dir = os.path.join(current_app.root_path, "static", "uploads")
    os.makedirs(upload_dir, exist_ok=True)

    original_name = f.filename or "upload"
    safe = secure_filename(original_name)
    stamp = now_tw().strftime("%Y%m%d_%H%M%S_%f")
    filename = f"{group_id}_{target_date.isoformat()}_{stamp}_{safe}"
    
    # 電腦實體儲存路徑
    save_path = os.path.join(upload_dir, filename)
    f.save(save_path)

    # 🛠️ 修正 2：存進資料庫的路徑，只要相對於 static 的乾淨字串
    # 這裡必須用正斜線，確保網頁能正常讀取
    db_path = f"uploads/{filename}"

    p = Photo(
        group_id=group_id,
        daily_record_id=dr.id,
        uploader_user_id=current_user.id,
        stored_path=db_path,  # ✅ 存入乾淨的相對路徑
        original_name=original_name,
    )
    db.session.add(p)
    db.session.commit()

    return jsonify({
        "ok":         True,
        "id":         p.id,
        "url":        url_for('static', filename=db_path), # ✅ 回傳正確網址
        "created_at": p.created_at.isoformat(),
    })


# ───────────────────────── QA ─────────────────────────

@bp.get("/qa/today")
@login_required
def qa_today():
    group_id = get_group_id_for_user()
    if not group_id: return jsonify({"error": "no_group"}), 400

    today = dt.date.today()
    dr = get_or_create_daily_record(group_id, today)

    # 🌟 修正點 1：改用 created_at 排序，保證資料庫絕對找得到這個欄位！
    items = (QAEntry.query
             .filter_by(daily_record_id=dr.id)
             .order_by(QAEntry.created_at.desc()) 
             .all())

    question = items[0].question if items else "今天讓你覺得最溫暖的一件事是什麼？"

    item_list = []
    for x in items:
        # 🌟 修正點 2：防呆機制，不管資料庫叫 created_at 還是 updated_at 都能抓到
        ts = getattr(x, 'updated_at', None) or getattr(x, 'created_at', None)
        u = db.session.get(User, x.user_id) 
        
        item_list.append({
            "id": x.id,
            "user_id": x.user_id,
            "user_name": u.name if u else f"User {x.user_id}",
            "avatar_url": u.avatar_url if u else None,
            "answer": x.answer,
            "updated_at": ts.isoformat() if ts else None,
            "is_me": (x.user_id == current_user.id),
        })

    return jsonify({"date": today.isoformat(), "question": question, "items": item_list})


@bp.post("/qa/answer")
@login_required
def qa_answer():
    data = request.get_json(force=True)
    answer = (data.get("answer") or "").strip()
    question = (data.get("question") or "").strip() or "今天讓你覺得最溫暖的一件事是什麼？"

    if not answer:
        return jsonify({"error": "empty_answer"}), 400

    group_id = get_group_id_for_user()
    if not group_id:
        return jsonify({"error": "no_group"}), 400

    today = dt.date.today()
    dr = get_or_create_daily_record(group_id, today)

    me = QAEntry.query.filter_by(daily_record_id=dr.id, user_id=current_user.id).first()
    if not me:
        me = QAEntry(daily_record_id=dr.id, user_id=current_user.id, question=question, answer=answer)
        db.session.add(me)
    else:
        me.question = question
        me.answer = answer

    db.session.commit()
    return jsonify({"ok": True})


# ───────────────────────── stats ─────────────────────────

@bp.get("/stats")
@login_required
def stats():
    from .models import LoginLog
    today = dt.date.today()

    start_str  = request.args.get("start")
    end_str    = request.args.get("end")
    days_param = request.args.get("days", 30, type=int)

    if start_str and end_str:
        try:
            since = dt.date.fromisoformat(start_str)
            today = dt.date.fromisoformat(end_str)
        except ValueError:
            since = today - timedelta(days=29)
    else:
        if days_param not in (7, 30, 365):
            days_param = 30
        since = today - timedelta(days=days_param - 1)

    group_id = get_group_id_for_user()

    # 找同組的 patient user_id（心情只看 patient 的）
    patient_member = GroupMember.query.filter_by(
        group_id=group_id, role="patient"
    ).first()
    patient_user_id = patient_member.user_id if patient_member else current_user.id

    mood_rows = (
        db.session.query(MoodEntry.created_at, MoodEntry.mood)
        .join(DailyRecord, MoodEntry.daily_record_id == DailyRecord.id)
        .filter(
            MoodEntry.user_id == patient_user_id,
            DailyRecord.date >= since,
            DailyRecord.date <= today,
        )
        .order_by(DailyRecord.date.asc())
        .all()
    )

    mood_map  = {"happy": 4, "neutral": 3, "sad": 2, "angry": 1}
    mood_data = [
        {"date": str(r.created_at)[:10], "score": mood_map.get(r.mood, 0)}
        for r in mood_rows
    ]

    week_tasks = []
    real_today = dt.date.today()
    for w in range(7, -1, -1):
        week_start = real_today - timedelta(days=real_today.weekday() + 7 * w)
        week_end   = week_start + timedelta(days=6)
        label      = week_start.strftime("%m/%d")

        total = (
            DailyTask.query
            .join(DailyRecord, DailyTask.daily_record_id == DailyRecord.id)
            .filter(
                DailyTask.caregiver_user_id == current_user.id,
                DailyRecord.date >= week_start,
                DailyRecord.date <= week_end,
            ).count()
        )
        done = (
            DailyTask.query
            .join(DailyRecord, DailyTask.daily_record_id == DailyRecord.id)
            .filter(
                DailyTask.caregiver_user_id == current_user.id,
                DailyTask.caregiver_done == True,
                DailyTask.patient_confirmed == True,
                DailyRecord.date >= week_start,
                DailyRecord.date <= week_end,
            ).count()
        )
        rate = round(done / total * 100) if total > 0 else 0
        week_tasks.append({"week": label, "rate": rate, "done": done, "total": total})

    year_ago = real_today - timedelta(days=364)
    logs = (
        LoginLog.query
        .filter(
            LoginLog.user_id == current_user.id,
            LoginLog.login_date >= year_ago,
        )
        .all()
    )
    login_dates = [str(l.login_date) for l in logs]

    return jsonify({
        "mood_data":      mood_data,
        "week_tasks":     week_tasks,
        "login_dates":    login_dates,
        "streak_days":    current_user.streak_days    or 0,
        "companion_days": current_user.companion_days or 0,
    })