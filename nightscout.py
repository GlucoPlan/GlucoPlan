"""
nightscout.py — клиент NightScout API.

Поддерживает:
  - Получение последних показаний CGM (глюкоза + тренд)
  - Расчёт тренда по нескольким точкам (ммоль/л в минуту)
  - Отправку приёма пищи (carbs) и инсулина как Treatment
  - Проверку связи с сервером

Все сетевые вызовы блокирующие — вызывать из потока, не из главного UI.
"""

import json
import urllib.request
import urllib.parse
import urllib.error
from datetime import datetime, timezone, timedelta
from dataclasses import dataclass, field
from typing import Optional, List

try:
    from logger import log_ns
except ImportError:
    def log_ns(msg): print(f"[NS] {msg}", flush=True)

# ── Направление тренда ────────────────────────────────────────────────────────

TREND_ARROWS = {
    'DoubleUp':        '⇈',
    'SingleUp':        '↑',
    'FortyFiveUp':     '↗',
    'Flat':            '→',
    'FortyFiveDown':   '↘',
    'SingleDown':      '↓',
    'DoubleDown':      '⇊',
    'NOT COMPUTABLE':  '?',
    'RATE OUT OF RANGE': '⚡',
    'None':            '—',
}

TREND_LABELS = {
    'DoubleUp':        'Быстро растёт (> +2 мг/дл/мин)',
    'SingleUp':        'Растёт (> +1 мг/дл/мин)',
    'FortyFiveUp':     'Медленно растёт',
    'Flat':            'Стабильно',
    'FortyFiveDown':   'Медленно снижается',
    'SingleDown':      'Снижается',
    'DoubleDown':      'Быстро снижается',
    'NOT COMPUTABLE':  'Нет данных',
    'RATE OUT OF RANGE': 'Слишком быстро',
    'None':            '—',
}

# Поправка к дозе с учётом тренда (ед. инсулина), ключ — direction NightScout
TREND_DOSE_DELTA = {
    'DoubleUp':       +2.0,
    'SingleUp':       +1.0,
    'FortyFiveUp':    +0.5,
    'Flat':            0.0,
    'FortyFiveDown':  -0.5,
    'SingleDown':     -1.0,
    'DoubleDown':     -2.0,
    'NOT COMPUTABLE':  0.0,
    'RATE OUT OF RANGE': 0.0,
    'None':            0.0,
}


@dataclass
class GlucoseReading:
    """Одно показание CGM."""
    sgv_mgdl:   float               # мг/дл — как хранит NS
    mmol:       float               # ммоль/л
    timestamp:  datetime            # UTC
    direction:  str = 'None'        # тренд из NS
    delta_mgdl: Optional[float] = None  # изменение за 5 мин, мг/дл

    @property
    def arrow(self) -> str:
        return TREND_ARROWS.get(self.direction, '?')

    @property
    def trend_label(self) -> str:
        return TREND_LABELS.get(self.direction, '?')

    @property
    def dose_delta(self) -> float:
        """Поправка к дозе инсулина на основе тренда (ед.)."""
        return TREND_DOSE_DELTA.get(self.direction, 0.0)

    @property
    def age_seconds(self) -> float:
        now = datetime.now(timezone.utc)
        return (now - self.timestamp).total_seconds()

    @property
    def is_fresh(self) -> bool:
        """Свежее ли показание (< 10 минут)."""
        return self.age_seconds < 600

    @property
    def age_str(self) -> str:
        sec = int(self.age_seconds)
        if sec < 60:
            return f"{sec} с назад"
        elif sec < 3600:
            return f"{sec // 60} мин назад"
        else:
            return f"{sec // 3600} ч {(sec % 3600) // 60} мин назад"


@dataclass
class NightScoutConfig:
    url:    str = ''     # https://mysite.herokuapp.com
    token:  str = ''     # API secret (не токен авторизации — именно API secret)
    enabled: bool = False


class NightScoutError(Exception):
    pass


class NightScoutClient:
    """
    Клиент NightScout REST API v1.
    url  — базовый адрес без слеша, например https://myns.fly.dev
    token — API secret (строка из настроек NS, обычно 12+ символов)
    """

    def __init__(self, config: NightScoutConfig):
        self.cfg = config

    @staticmethod
    def _hash_secret(secret: str) -> str:
        """
        NightScout требует SHA1-хеш от API Secret в заголовке api-secret.
        Если токен уже выглядит как SHA1 (40 hex-символов) — используем как есть.
        """
        import hashlib
        if len(secret) == 40 and all(c in '0123456789abcdefABCDEF' for c in secret):
            return secret  # уже хеш
        return hashlib.sha1(secret.encode('utf-8')).hexdigest()

    def _request(self, method: str, path: str,
                 params: dict = None, body: dict = None,
                 timeout: int = 10) -> dict:
        base_url = self.cfg.url.rstrip('/')
        url      = base_url + path

        # Добавляем token в query-параметры (работает на всех хостингах)
        all_params = dict(params or {})
        if self.cfg.token:
            all_params['token'] = self.cfg.token
        if all_params:
            url += '?' + urllib.parse.urlencode(all_params)

        data = json.dumps(body).encode('utf-8') if body else None
        req  = urllib.request.Request(url, data=data, method=method)

        # SHA1-хеш в заголовке (стандартный способ NS)
        if self.cfg.token:
            req.add_header('api-secret', self._hash_secret(self.cfg.token))

        req.add_header('Content-Type', 'application/json')
        req.add_header('Accept', 'application/json')

        log_ns(f"{method} {base_url + path} (params: {list(all_params.keys())})")

        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                raw = resp.read().decode('utf-8')
                result = json.loads(raw) if raw.strip() else {}
                log_ns(f"OK {resp.status}")
                return result
        except urllib.error.HTTPError as e:
            body_text = e.read().decode('utf-8', errors='replace')
            log_ns(f"HTTP {e.code}: {body_text[:300]}")
            raise NightScoutError(f"HTTP {e.code}: {body_text[:200]}")
        except urllib.error.URLError as e:
            log_ns(f"URLError: {e.reason}")
            raise NightScoutError(f"Не удалось подключиться: {e.reason}")
        except Exception as e:
            log_ns(f"Exception: {e}")
            raise NightScoutError(str(e))

    # ── Получение показаний ────────────────────────────────────────────────

    def get_entries(self, count: int = 5) -> List[GlucoseReading]:
        """
        Возвращает `count` последних показаний CGM, от новых к старым.
        """
        raw = self._request('GET', '/api/v1/entries/sgv.json',
                            params={'count': count, 'units': 'mmol'})
        readings = []
        for e in raw:
            try:
                sgv  = float(e.get('sgv', 0))
                mmol = round(sgv / 18.0182, 1)
                ts_ms = e.get('date', 0)
                ts   = datetime.fromtimestamp(ts_ms / 1000, tz=timezone.utc)
                dir_ = e.get('direction', 'None') or 'None'
                delt = e.get('delta', None)
                readings.append(GlucoseReading(
                    sgv_mgdl=sgv, mmol=mmol, timestamp=ts,
                    direction=dir_, delta_mgdl=float(delt) if delt else None))
            except Exception as ex:
                log_ns(f"Ошибка парсинга записи CGM: {ex} — запись: {e}")
                continue
        log_ns(f"Получено {len(readings)} показаний CGM")
        return readings

    def get_current_glucose(self) -> Optional[GlucoseReading]:
        """
        Возвращает последнее свежее (< 10 мин) показание или None.
        Также вычисляет тренд по нескольким точкам если direction отсутствует.
        """
        readings = self.get_entries(count=5)
        if not readings:
            return None
        latest = readings[0]
        if not latest.is_fresh:
            return None

        # Если NS не вернул direction — вычисляем по последним точкам
        if latest.direction in ('None', 'NOT COMPUTABLE', '') and len(readings) >= 3:
            latest.direction = self._calc_direction(readings[:4])

        return latest

    def _calc_direction(self, readings: List[GlucoseReading]) -> str:
        """Вычисляет тренд по линейной регрессии нескольких точек."""
        if len(readings) < 2:
            return 'Flat'
        # readings[0] — самое новое
        # Считаем скорость изменения мг/дл за минуту
        deltas = []
        for i in range(len(readings) - 1):
            dt_min = (readings[i].timestamp - readings[i+1].timestamp).total_seconds() / 60
            if dt_min > 0:
                rate = (readings[i].sgv_mgdl - readings[i+1].sgv_mgdl) / dt_min
                deltas.append(rate)
        if not deltas:
            return 'Flat'
        rate = sum(deltas) / len(deltas)   # мг/дл в минуту
        if rate >  3.5:   return 'DoubleUp'
        if rate >  2.0:   return 'SingleUp'
        if rate >  1.0:   return 'FortyFiveUp'
        if rate > -1.0:   return 'Flat'
        if rate > -2.0:   return 'FortyFiveDown'
        if rate > -3.5:   return 'SingleDown'
        return 'DoubleDown'

    def calc_trend_projection(self, readings: List[GlucoseReading],
                               minutes_ahead: int = 20) -> Optional[float]:
        """
        Прогноз сахара через minutes_ahead минут.
        Приоритет: если direction известен — берём скорость из него,
        иначе считаем по последним точкам. Дополнительно ограничиваем
        скорость физиологическим максимумом ±0.25 ммоль/л в минуту.
        """
        if not readings:
            return None

        latest = readings[0]

        # Скорость по direction (ммоль/л в минуту)
        DIRECTION_RATE = {
            'DoubleUp':       0.20,
            'SingleUp':       0.12,
            'FortyFiveUp':    0.06,
            'Flat':           0.00,
            'FortyFiveDown': -0.06,
            'SingleDown':    -0.12,
            'DoubleDown':    -0.20,
        }
        direction = latest.direction or 'Flat'

        if direction in DIRECTION_RATE:
            # Используем табличную скорость — она более надёжна для Libre
            rate_mmol_per_min = DIRECTION_RATE[direction]
        elif len(readings) >= 2:
            # Считаем по точкам, только если direction неизвестен
            deltas = []
            for i in range(min(3, len(readings) - 1)):
                dt_min = (readings[i].timestamp - readings[i+1].timestamp
                          ).total_seconds() / 60
                if dt_min > 0:
                    d_mmol = (readings[i].sgv_mgdl - readings[i+1].sgv_mgdl) / 18.0182
                    deltas.append(d_mmol / dt_min)
            if not deltas:
                return None
            rate_mmol_per_min = sum(deltas) / len(deltas)
            # Физиологический ограничитель: не более 0.25 ммоль/л в минуту
            rate_mmol_per_min = max(-0.25, min(0.25, rate_mmol_per_min))
        else:
            return None

        projected = latest.mmol + rate_mmol_per_min * minutes_ahead
        return round(max(1.5, min(30.0, projected)), 1)

    # ── Отправка данных ────────────────────────────────────────────────────

    def post_treatment(self, treatment: dict) -> dict:
        """
        Отправляет Treatment на сервер.
        treatment — словарь по схеме NS Treatments API.
        """
        return self._request('POST', '/api/v1/treatments', body=treatment)

    def post_meal(self, carbs_g: float, notes: str = '',
                  insulin_units: float = 0.0,
                  glucose_mmol: Optional[float] = None,
                  dt: Optional[datetime] = None) -> dict:
        """
        Записывает приём пищи + болюс как Treatment типа 'Meal Bolus'.
        dt — локальное время приёма (если None, берёт текущее).
        """
        if dt is None:
            dt = datetime.now()
        # NS ждёт ISO 8601 в локальном времени
        created_at = dt.strftime('%Y-%m-%dT%H:%M:%S')

        treatment = {
            'eventType':  'Meal Bolus',
            'created_at': created_at,
            'carbs':      round(carbs_g, 1),
            'insulin':    round(insulin_units, 2) if insulin_units else None,
            'notes':      notes or '',
        }
        if glucose_mmol is not None:
            treatment['glucose']      = round(glucose_mmol * 18.0182)  # → мг/дл
            treatment['glucoseType']  = 'Finger'
            treatment['units']        = 'mmol/L'

        # Убираем None-поля
        treatment = {k: v for k, v in treatment.items() if v is not None and v != ''}
        return self.post_treatment(treatment)

    def post_note(self, text: str, dt: Optional[datetime] = None) -> dict:
        """Записывает произвольную заметку как Treatment типа Note."""
        if dt is None:
            dt = datetime.now()
        return self.post_treatment({
            'eventType':  'Note',
            'created_at': dt.strftime('%Y-%m-%dT%H:%M:%S'),
            'notes':      text,
        })

    # ── Утилиты ────────────────────────────────────────────────────────────

    def check_connection(self) -> tuple[bool, str]:
        """
        Проверяет доступность сервера.
        Возвращает (ok: bool, message: str).
        """
        log_ns(f"Проверка соединения с {self.cfg.url}")
        try:
            status = self._request('GET', '/api/v1/status.json', timeout=8)
            name   = status.get('settings', {}).get('customTitle', 'NightScout')
            ver    = status.get('version', '?')
            msg    = f"Подключено: {name} (v{ver})"
            log_ns(msg)
            return True, msg
        except NightScoutError as e:
            log_ns(f"Ошибка соединения: {e}")
            return False, str(e)
