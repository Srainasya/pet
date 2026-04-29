from app import create_app
from app.extensions import db
from app.models import StoreItem

app = create_app()

with app.app_context():
    if StoreItem.query.count() == 0:
        rows = [
            StoreItem(name="椅子", category="item", price=140, image="/static/store/item/1.png", is_locked_default=False),
            StoreItem(name="泰迪熊", category="item", price=140, image="/static/store/item/2.png", is_locked_default=False),
            StoreItem(name="植物", category="item", price=168, image="/static/store/item/3.png", is_locked_default=False),
            StoreItem(name="沙發", category="item", price=210, image="/static/store/item/4.png", is_locked_default=False),
            StoreItem(name="棕櫚樹", category="item", price=210, image="/static/store/item/5.png", is_locked_default=False),
            StoreItem(name="床", category="item", price=320, image="/static/store/item/6.png", is_locked_default=False),

            StoreItem(name="狗狗", category="pet", price=500, image="/static/store/pets/dog.png", is_locked_default=False),
            StoreItem(name="鴨鴨", category="pet", price=800, image="/static/store/pets/duck.png", is_locked_default=False),
            StoreItem(name="狐狐", category="pet", price=800, image="/static/store/pets/fox.png", is_locked_default=False),
        ]

        db.session.add_all(rows)
        db.session.commit()
        print("store_items seeded done")
    else:
        print("store_items already has data")