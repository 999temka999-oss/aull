#!/usr/bin/env python3
"""
Скрипт для добавления пшеницы в инвентарь игрока для тестирования.
"""

from app import create_app
from app.models import db, Player, Inventory, add_inventory

def add_wheat_to_player(user_id=None, quantity=100):
    """Добавляет пшеницу в инвентарь игрока."""
    app = create_app()
    
    with app.app_context():
        # Если user_id не указан, берем первого игрока
        if user_id is None:
            player = db.session.query(Player).first()
            if not player:
                print("❌ Игроков в базе не найдено")
                return False
            user_id = player.user_id
            print(f"📍 Используем игрока: {player.display_name} (ID: {user_id})")
        else:
            player = db.session.get(Player, user_id)
            if not player:
                print(f"❌ Игрок с ID {user_id} не найден")
                return False
            
        # Добавляем пшеницу
        try:
            inventory_row = add_inventory(user_id, "crop_wheat", quantity)
            db.session.commit()
            
            print(f"✅ Добавлено {quantity} пшеницы")
            print(f"📦 Текущее количество пшеницы: {inventory_row.qty}")
            
            # Показываем весь инвентарь
            all_inventory = db.session.query(Inventory).filter_by(user_id=user_id).all()
            print(f"\n📋 Весь инвентарь игрока {player.display_name}:")
            for item in all_inventory:
                item_name = {
                    "seed_wheat": "Семена пшеницы",
                    "crop_wheat": "Пшеница"
                }.get(item.item_key, item.item_key)
                print(f"  • {item_name}: {item.qty}")
                
            return True
            
        except Exception as e:
            db.session.rollback()
            print(f"❌ Ошибка: {e}")
            return False

if __name__ == "__main__":
    print("🌾 Добавление пшеницы для тестирования...\n")
    
    success = add_wheat_to_player(quantity=100)
    
    if success:
        print(f"\n🎉 Готово! Теперь можно тестировать продажу пшеницы.")
    else:
        print(f"\n💥 Не удалось добавить пшеницу.")