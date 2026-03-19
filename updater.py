"""
updater.py — проверка обновлений через GitHub Releases API.

Запускается в фоновом потоке при старте.
Результат отображается баннером на вкладке Настройки.
Проверка — не чаще раза в сутки.
"""

import json
import threading
import urllib.request
import urllib.error
from datetime import datetime, timezone

try:
    from logger import log, log_error
except ImportError:
    def log(msg):       print(f"[APP] {msg}", flush=True)
    def log_error(msg, exc=None): print(f"[ERROR] {msg}", flush=True)


def _parse_version(tag: str) -> tuple:
    """'v1.2.3' или '1.2.3' → (1, 2, 3)."""
    try:
        return tuple(int(x) for x in tag.lstrip('v').strip().split('.')[:3])
    except ValueError:
        return (0, 0, 0)


def _is_newer(remote_tag: str, local_version: str) -> bool:
    return _parse_version(remote_tag) > _parse_version(local_version)


def check_for_updates(repo: str, current_version: str, callback) -> None:
    """
    Запускает проверку в фоновом потоке.
    callback(result) вызывается с результатом:
        {'available': bool, 'version': str, 'url': str, 'error': str|None}
    """
    def _worker():
        result = {'available': False, 'version': current_version,
                  'url': '', 'error': None}
        try:
            if 'your-username' in repo:
                log("Проверка обновлений пропущена: GITHUB_REPO не настроен в version.py")
                result['error'] = 'not_configured'
                callback(result)
                return

            api_url = f"https://api.github.com/repos/{repo}/releases/latest"
            log(f"Проверка обновлений: GET {api_url}")
            req = urllib.request.Request(api_url)
            req.add_header('Accept', 'application/vnd.github+json')
            req.add_header('User-Agent', f'GlucoPlan/{current_version}')

            with urllib.request.urlopen(req, timeout=8) as resp:
                data = json.loads(resp.read().decode('utf-8'))

            tag      = data.get('tag_name', '')
            html_url = data.get('html_url', '')
            assets   = data.get('assets', [])
            dl_url   = next((a['browser_download_url'] for a in assets
                             if a['name'].endswith('.zip')), html_url)

            log(f"Последний релиз на GitHub: {tag or '(нет релизов)'}")
            log(f"Текущая версия: {current_version}")

            if not tag:
                log("На GitHub нет ни одного опубликованного релиза — баннер не показывается")
                callback(result)
                return

            if _is_newer(tag, current_version):
                result.update(available=True,
                              version=tag.lstrip('v'),
                              url=dl_url)
                log(f"✓ Доступна новая версия: {tag}")
            else:
                log(f"✓ Установлена последняя версия")

        except urllib.error.HTTPError as e:
            if e.code == 404:
                log("Проверка обновлений: репозиторий не найден или нет релизов (404)")
                result['error'] = 'no_releases'
            else:
                result['error'] = f"HTTP {e.code}"
                log(f"Проверка обновлений: HTTP ошибка {e.code}")
        except urllib.error.URLError as e:
            result['error'] = str(e.reason)
            log(f"Проверка обновлений: нет соединения — {e.reason}")
        except Exception as e:
            result['error'] = str(e)
            log_error(f"Проверка обновлений: ошибка — {e}")

        callback(result)

    threading.Thread(target=_worker, daemon=True).start()


def should_check_today(db) -> bool:
    """True если с последней проверки прошло > 23 часов."""
    try:
        cfg      = db.get_ns_config()
        last_str = cfg.get('update_checked_at', '')
        if not last_str:
            return True
        last = datetime.fromisoformat(last_str)
        now  = datetime.now(timezone.utc).replace(tzinfo=None)
        return (now - last).total_seconds() > 23 * 3600
    except Exception:
        return True


def mark_checked(db) -> None:
    """Записывает время последней проверки в БД."""
    try:
        with db.get_connection() as conn:
            db._ensure_ns_tables(conn)
            conn.execute(
                "INSERT OR REPLACE INTO ns_config (key, value) VALUES (?, ?)",
                ('update_checked_at',
                 datetime.now(timezone.utc).replace(tzinfo=None).isoformat()))
            conn.commit()
    except Exception:
        pass


def save_update_result(db, result: dict) -> None:
    """Сохраняет результат проверки в БД для отображения при следующем старте."""
    try:
        with db.get_connection() as conn:
            db._ensure_ns_tables(conn)
            for key, value in [
                ('update_available', '1' if result['available'] else '0'),
                ('update_version',   result.get('version', '')),
                ('update_url',       result.get('url', '')),
            ]:
                conn.execute(
                    "INSERT OR REPLACE INTO ns_config (key, value) VALUES (?, ?)",
                    (key, value))
            conn.commit()
    except Exception:
        pass
