"""Логика выращивания культур.

Обработка стадий роста всех культур: пшеница, морковь, арбуз, тыква, лук.
"""

from __future__ import annotations
from datetime import datetime, timedelta, timezone

# Длительности роста всех культур (мс)
CROP_DURATIONS = {
    "wheat": 120_000,      # 2 минуты
    "carrot": 144_000,     # 2.4 минуты
    "watermelon": 172_800, # 2.88 минуты
    "pumpkin": 207_360,    # 3.456 минуты
    "onion": 248_832,      # 4.147 минуты
}

# Переводные коэффициенты для стадий (одинаковые пропорции для всех культур)
STAGE_RATIOS = {
    "sprout": 0.167,   # 16.7% от общего времени
    "young": 0.333,    # 33.3% от общего времени
    "mature": 0.5,     # 50% от общего времени
    "ready": 1.0,      # 100% - готово к сбору
}

# Обратная совместимость для пшеницы
WHEAT_STAGE_SPROUT_MS = int(CROP_DURATIONS["wheat"] * STAGE_RATIOS["sprout"])
WHEAT_STAGE_YOUNG_MS  = int(CROP_DURATIONS["wheat"] * STAGE_RATIOS["young"])
WHEAT_STAGE_MATURE_MS = int(CROP_DURATIONS["wheat"] * STAGE_RATIOS["mature"])
WHEAT_TOTAL_MS        = CROP_DURATIONS["wheat"]

def utc_now() -> datetime:
    """Возвращает текущее UTC время."""
    return datetime.now(timezone.utc)

def to_unix_ms(dt: datetime) -> int:
    """Преобразует datetime в Unix timestamp в миллисекундах."""
    # dt должен быть timezone-aware (UTC)
    return int(dt.timestamp() * 1000)

def crop_stage_info(crop_type: str, planted_at: datetime) -> dict:
    """
    Определяет стадию роста любой культуры.
    
    Args:
        crop_type: Тип культуры ('wheat', 'carrot', 'watermelon', 'pumpkin', 'onion')
        planted_at: Время посадки
        
    Returns:
        dict: Словарь с данными о стадии роста:
            - stage: 'sprout' | 'young' | 'mature' | 'ready'
            - ready_at: ISO8601 строка готовности
            - ready_at_unix_ms: int (мс)
            - remaining_ms: int (мс, >=0)
    """
    if crop_type not in CROP_DURATIONS:
        return {"error": f"Unknown crop type: {crop_type}"}
    
    now = utc_now()
    if planted_at and planted_at.tzinfo is None:
        planted_at = planted_at.replace(tzinfo=timezone.utc)

    total_duration_ms = CROP_DURATIONS[crop_type]
    elapsed_ms = int((now - planted_at).total_seconds() * 1000)
    ready_at = planted_at + timedelta(milliseconds=total_duration_ms)
    ready_at_ms = to_unix_ms(ready_at)
    now_ms = to_unix_ms(now)
    remaining_ms = max(0, ready_at_ms - now_ms)

    # Вычисляем стадии для конкретной культуры
    sprout_threshold = int(total_duration_ms * STAGE_RATIOS["sprout"])
    young_threshold = int(total_duration_ms * STAGE_RATIOS["young"])
    mature_threshold = int(total_duration_ms * STAGE_RATIOS["mature"])

    if remaining_ms <= 0:
        stage = "ready"
    elif elapsed_ms < sprout_threshold:
        stage = "sprout"
    elif elapsed_ms < young_threshold:
        stage = "young"
    elif elapsed_ms < mature_threshold:
        stage = "mature"
    else:
        stage = "mature"

    return {
        "stage": stage,
        "ready_at": ready_at.isoformat().replace("+00:00", "Z"),
        "ready_at_unix_ms": ready_at_ms,
        "remaining_ms": remaining_ms,
    }

def wheat_stage_info(planted_at: datetime) -> dict:
    """
    Определяет стадию роста пшеницы (для обратной совместимости).
    
    Args:
        planted_at: Время посадки
        
    Returns:
        dict: Словарь с данными о стадии роста пшеницы
    """
    return crop_stage_info("wheat", planted_at)
