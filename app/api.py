import datetime as dt
import random
import os
from flask import Blueprint, jsonify, request, current_app
from flask_login import login_required, current_user

from .extensions import db
from .models import GroupMember, DailyRecord, MoodEntry, Photo, UserDailyProgress, QAEntry , DailyTask, User
from flask import send_file
from werkzeug.exceptions import NotFound, Forbidden
from werkzeug.utils import secure_filename
import hashlib

bp = Blueprint("api", __name__, url_prefix="/api")

TASK_POOL = [
    "陪失智者打電話 10 分鐘",
    "陪失智者出門散步 15 分鐘",
    "陪失智者拼拼圖 10 分鐘",
    "陪失智者看過往照片/影片回憶 10 分鐘",
]

def pick_task_for_today():
    # 最簡：隨機挑（你要 deterministic 再改）
    import random
    return random.choice(TASK_POOL)

def get_or_create_daily_record(group_id: int, day: dt.date) -> DailyRecord:
    dr = DailyRecord.query.filter_by(group_id=group_id, date=day).first()
    if dr:
        return dr
    dr = DailyRecord(group_id=group_id, date=day)
    db.session.add(dr)
    db.session.commit()
    return dr

def _is_role(role: str) -> bool:
    m = GroupMember.query.filter_by(user_id=current_user.id).first()
    return bool(m and m.role == role)

def _pick_task_for(group_id: int, date: dt.date, caregiver_user_id: int) -> str:
    key = f"{group_id}:{date.isoformat()}:{caregiver_user_id}".encode("utf-8")
    h = hashlib.sha256(key).hexdigest()
    idx = int(h[:8], 16) % len(TASK_POOL)
    return TASK_POOL[idx]

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

def _update_reward_if_completed(progress: UserDailyProgress, photo_done: bool, mood_done: bool, qa_done: bool, task_done: bool):
    done = sum([photo_done, mood_done, qa_done, task_done])
    if done >= 4 and not progress.reward_unlocked:
        progress.reward_unlocked = True
        progress.reward_payload = ""  # TODO: 你之後填獎勵
        db.session.commit()

@bp.get("/tasks/today")
@login_required
def tasks_today():
    group_id = get_group_id_for_user()
    if not group_id:
        return jsonify({"error": "no_group"}), 400

    today = dt.date.today()
    dr = get_or_create_daily_record(group_id, today)

    # 只允許 caregiver 取「他自己的」今日任務
    m = GroupMember.query.filter_by(user_id=current_user.id).first()
    role = m.role if m else None
    if role != "caregiver":
        return jsonify({"error": "forbidden"}), 403

    # 先找今天是否已有任務
    t = DailyTask.query.filter_by(
        daily_record_id=dr.id,
        caregiver_user_id=current_user.id
    ).first()

    # 沒有就建立一筆（從你任務池隨機挑一個）
    if not t:
        task_text = pick_task_for_today()  # 你自己做任務陣列的 function（下面我也給）
        t = DailyTask(
            daily_record_id=dr.id,              # ✅ 用 dr.id 綁 group+date
            caregiver_user_id=current_user.id,  # ✅ 綁到家人本人
            task_text=task_text,
            caregiver_done=False,
            patient_confirmed=False,
        )
        db.session.add(t)
        db.session.commit()

    completed = bool(t.caregiver_done and t.patient_confirmed)

    return jsonify({
        "task_id": t.id,
        "task_text": t.task_text,
        "caregiver_done": bool(t.caregiver_done),
        "patient_confirmed": bool(t.patient_confirmed),
        "completed": completed
    })

@bp.post("/tasks/complete")
@login_required
def tasks_complete():
    # caregiver 按「我完成了」
    if not _is_role("caregiver"):
        return jsonify({"error": "forbidden"}), 403

    group_id = get_group_id_for_user()
    if not group_id:
        return jsonify({"error": "no_group"}), 400

    today = dt.date.today()
    dr = get_or_create_daily_record(group_id, today)
    task = get_or_create_daily_task(dr.id, current_user.id, group_id, today)

    task.caregiver_done = True
    db.session.commit()

    return jsonify({"ok": True, "caregiver_done": True})

def get_my_member():
    return GroupMember.query.filter_by(user_id=current_user.id).first()

@bp.get("/tasks/pending_confirmations")
@login_required
def tasks_pending_confirmations():
    m = get_my_member()
    if not m:
        return jsonify({"error": "no_group"}), 400

    # ✅ 這支就是「失智者確認」頁 → 必須 patient 才能看
    if m.role != "patient":
        return jsonify({"error": "forbidden"}), 403

    today = dt.date.today()

    # 找今天 daily_record
    dr = DailyRecord.query.filter_by(group_id=m.group_id, date=today).first()
    if not dr:
        return jsonify({"items": []})

    # 找「家人已按完成，但 patient 尚未確認」的任務
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
        caregiver = User.query.get(t.caregiver_user_id)  # 你有 User table 的話
        items.append({
            "task_id": t.id,
            "task_text": t.task_text,
            "caregiver_user_id": t.caregiver_user_id,
            "caregiver_name": (caregiver.name if caregiver else f"User {t.caregiver_user_id}"),
            "avatar_url": (caregiver.avatar_url if caregiver else None),
            "updated_at": t.updated_at.isoformat() if t.updated_at else None,
        })

    return jsonify({"items": items})

@bp.post("/tasks/confirm")
@login_required
def tasks_confirm():
    # patient 按「我確認他完成了」
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

    # 確保 task 的 daily_record 屬於同一 group（避免跨組確認）
    dr = DailyRecord.query.get(task.daily_record_id)
    if not dr or dr.group_id != group_id:
        return jsonify({"error": "forbidden"}), 403

    if not task.caregiver_done:
        return jsonify({"error": "caregiver_not_done"}), 400

    task.patient_confirmed = True
    db.session.commit()
    return jsonify({"ok": True, "patient_confirmed": True})
#end

def get_group_id_for_user():
    m = GroupMember.query.filter_by(user_id=current_user.id).first()
    return m.group_id if m else None


def get_or_create_daily_record(group_id: int, date: dt.date):
    dr = DailyRecord.query.filter_by(group_id=group_id, date=date).first()
    if not dr:
        dr = DailyRecord(group_id=group_id, date=date)
        db.session.add(dr)
        db.session.commit()
    return dr


def get_or_create_user_progress(daily_record_id: int, user_id: int):
    p = UserDailyProgress.query.filter_by(daily_record_id=daily_record_id, user_id=user_id).first()
    if not p:
        p = UserDailyProgress(daily_record_id=daily_record_id, user_id=user_id)
        db.session.add(p)
        db.session.commit()
    return p

@bp.get("/patient/today_status")
@login_required
def patient_today_status():
    group_id = get_group_id_for_user()
    if not group_id:
        return jsonify({"error": "no_group"}), 400

    today = dt.date.today()
    dr = get_or_create_daily_record(group_id, today)

    # ===== role（只查一次）=====
    gm = GroupMember.query.filter_by(user_id=current_user.id).first()
    role = gm.role if gm else None

    # ===== shared（group）=====
    photo_done = Photo.query.filter_by(daily_record_id=dr.id).count() > 0

    # ===== shared wall, personal completion：自己是否回答過 =====
    qa_done = QAEntry.query.filter_by(daily_record_id=dr.id, user_id=current_user.id).first() is not None

    # ===== personal（user）=====
    progress = get_or_create_user_progress(dr.id, current_user.id)

    mood = MoodEntry.query.filter_by(daily_record_id=dr.id, user_id=current_user.id).first()
    mood_done = mood is not None

    # ===== task_done（caregiver 需要 patient confirm 才算）=====
    if role == "caregiver":
        t = DailyTask.query.filter_by(
            daily_record_id=dr.id,
            caregiver_user_id=current_user.id
        ).first()
        task_done = bool(t and t.caregiver_done and t.patient_confirmed)
    else:
        # patient 不做 caregiver 的任務（避免卡 4/4）
        task_done = True

    # ===== reward（如果你 DB 還沒加欄位，先不要呼叫，不然會炸）=====
    # _update_reward_if_completed(progress, photo_done, mood_done, qa_done, task_done)

    # next_action
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
        "photo_done": photo_done,
        "qa_done": qa_done,
        "role": role,

        "mood_done": mood_done,
        "mood": mood.mood if mood else None,

        "task_done": task_done,

        "pet_xp": progress.pet_xp,
        "pet_level": progress.pet_level,
        "farm_state": progress.farm_state,

        # reward 先保留，但如果你 DB 沒欄位就先不要回傳
        # "reward_unlocked": bool(progress.reward_unlocked),
        # "reward_payload": progress.reward_payload,

        "today_progress": done,
        "next_action": next_action,
        "vapid_public_key": current_app.config.get("VAPID_PUBLIC_KEY", "")
    })

@bp.post("/tasks/complete")
@login_required
def complete_tasks():
    group_id = get_group_id_for_user()
    if not group_id:
        return jsonify({"error": "no_group"}), 400

    today = dt.date.today()
    dr = get_or_create_daily_record(group_id, today)
    progress = get_or_create_user_progress(dr.id, current_user.id)

    progress.task_done = True
    db.session.commit()
    return jsonify({"ok": True, "task_done": True})


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

# ---- Push 訂閱：先存前端 subscription（MVP 先用 in-memory / 之後存 DB） ----
_SUBS = {}  # user_id -> subscription json

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
            "id": p.id,
            "url": url_for("api.photo_file", photo_id=p.id),  # 下面會做
            "original_name": p.original_name,
            "uploader_user_id": p.uploader_user_id,
            "created_at": p.created_at.isoformat(),
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

    # 確保只能看自己 group 的照片
    if p.group_id != group_id:
        raise Forbidden()

    # stored_path 建議存相對路徑或絕對路徑；這裡用絕對路徑示範
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

    # date 可選：沒給就算今天
    date_str = request.form.get("date")
    if date_str:
        try:
            target_date = dt.date.fromisoformat(date_str)
        except ValueError:
            return jsonify({"error": "invalid_date"}), 400
    else:
        target_date = dt.date.today()

    dr = get_or_create_daily_record(group_id, target_date)

    # 儲存位置（你可以改到 instance/uploads）
    upload_dir = current_app.config.get("UPLOAD_DIR") or os.path.join(current_app.instance_path, "uploads")
    os.makedirs(upload_dir, exist_ok=True)

    original_name = f.filename or "upload"
    safe = secure_filename(original_name)
    stamp = dt.datetime.utcnow().strftime("%Y%m%d_%H%M%S_%f")
    filename = f"{group_id}_{target_date.isoformat()}_{stamp}_{safe}"
    path = os.path.join(upload_dir, filename)

    f.save(path)

    p = Photo(
        group_id=group_id,
        daily_record_id=dr.id,
        uploader_user_id=current_user.id,
        stored_path=path,
        original_name=original_name,
    )
    db.session.add(p)
    db.session.commit()

    return jsonify({
        "ok": True,
        "id": p.id,
        "url": url_for("api.photo_file", photo_id=p.id),
        "created_at": p.created_at.isoformat(),
    })
    
@bp.get("/qa/today")
@login_required
def qa_today():
    group_id = get_group_id_for_user()
    if not group_id:
        return jsonify({"error": "no_group"}), 400

    today = dt.date.today()
    dr = get_or_create_daily_record(group_id, today)

    items = (QAEntry.query
             .filter_by(daily_record_id=dr.id)
             .order_by(QAEntry.updated_at.desc())
             .all())

    question = items[0].question if items else "今天讓你覺得最溫暖的一件事是什麼？"

    return jsonify({
        "date": today.isoformat(),
        "question": question,
        "items": [
            {
                "id": x.id,
                "user_id": x.user_id,
                "user_name": getattr(x.user, "name", None),
                "avatar_url": getattr(x.user, "avatar_url", None),
                "answer": x.answer,
                "updated_at": x.updated_at.isoformat(),
                "is_me": (x.user_id == current_user.id),
            } for x in items
        ]
    })

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