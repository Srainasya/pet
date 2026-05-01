# import datetime as dt
# import secrets
# from flask_login import UserMixin
# from .extensions import db


# class StoreItem(db.Model):
#     __tablename__ = "store_items"

#     id = db.Column(db.Integer, primary_key=True)
#     name = db.Column(db.String(100), nullable=False)
#     category = db.Column(db.String(20), nullable=False)   # item / pet
#     price = db.Column(db.Integer, nullable=False)
#     image = db.Column(db.String(255), nullable=True)
#     is_locked_default = db.Column(db.Boolean, default=False)
    
# class UserStoreItem(db.Model):
#     __tablename__ = "user_store_items"

#     id = db.Column(db.Integer, primary_key=True)
#     user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
#     store_item_id = db.Column(db.Integer, db.ForeignKey("store_items.id"), nullable=False)

#     unlocked = db.Column(db.Boolean, default=False, nullable=False)
#     equipped = db.Column(db.Boolean, default=False, nullable=False)

#     __table_args__ = (
#         db.UniqueConstraint("user_id", "store_item_id", name="uq_user_store_item"),
#     )

#     store_item = db.relationship("StoreItem", backref=db.backref("user_links", lazy=True))

# class DailyTask(db.Model):
#     __tablename__ = "daily_tasks"
#     id = db.Column(db.Integer, primary_key=True)

#     daily_record_id = db.Column(db.Integer, db.ForeignKey("daily_records.id"), nullable=False, index=True)
#     caregiver_user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)

#     task_text = db.Column(db.String(255), nullable=False)

#     caregiver_done = db.Column(db.Boolean, default=False, nullable=False)
#     patient_confirmed = db.Column(db.Boolean, default=False, nullable=False)

#     created_at = db.Column(db.DateTime, default=dt.datetime.utcnow, nullable=False)
#     updated_at = db.Column(db.DateTime, default=dt.datetime.utcnow, onupdate=dt.datetime.utcnow, nullable=False)

#     __table_args__ = (
#         db.UniqueConstraint("daily_record_id", "caregiver_user_id", name="uq_daily_task_user"),
#     )
    
# class UserDailyProgress(db.Model):
#     __tablename__ = "user_daily_progress"

#     id = db.Column(db.Integer, primary_key=True)

#     # ✅ 指向 daily_records
#     daily_record_id = db.Column(db.Integer, db.ForeignKey("daily_records.id"), nullable=False)

#     # ✅ 指向 users
#     user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    
#     reward_unlocked = db.Column(db.Boolean, default=False, nullable=False)
#     reward_payload = db.Column(db.Text, default="", nullable=False)  # 先留空，你之後放獎勵內容/型別/JSON 都行
    
#     task_done = db.Column(db.Boolean, default=False, nullable=False)
#     pet_xp = db.Column(db.Integer, default=0, nullable=False)
#     pet_level = db.Column(db.Integer, default=1, nullable=False)
#     farm_state = db.Column(db.Text, default="{}", nullable=False)

#     created_at = db.Column(db.DateTime, default=dt.datetime.utcnow, nullable=False)
#     updated_at = db.Column(db.DateTime, default=dt.datetime.utcnow, onupdate=dt.datetime.utcnow, nullable=False)

#     __table_args__ = (
#         db.UniqueConstraint("daily_record_id", "user_id", name="uq_progress_daily_user"),
#     )

# class User(db.Model, UserMixin):
#     __tablename__ = "users"
#     id = db.Column(db.Integer, primary_key=True)
#     google_sub = db.Column(db.String(128), unique=True, index=True, nullable=True)
#     email = db.Column(db.String(255), unique=True, index=True, nullable=True)
#     name = db.Column(db.String(255), nullable=True)
#     avatar_url = db.Column(db.Text, nullable=True)
#     coins = db.Column(db.Integer, default=0, nullable=False)
#     created_at = db.Column(db.DateTime, default=dt.datetime.utcnow, nullable=False)
#     onboarding_done = db.Column(db.Boolean, default=False, nullable=False)

# class Group(db.Model):
#     __tablename__ = "groups"
#     id = db.Column(db.Integer, primary_key=True)
#     name = db.Column(db.String(255), default="My Family", nullable=False)
#     invite_code = db.Column(db.String(12), unique=True, index=True, nullable=False)
#     created_at = db.Column(db.DateTime, default=dt.datetime.utcnow, nullable=False)

#     @staticmethod
#     def new_invite_code():
#         return secrets.token_hex(3).upper()

# class GroupMember(db.Model):
#     __tablename__ = "group_members"
#     id = db.Column(db.Integer, primary_key=True)
#     group_id = db.Column(db.Integer, db.ForeignKey("groups.id"), nullable=False, index=True)
#     user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
#     role = db.Column(db.String(16), nullable=False)
#     created_at = db.Column(db.DateTime, default=dt.datetime.utcnow, nullable=False)

#     __table_args__ = (
#         db.UniqueConstraint("group_id", "user_id", name="uq_group_user"),
#     )

# class DailyRecord(db.Model):
#     __tablename__ = "daily_records"
#     id = db.Column(db.Integer, primary_key=True)
#     group_id = db.Column(db.Integer, db.ForeignKey("groups.id"), nullable=False, index=True)
#     date = db.Column(db.Date, nullable=False, index=True)
#     created_at = db.Column(db.DateTime, default=dt.datetime.utcnow, nullable=False)

#     __table_args__ = (
#         db.UniqueConstraint("group_id", "date", name="uq_group_date"),
#     )

# class MoodEntry(db.Model):
#     __tablename__ = "mood_entries"
#     id = db.Column(db.Integer, primary_key=True)
#     daily_record_id = db.Column(db.Integer, db.ForeignKey("daily_records.id"), nullable=False, index=True)
#     user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
#     mood = db.Column(db.String(32), nullable=False)
#     created_at = db.Column(db.DateTime, default=dt.datetime.utcnow, nullable=False)

#     __table_args__ = (
#         db.UniqueConstraint("daily_record_id", "user_id", name="uq_daily_user_mood"),
#     )

# class Photo(db.Model):
#     __tablename__ = "photos"
#     id = db.Column(db.Integer, primary_key=True)
#     group_id = db.Column(db.Integer, nullable=False, index=True)
#     daily_record_id = db.Column(db.Integer, db.ForeignKey("daily_records.id"), nullable=False, index=True)
#     uploader_user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
#     stored_path = db.Column(db.String(255), nullable=False)
#     original_name = db.Column(db.String(255), nullable=True)
#     created_at = db.Column(db.DateTime, nullable=False, default=dt.datetime.utcnow)

#     daily_record = db.relationship("DailyRecord", backref=db.backref("photos", lazy=True))
#     uploader = db.relationship("User", foreign_keys=[uploader_user_id])

# class QAEntry(db.Model):
#     __tablename__ = "qa_entries"

#     id = db.Column(db.Integer, primary_key=True)
#     daily_record_id = db.Column(db.Integer, db.ForeignKey("daily_records.id"), nullable=False, index=True)
#     user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)

#     question = db.Column(db.Text, nullable=False)
#     answer = db.Column(db.Text, nullable=False)

#     created_at = db.Column(db.DateTime, default=dt.datetime.utcnow, nullable=False)
#     updated_at = db.Column(db.DateTime, default=dt.datetime.utcnow, onupdate=dt.datetime.utcnow, nullable=False)

#     __table_args__ = (
#         db.UniqueConstraint("daily_record_id", "user_id", name="uq_daily_user_qa"),
#     )

#     user = db.relationship("User", foreign_keys=[user_id])

import datetime as dt
import secrets
from flask_login import UserMixin
from .extensions import db


class StoreItem(db.Model):
    __tablename__ = "store_items"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    category = db.Column(db.String(20), nullable=False)   # item / pet
    price = db.Column(db.Integer, nullable=False)
    image = db.Column(db.String(255), nullable=True)
    is_locked_default = db.Column(db.Boolean, default=False)


class UserStoreItem(db.Model):
    __tablename__ = "user_store_items"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    store_item_id = db.Column(db.Integer, db.ForeignKey("store_items.id"), nullable=False)

    unlocked = db.Column(db.Boolean, default=False, nullable=False)
    equipped = db.Column(db.Boolean, default=False, nullable=False)

    __table_args__ = (
        db.UniqueConstraint("user_id", "store_item_id", name="uq_user_store_item"),
    )

    store_item = db.relationship("StoreItem", backref=db.backref("user_links", lazy=True))


class DailyTask(db.Model):
    __tablename__ = "daily_tasks"
    id = db.Column(db.Integer, primary_key=True)

    daily_record_id = db.Column(db.Integer, db.ForeignKey("daily_records.id"), nullable=False, index=True)
    caregiver_user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)

    task_text = db.Column(db.String(255), nullable=False)

    caregiver_done = db.Column(db.Boolean, default=False, nullable=False)
    patient_confirmed = db.Column(db.Boolean, default=False, nullable=False)

    created_at = db.Column(db.DateTime, default=dt.datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=dt.datetime.utcnow, onupdate=dt.datetime.utcnow, nullable=False)

    __table_args__ = (
        db.UniqueConstraint("daily_record_id", "caregiver_user_id", name="uq_daily_task_user"),
    )


class UserDailyProgress(db.Model):
    __tablename__ = "user_daily_progress"

    id = db.Column(db.Integer, primary_key=True)
    daily_record_id = db.Column(db.Integer, db.ForeignKey("daily_records.id"), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)

    reward_unlocked = db.Column(db.Boolean, default=False, nullable=False)
    reward_payload = db.Column(db.Text, default="", nullable=False)

    task_done = db.Column(db.Boolean, default=False, nullable=False)
    pet_xp = db.Column(db.Integer, default=0, nullable=False)
    pet_level = db.Column(db.Integer, default=1, nullable=False)
    farm_state = db.Column(db.Text, default="{}", nullable=False)

    created_at = db.Column(db.DateTime, default=dt.datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=dt.datetime.utcnow, onupdate=dt.datetime.utcnow, nullable=False)

    __table_args__ = (
        db.UniqueConstraint("daily_record_id", "user_id", name="uq_progress_daily_user"),
    )


class User(db.Model, UserMixin):
    __tablename__ = "users"
    id = db.Column(db.Integer, primary_key=True)
    google_sub = db.Column(db.String(128), unique=True, index=True, nullable=True)
    email = db.Column(db.String(255), unique=True, index=True, nullable=True)
    name = db.Column(db.String(255), nullable=True)
    avatar_url = db.Column(db.Text, nullable=True)
    coins = db.Column(db.Integer, default=0, nullable=False)
    created_at = db.Column(db.DateTime, default=dt.datetime.utcnow, nullable=False)
    onboarding_done = db.Column(db.Boolean, default=False, nullable=False)


class Group(db.Model):
    __tablename__ = "groups"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255), default="My Family", nullable=False)
    invite_code = db.Column(db.String(12), unique=True, index=True, nullable=False)
    created_at = db.Column(db.DateTime, default=dt.datetime.utcnow, nullable=False)

    @staticmethod
    def new_invite_code():
        while True:
            code = secrets.token_hex(3).upper()   # 例如 A1B2C3
            exists = Group.query.filter_by(invite_code=code).first()
            if not exists:
                return code


class GroupMember(db.Model):
    __tablename__ = "group_members"
    id = db.Column(db.Integer, primary_key=True)
    group_id = db.Column(db.Integer, db.ForeignKey("groups.id"), nullable=False, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    role = db.Column(db.String(16), nullable=False)
    created_at = db.Column(db.DateTime, default=dt.datetime.utcnow, nullable=False)

    __table_args__ = (
        db.UniqueConstraint("group_id", "user_id", name="uq_group_user"),
    )


class DailyRecord(db.Model):
    __tablename__ = "daily_records"
    id = db.Column(db.Integer, primary_key=True)
    group_id = db.Column(db.Integer, db.ForeignKey("groups.id"), nullable=False, index=True)
    date = db.Column(db.Date, nullable=False, index=True)
    created_at = db.Column(db.DateTime, default=dt.datetime.utcnow, nullable=False)

    __table_args__ = (
        db.UniqueConstraint("group_id", "date", name="uq_group_date"),
    )


class MoodEntry(db.Model):
    __tablename__ = "mood_entries"
    id = db.Column(db.Integer, primary_key=True)
    daily_record_id = db.Column(db.Integer, db.ForeignKey("daily_records.id"), nullable=False, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    mood = db.Column(db.String(32), nullable=False)
    created_at = db.Column(db.DateTime, default=dt.datetime.utcnow, nullable=False)

    __table_args__ = (
        db.UniqueConstraint("daily_record_id", "user_id", name="uq_daily_user_mood"),
    )


class Photo(db.Model):
    __tablename__ = "photos"
    id = db.Column(db.Integer, primary_key=True)
    group_id = db.Column(db.Integer, nullable=False, index=True)
    daily_record_id = db.Column(db.Integer, db.ForeignKey("daily_records.id"), nullable=False, index=True)
    uploader_user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    stored_path = db.Column(db.String(255), nullable=False)
    original_name = db.Column(db.String(255), nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=dt.datetime.utcnow)

    daily_record = db.relationship("DailyRecord", backref=db.backref("photos", lazy=True))
    uploader = db.relationship("User", foreign_keys=[uploader_user_id])


class QAEntry(db.Model):
    __tablename__ = "qa_entries"

    id = db.Column(db.Integer, primary_key=True)
    daily_record_id = db.Column(db.Integer, db.ForeignKey("daily_records.id"), nullable=False, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)

    question = db.Column(db.Text, nullable=False)
    answer = db.Column(db.Text, nullable=False)

    created_at = db.Column(db.DateTime, default=dt.datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=dt.datetime.utcnow, onupdate=dt.datetime.utcnow, nullable=False)

    __table_args__ = (
        db.UniqueConstraint("daily_record_id", "user_id", name="uq_daily_user_qa"),
    )

    user = db.relationship("User", foreign_keys=[user_id])

class GameRecord(db.Model):
    __tablename__ = 'game_records'

    id = db.Column(db.Integer, primary_key=True)
    # 綁定 Google 帳號的使用者 ID
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False) 
    game_type = db.Column(db.String(50), default='memory_match')
    score = db.Column(db.Integer)  # 這裡存秒數
    completed_at = db.Column(db.DateTime, default=dt.datetime.utcnow, nullable=False)

    # 建立關聯：這行必須縮進在 class 裡面
    user = db.relationship('User', backref=db.backref('game_records', lazy=True))