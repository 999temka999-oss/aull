#!/usr/bin/env python3
"""
Тест импортов и базовой функциональности проекта.
"""

def test_imports():
    """Проверяет, что все модули импортируются без ошибок."""
    try:
        # Основные модули
        import os
        import time
        from datetime import datetime, timedelta
        
        print("✅ Стандартные модули импортированы")
        
        # Модули приложения
        from config import Config
        print("✅ Config импортирован")
        
        from app.models import db, Player, ActionNonce, Plot, Inventory
        print("✅ Models импортированы")
        
        from app.logic.crops import wheat_stage_info, utc_now
        print("✅ Crops logic импортирована")
        
        from app.utils.tg_auth import verify_init_data_ed25519
        print("✅ Telegram auth импортирована")
        
        # Тест базовых функций
        now = utc_now()
        print(f"✅ UTC time: {now}")
        
        # Тест конфигурации  
        config = Config()
        print(f"✅ Config loaded, field cost: {config.FIELD_COST}")
        
        print("\n🎉 Все импорты прошли успешно!")
        return True
        
    except ImportError as e:
        print(f"❌ Ошибка импорта: {e}")
        return False
    except Exception as e:
        print(f"❌ Общая ошибка: {e}")
        return False

def test_flask_app():
    """Тест создания Flask приложения."""
    try:
        from app import create_app
        
        app = create_app()
        print("✅ Flask app создано")
        
        with app.app_context():
            from app.models import db
            # Проверим, что таблицы могут быть созданы
            db.create_all()
            print("✅ Таблицы БД созданы")
            
        print("✅ Flask app протестировано")
        return True
        
    except Exception as e:
        print(f"❌ Ошибка Flask app: {e}")
        return False

if __name__ == "__main__":
    print("🧪 Запуск тестов проекта...\n")
    
    test1 = test_imports()
    test2 = test_flask_app()
    
    if test1 and test2:
        print("\n🏆 Все тесты прошли! Проект готов к запуску.")
    else:
        print("\n💥 Обнаружены ошибки. Требуется исправление.")