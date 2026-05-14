from flask import Blueprint, render_template, request, redirect, url_for, current_app, flash, jsonify
from flask_login import login_required, current_user
from werkzeug.utils import secure_filename
from .extensions import db
import os
import uuid
import calendar
from datetime import date , datetime
from .models import (
    GroupMember, Photo, StoreItem, UserStoreItem,
    DailyRecord, MoodEntry, QAEntry, DailyTask, UserDailyProgress, Group, User, GameRecord
)
bp = Blueprint("patient", __name__, url_prefix="/patient")

ALLOWED_EXTS = {"jpg", "jpeg", "png", "webp", "gif"}




def _allowed(filename: str) -> bool:
    if not filename or "." not in filename:
        return False
    ext = filename.rsplit(".", 1)[1].lower()
    return ext in ALLOWED_EXTS


def get_group_id():
    m = GroupMember.query.filter_by(user_id=current_user.id).first()
    return m.group_id if m else None


def my_role():
    m = GroupMember.query.filter_by(user_id=current_user.id).first()
    return m.role if m else None

@bp.get("/calendar")
@login_required
def patient_calendar():
    group_id = get_group_id()
    if not group_id:
        flash("尚未綁定家庭，請先完成 onboarding。")
        return redirect(url_for("onboarding.start"))

    today = date.today()
    year = request.args.get("year", type=int) or today.year
    month = request.args.get("month", type=int) or today.month

    # 安全修正，避免奇怪參數
    if month < 1 or month > 12:
        month = today.month

    cal = calendar.Calendar(firstweekday=6)  # 週日開頭
    month_days = list(cal.monthdatescalendar(year, month))

    # 這個月所有 daily_records
    first_day = date(year, month, 1)
    last_day_num = calendar.monthrange(year, month)[1]
    last_day = date(year, month, last_day_num)

    records = (
        DailyRecord.query
        .filter(
            DailyRecord.group_id == group_id,
            DailyRecord.date >= first_day,
            DailyRecord.date <= last_day
        )
        .all()
    )

    record_dates = {r.date for r in records}

    prev_year, prev_month = (year - 1, 12) if month == 1 else (year, month - 1)
    next_year, next_month = (year + 1, 1) if month == 12 else (year, month + 1)

    return render_template(
        "patient_calendar.html",
        year=year,
        month=month,
        month_days=month_days,
        today=today,
        record_dates=record_dates,
        prev_year=prev_year,
        prev_month=prev_month,
        next_year=next_year,
        next_month=next_month,
    )
@bp.get("/calendar/<date_str>")
@login_required
def patient_calendar_day(date_str):
    group_id = get_group_id()
    if not group_id:
        flash("尚未綁定家庭，請先完成 onboarding。")
        return redirect(url_for("onboarding.start"))

    try:
        target_date = datetime.strptime(date_str, "%Y-%m-%d").date()
    except ValueError:
        flash("日期格式錯誤")
        return redirect(url_for("patient.patient_calendar"))

    dr = DailyRecord.query.filter_by(group_id=group_id, date=target_date).first()

    if not dr:
        flash("這一天還沒有資料")
        return redirect(url_for("patient.patient_calendar", year=target_date.year, month=target_date.month))

    photos = (
        db.session.query(Photo, User)
        .join(User, Photo.uploader_user_id == User.id)
        .filter(Photo.daily_record_id == dr.id)
        .order_by(Photo.created_at.asc())
        .all()
    )

    moods = (
        db.session.query(MoodEntry, User)
        .join(User, MoodEntry.user_id == User.id)
        .filter(MoodEntry.daily_record_id == dr.id)
        .order_by(MoodEntry.created_at.asc())
        .all()
    )

    qas = (
        db.session.query(QAEntry, User)
        .join(User, QAEntry.user_id == User.id)
        .filter(QAEntry.daily_record_id == dr.id)
        .order_by(QAEntry.created_at.asc())
        .all()
    )

    tasks = (
        db.session.query(DailyTask, User)
        .join(User, DailyTask.caregiver_user_id == User.id)
        .filter(DailyTask.daily_record_id == dr.id)
        .order_by(DailyTask.created_at.asc())
        .all()
    )

    progresses = (
        db.session.query(UserDailyProgress, User)
        .join(User, UserDailyProgress.user_id == User.id)
        .filter(UserDailyProgress.daily_record_id == dr.id)
        .order_by(UserDailyProgress.created_at.asc())
        .all()
    )

    return render_template(
        "patient_calendar_day.html",
        target_date=target_date,
        daily_record=dr,
        photos=photos,
        moods=moods,
        qas=qas,
        tasks=tasks,
        progresses=progresses,
    )
# ========== Farm ==========
@bp.route("/farm")
@login_required
def farm():
    membership = GroupMember.query.filter_by(user_id=current_user.id).first()
    group = None

    if membership:
        group = Group.query.filter_by(id=membership.group_id).first()

    print("current_user.id =", current_user.id)
    print("membership =", membership)
    print("group =", group)
    if group:
        print("invite_code =", group.invite_code)

    return render_template(
        "patient_farm.html",
        group=group
    )

# ========== Photos ==========
@bp.route("/photos", methods=["GET", "POST"])
@login_required
def photos():
    group_id = get_group_id()
    if not group_id:
        flash("尚未綁定家庭")
        return redirect(url_for("onboarding.start"))

    today = date.today()
    from .api import get_or_create_daily_record
    dr = get_or_create_daily_record(group_id, today)

    if request.method == "POST":
        f = request.files.get("photo")
        if not f or not f.filename:
            flash("請選擇照片")
            return redirect(url_for("patient.photos"))

        original_name = f.filename # 🌟 定義變數
        safe_name = secure_filename(original_name)
        
        ext = safe_name.rsplit(".", 1)[1].lower() if "." in safe_name else "jpg"
        
        # 🌟 統一資料夾與路徑
        rel_dir = os.path.join("uploads", str(group_id), today.isoformat())
        abs_dir = os.path.join(current_app.static_folder, rel_dir)
        os.makedirs(abs_dir, exist_ok=True)

        filename = f"{uuid.uuid4().hex}.{ext}"
        abs_path = os.path.join(abs_dir, filename)
        f.save(abs_path)

        # 🌟 將確切的相對路徑存入資料庫，確保顯示正常
        rel_path = os.path.join(rel_dir, filename).replace("\\", "/")

        # 🌟 注意！寫入資料庫必須縮進在 if POST 裡面
        p = Photo(
            group_id=group_id,
            daily_record_id=dr.id,
            uploader_user_id=current_user.id,
            stored_path=rel_path,
            original_name=original_name,
        )
        db.session.add(p)
        db.session.commit()
        flash("上傳成功 ✅")
        return redirect(url_for("patient.photos"))

    # GET 請求：顯示照片列表
    photos_list = Photo.query.filter_by(daily_record_id=dr.id).order_by(Photo.created_at.desc()).all()
    return render_template("patient_photos.html", photos=photos_list, today=today)


# ========== QA / Tasks ==========
@bp.get("/qa")
@login_required
def qa():
    return render_template("patient_qa.html")


@bp.get("/tasks")
@login_required
def tasks():
    role = my_role()

    if role == "caregiver":
        return render_template("caregiver_tasks.html")

    return render_template("patient_tasks.html")

# ========== Game / Games Menu ========== 陳威任新增

@bp.get("/games")
@login_required
def game_menu():
    # 這裡定義了要在選單上顯示的遊戲資料
    available_games = [
        {
            "id": "liar_king",
            "title": "瞎掰王",
            "desc": "發揮想像力，看看誰在說謊！",
            "icon": "🎭",
            "route": "patient.game_liar_king" # 這要對應到下方的函數名稱
        },
        {
            "id": "memory_game",
            "title": "記憶翻牌",
            "desc": "鍛鍊大腦，找出成對的卡片吧！",
            "icon": "🃏",
            "route": "patient.game_memory"
        }
    ]
    # 關鍵：必須把 available_games 傳給名為 games 的變數
    return render_template("patient_game_menu.html", games=available_games)

@bp.get("/game/liar-king")
@login_required
def game_liar_king():
    return render_template("game_liar_king.html")

@bp.get("/game/memory")
@login_required
def game_memory():
    # 撈取目前使用者的記憶翻牌紀錄，按秒數(score)由小到大排序，取前 5 名最佳成績
    best_records = GameRecord.query.filter_by(
        user_id=current_user.id,
        game_type="memory"
    ).order_by(GameRecord.score.asc()).limit(5).all()

    # 將撈到的 records 傳給前端網頁
    return render_template("game_memory.html", records=best_records)

# --- 從這裡開始替換 ---
@bp.route("/api/game/save-memory-result", methods=["POST"])
@login_required
def save_game_result():
    data = request.json
    seconds = data.get("seconds")
    
    # 真正建立一筆新紀錄並存入資料庫
    new_record = GameRecord(user_id=current_user.id, score=seconds, game_type="memory")
    db.session.add(new_record)
    db.session.commit()
    
    return jsonify({"status": "success", "message": "成績已同步至 Google 帳號"})
# --- 到這裡結束 ---

# ========== Store / Pet ==========
@bp.get("/pet")
@login_required
def patient_pet():
    # 1. 撈所有商店商品
    store_items = StoreItem.query.order_by(StoreItem.id.asc()).all()

    # 2. 撈當前使用者已擁有的商品
    owned_rows = UserStoreItem.query.filter_by(user_id=current_user.id).all()
    owned_map = {row.store_item_id: row for row in owned_rows}

    items = []
    pets = []

    for s in store_items:
        owned_row = owned_map.get(s.id)
        owned = owned_row is not None and owned_row.unlocked
        equipped = owned_row.equipped if owned_row else False
        affordable = current_user.coins >= s.price

        data = {
            "id": s.id,
            "name": s.name,
            "price": s.price,
            "image": s.image,
            "icon": s.image if not s.image else None,   # 若你 DB 沒圖片先留 fallback 用
            "locked": s.is_locked_default and not owned,
            "owned": owned,
            "equipped": equipped,
            "affordable": affordable,
            "category": s.category,
        }

        if s.category == "pet":
            pets.append(data)
        else:
            items.append(data)

    return render_template(
        "patient_pet.html",
        coins=current_user.coins,
        items=items,
        pets=pets
    )


@bp.post("/pet/buy/<int:item_id>")
@login_required
def buy_store_item(item_id):
    store_item = StoreItem.query.get_or_404(item_id)

    user_item = UserStoreItem.query.filter_by(
        user_id=current_user.id,
        store_item_id=item_id
    ).first()

    if user_item and user_item.unlocked:
        flash("你已經擁有這個物品了。")
        return redirect(url_for("patient.patient_pet"))

    if current_user.coins < store_item.price:
        flash("金幣不足，無法購買。")
        return redirect(url_for("patient.patient_pet", insufficient=1))

    # 扣錢
    current_user.coins -= store_item.price

    if not user_item:
        user_item = UserStoreItem(
            user_id=current_user.id,
            store_item_id=item_id,
            unlocked=True,
            equipped=False
        )
        db.session.add(user_item)
    else:
        user_item.unlocked = True

    db.session.commit()
    flash(f"成功購買：{store_item.name} ✅")
    return redirect(url_for("patient.patient_pet"))


@bp.post("/pet/equip/<int:item_id>")
@login_required
def equip_store_item(item_id):
    store_item = StoreItem.query.get_or_404(item_id)

    user_item = UserStoreItem.query.filter_by(
        user_id=current_user.id,
        store_item_id=item_id,
        unlocked=True
    ).first()

    if not user_item:
        flash("你還沒購買這個物品。")
        return redirect(url_for("patient.patient_pet"))

    # 同類型只能裝備一個
    equipped_rows = (
        UserStoreItem.query
        .join(StoreItem, StoreItem.id == UserStoreItem.store_item_id)
        .filter(
            UserStoreItem.user_id == current_user.id,
            UserStoreItem.equipped == True,
            StoreItem.category == store_item.category
        )
        .all()
    )

    for row in equipped_rows:
        row.equipped = False

    user_item.equipped = True
    db.session.commit()

    flash(f"已使用：{store_item.name} ✨")
    return redirect(url_for("patient.patient_pet"))
@bp.get("/stats")
@login_required
def stats():
    return render_template("patient_status.html")