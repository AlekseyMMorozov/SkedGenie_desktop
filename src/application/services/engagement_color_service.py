# src/application/services/engagement_color_service.py
"""Сервис генерации уникальных читаемых цветов для типов задействований."""
from __future__ import annotations

import colorsys
import logging
from typing import List, Set

from src.domain.engagements.engagement_exceptions import InvalidColorError


# Зарезервированные системные цвета (нормализованные к верхнему регистру)
SYSTEM_RESERVED_COLORS: Set[str] = {
    "#E0E0E0",  # Выходные / Праздники (светло-серый)
    "#FFEBEE",  # Дни рождения / Особые отметки (светло-розовый)
    "#F5F5F5",  # Фон нерабочих дней
}

# Минимальная яркость (0-255) для обеспечения читаемости белого текста
MIN_BRIGHTNESS = 140


class EngagementColorService:
    """Генерация оптимальных цветов для новых типов задействований."""

    def __init__(self, logger: logging.Logger) -> None:
        self._logger = logger

    @staticmethod
    def _hex_to_rgb(hex_color: str) -> tuple[int, int, int]:
        """Преобразует HEX (#RRGGBB) в кортеж RGB."""
        h = hex_color.lstrip("#")
        return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)

    @staticmethod
    def _rgb_to_hex(r: int, g: int, b: int) -> str:
        """Преобразует RGB в HEX."""
        return f"#{r:02X}{g:02X}{b:02X}"

    @staticmethod
    def _perceived_brightness(r: int, g: int, b: int) -> float:
        """Вычисляет воспринимаемую яркость (W3C formula)."""
        return (r * 299 + g * 587 + b * 114) / 1000

    @staticmethod
    def _color_distance_hsl(hex1: str, hex2: str) -> float:
        """Вычисляет расстояние между цветами в пространстве HSL."""
        r1, g1, b1 = [x / 255.0 for x in EngagementColorService._hex_to_rgb(hex1)]
        r2, g2, b2 = [x / 255.0 for x in EngagementColorService._hex_to_rgb(hex2)]

        h1, l1, s1 = colorsys.rgb_to_hls(r1, g1, b1)
        h2, l2, s2 = colorsys.rgb_to_hls(r2, g2, b2)

        # Hue — круговой параметр, считаем кратчайшую дугу
        dh = min(abs(h1 - h2), 1.0 - abs(h1 - h2))
        dl = abs(l1 - l2)
        ds = abs(s1 - s2)

        return (dh * 360) ** 2 + (dl * 100) ** 2 + (ds * 100) ** 2

    def generate_unique_color(self, existing_colors: List[str]) -> str:
        """
        Генерирует цвет, максимально удалённый от существующих,
        достаточно яркий для белого текста и не входящий в системные резервы.
        """
        normalized_existing = [c.upper() for c in existing_colors]
        all_occupied = set(normalized_existing) | SYSTEM_RESERVED_COLORS

        best_color = ""
        best_min_distance = -1.0

        # Проходим по 36 оттенкам (шаг 10°) × 3 уровня насыщенности × 2 уровня яркости
        candidates: List[str] = []
        for hue in range(0, 360, 10):
            for saturation in (70, 85, 100):
                for lightness in (45, 55):
                    r, g, b = colorsys.hls_to_rgb(
                        hue / 360.0, lightness / 100.0, saturation / 100.0
                    )
                    ri, gi, bi = int(r * 255), int(g * 255), int(b * 255)

                    if self._perceived_brightness(ri, gi, bi) < MIN_BRIGHTNESS:
                        continue

                    candidate = self._rgb_to_hex(ri, gi, bi)
                    if candidate in all_occupied:
                        continue

                    candidates.append(candidate)

        if not candidates:
            # Fallback: если все кандидаты заняты (крайне маловероятно)
            self._logger.warning("Не удалось найти уникальный цвет, используется fallback")
            return "#4A90D9"

        for candidate in candidates:
            min_dist = min(
                self._color_distance_hsl(candidate, occupied)
                for occupied in all_occupied
            )
            if min_dist > best_min_distance:
                best_min_distance = min_dist
                best_color = candidate

        self._logger.debug(
            "Сгенерирован цвет %s (мин. дистанция: %.2f)", best_color, best_min_distance
        )
        return best_color

    @staticmethod
    def validate_color(color: str) -> None:
        """Проверяет корректность HEX-цвета и его яркость."""
        if not isinstance(color, str) or len(color) != 7 or not color.startswith("#"):
            raise InvalidColorError(color, "Формат должен быть #RRGGBB")
        try:
            int(color[1:], 16)
        except ValueError:
            raise InvalidColorError(color, "Некорректное HEX-значение")

        r, g, b = EngagementColorService._hex_to_rgb(color)
        brightness = EngagementColorService._perceived_brightness(r, g, b)
        if brightness < MIN_BRIGHTNESS:
            raise InvalidColorError(
                color,
                f"Цвет слишком тёмкий (яркость {brightness:.0f}, минимум {MIN_BRIGHTNESS})",
            )
