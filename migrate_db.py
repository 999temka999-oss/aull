#!/usr/bin/env python3
"""
Скрипт миграции для добавления полей блокировки в таблицу players.
"""

import sqlite3
import os

def migrate_database():
    """Добавляет поля блокировки в таблицу players."""
    db_path = "instance/app.db"
    
    if not os.path.exists(db_path):
        print("❌ База данных не найдена. Запустите приложение сначала.")
        return False
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Проверяем, существуют ли уже столбцы
        cursor.execute("PRAGMA table_info(players)")
        columns = [column[1] for column in cursor.fetchall()]
        
        if 'is_blocked' in columns:
            print("✅ Столбцы блокировки уже существуют.")
            conn.close()
            return True
        
        print("🔄 Добавление полей блокировки в таблицу players...")
        
        # Добавляем столбцы
        cursor.execute("ALTER TABLE players ADD COLUMN is_blocked INTEGER DEFAULT 0")
        cursor.execute("ALTER TABLE players ADD COLUMN blocked_reason TEXT")
        
        conn.commit()
        
        print("✅ Миграция выполнена успешно!")
        print("   - Добавлен столбец is_blocked (INTEGER, по умолчанию 0)")
        print("   - Добавлен столбец blocked_reason (TEXT, может быть NULL)")
        
        # Проверяем результат
        cursor.execute("SELECT COUNT(*) FROM players")
        player_count = cursor.fetchone()[0]
        print(f"📊 Обновлено записей игроков: {player_count}")
        
        conn.close()
        return True
        
    except sqlite3.Error as e:
        print(f"❌ Ошибка SQLite: {e}")
        return False
    except Exception as e:
        print(f"❌ Общая ошибка: {e}")
        return False

if __name__ == "__main__":
    print("🗄️  Миграция базы данных для системы блокировки...\n")
    
    success = migrate_database()
    
    if success:
        print(f"\n🎉 Миграция завершена! Теперь можно запускать приложение.")
    else:
        print(f"\n💥 Миграция не удалась. Проверьте ошибки выше.")