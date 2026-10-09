#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
J.A.R.V.I.S. — голосовой помощник с красивым игровым меню.

Команды (русский язык, recognition=ru-RU):
  «Джарвис, открой меню»   — открывает игровое меню в браузере
  «Джарвис, закрой меню»   — закрывает вкладку меню (останавливает сервер меню)
  «Джарвис, добавь игру <название> <путь>» — добавляет ярлык в меню
  «Джарвис, запусти <название>»             — запускает игру из меню
  «Джарвис, выход» / «пока»                 — выключает помощника

Меню — единый HTML-файл jarvis_menu.html, работает и офлайн
(данные хранятся в localStorage + резервная копия games.json).

Зависимости:  pip install -r Requirements.txt
Нужен микрофон. Без микрофона/Internet Explorer-распознавания
доступен текстовый режим (просто печатайте команды).
"""

import json
import os
import re
import subprocess
import sys
import threading
import time
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
MENU_HTML = os.path.join(BASE_DIR, "jarvis_menu.html")
GAMES_JSON = os.path.join(BASE_DIR, "games.json")
MENU_PORT = 8765
MENU_URL = f"http://127.0.0.1:{MENU_PORT}/"

WAKE = ("джарвис", "jarvis", "джарвиса")


# ----------------------------------------------------------------------------
# Хранилище ярлыков игр
# ----------------------------------------------------------------------------
def load_games():
    try:
        with open(GAMES_JSON, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return []


def save_games(games):
    try:
        with open(GAMES_JSON, "w", encoding="utf-8") as f:
            json.dump(games, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"[warn] не удалось сохранить games.json: {e}")


# ----------------------------------------------------------------------------
# Локальный HTTP-сервер для меню (отдача HTML + API)
# ----------------------------------------------------------------------------
class MenuHandler(BaseHTTPRequestHandler):
    def log_message(self, *a):  # тихий режим
        pass

    def _send(self, code, body, ctype):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path in ("/", "/index.html", "/menu"):
            try:
                with open(MENU_HTML, "rb") as f:
                    self._send(200, f.read(), "text/html; charset=utf-8")
            except FileNotFoundError:
                self._send(500, b"jarvis_menu.html not found", "text/plain")
        elif self.path == "/api/games":
            self._send(200, json.dumps(load_games()).encode(), "application/json")
        else:
            self._send(404, b"not found", "text/plain")

    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        raw = self.rfile.read(length) if length else b"{}"
        try:
            data = json.loads(raw.decode("utf-8"))
        except Exception:
            data = {}

        if self.path == "/api/games":
            games = data if isinstance(data, list) else []
            save_games(games)
            self._send(200, b'{"ok":true}', "application/json")
        elif self.path == "/api/launch":
            ok, msg = launch_path(data.get("path", ""))
            code = 200 if ok else 400
            self._send(code, json.dumps({"ok": ok, "msg": msg}).encode(), "application/json")
        else:
            self._send(404, b"not found", "text/plain")


_server_lock = threading.Lock()
_menu_server = None


def start_menu_server():
    global _menu_server
    with _server_lock:
        if _menu_server is None:
            _menu_server = ThreadingHTTPServer(("127.0.0.1", MENU_PORT), MenuHandler)
            threading.Thread(target=_menu_server.serve_forever, daemon=True).start()
            print(f"[menu] сервер меню: {MENU_URL}")


def stop_menu_server():
    global _menu_server
    with _server_lock:
        if _menu_server is not None:
            _menu_server.shutdown()
            _menu_server.server_close()
            _menu_server = None
            print("[menu] сервер меню остановлен")


def open_menu():
    start_menu_server()
    webbrowser.open(MENU_URL)
    speak("Меню открыто, сэр.")


def close_menu():
    stop_menu_server()
    # пытаемся закрыть окно браузера с меню (Windows)
    if os.name == "nt":
        ps = (
            "Get-Process | Where-Object {$_.MainWindowTitle -like '*JARVIS*'} | "
            "ForEach-Object { $_.CloseMainWindow() | Out-Null }"
        )
        try:
            subprocess.run(["powershell", "-Command", ps], timeout=5)
        except Exception:
            pass
    speak("Меню закрыто.")


# ----------------------------------------------------------------------------
# Запуск программ (кроссплатформенно)
# ----------------------------------------------------------------------------
def launch_path(path):
    path = (path or "").strip().strip('"')
    if not path:
        return False, "empty path"
    try:
        if os.name == "nt":
            # .lnk / .exe через ассоциации Windows
            os.startfile(path)  # noqa
        else:
            subprocess.Popen(["xdg-open", path] if not path.endswith((".sh", ".AppImage"))
                             else [path], start_new_session=True)
        return True, "launched"
    except Exception as e:
        # запасной вариант
        try:
            cmd = {"nt": ["cmd", "/c", "start", "", path],
                   "posix": ["sh", "-c", f"xdg-open '{path}'"]}[
                "nt" if os.name == "nt" else "posix"]
            subprocess.Popen(cmd, start_new_session=True)
            return True, str(e)
        except Exception as e2:
            return False, f"{e} / {e2}"


def find_game(name):
    games = load_games()
    name_n = norm(name)
    best = None
    for g in games:
        gn = norm(g["name"])
        if name_n == gn or name_n in gn or gn in name_n:
            best = g
            break
    return best


def add_game(name, path=""):
    games = load_games()
    games.append({"name": name, "path": path, "icon": "", "emoji": "🎮"})
    save_games(games)
    print(f"[games] добавлена: {name} -> {path}")


def norm(s):
    s = s.lower().replace("ё", "е")
    return re.sub(r"[^\w\s]", " ", s).strip()


# ----------------------------------------------------------------------------
# Речь (TTS) — pyttsx3 если есть, иначе печать
# ----------------------------------------------------------------------------
_tts_engine = None


def init_tts():
    global _tts_engine
    try:
        import pyttsx3
        _tts_engine = pyttsx3.init()
        voices = _tts_engine.getProperty("voices")
        for v in voices:
            if "ru" in (v.id or "").lower() or "russian" in (getattr(v, "name", "") or "").lower():
                _tts_engine.setProperty("voice", v.id)
                break
    except Exception:
        _tts_engine = None


def speak(text):
    print(f"\n🤖 JARVIS: {text}")
    if _tts_engine:
        try:
            _tts_engine.say(text)
            _tts_engine.runAndWait()
        except Exception:
            pass


# ----------------------------------------------------------------------------
# Распознавание речи
# ----------------------------------------------------------------------------
def listen_loop(on_command):
    try:
        import speech_recognition as sr
    except ImportError:
        print("[!] speech_recognition не установлен — включаю ТЕКСТОВЫЙ режим.")
        text_mode(on_command)
        return

    recognizer = sr.Recognizer()
    recognizer.energy_threshold = 300
    recognizer.dynamic_energy_threshold = True

    try:
        with sr.Microphone() as src0:
            pass
    except OSError:
        print("[!] Микрофон не найден — включаю ТЕКСТОВЫЙ режим (печатайте команды).")
        text_mode(on_command)
        return

    speak("Система Джарвис активна. Скажите: Джарвис, открой меню.")
    while not STOP.is_set():
        try:
            with sr.Microphone() as source:
                recognizer.adjust_for_ambient_noise(source, duration=0.4)
                audio = recognizer.listen(source, timeout=8, phrase_time_limit=8)
            text = recognizer.recognize_google(audio, language="ru-RU")
            print(f"\n🎤 Вы: {text}")
            on_command(text)
        except sr.WaitTimeoutError:
            continue
        except sr.UnknownValueError:
            continue
        except sr.RequestError as e:
            print(f"[!] Сервис распознавания недоступен: {e}. Жду 3 c…")
            time.sleep(3)
        except KeyboardInterrupt:
            break


def text_mode(on_command):
    speak("Текстовый режим. Введите команду (exit — выход).")
    while not STOP.is_set():
        try:
            line = input("\n⌨️  Вы: ").strip()
        except (EOFError, KeyboardInterrupt):
            break
        if line.lower() in ("exit", "выход", "quit"):
            STOP.set()
            break
        if line:
            on_command(line)


STOP = threading.Event()


# ----------------------------------------------------------------------------
# Обработка команд
# ----------------------------------------------------------------------------
def handle_command(text):
    t = norm(text)
    has_wake = any(w in t for w in WAKE)

    # выход
    if re.search(r"\b(выключись|выключить себя|пока|до свидания|стоп джарвис)\b", t) and (has_wake or "джарвис" in t):
        STOP.set()
        speak("До встречи, сэр.")
        return
    if re.search(r"\b(jarvis)?\s*(выход)\b", t) and has_wake:
        STOP.set()
        speak("До встречи, сэр.")
        return

    if not has_wake:
        return  # команда не к нам

    # открыть меню
    if re.search(r"(открой|открыть|покажи|открывай)\b.*\b(меню|игр|game)", t):
        open_menu()
        return

    # закрыть меню
    if re.search(r"(закрой|закрыть|скрыть|убери)\b.*\bменю", t):
        close_menu()
        return

    # добавить игру: «Джарвис, добавь игру <название> [путь <путь> | <путь>]»
    if re.search(r"(добав\w*|запомни)", t):
        low = text.lower().replace("ё", "е")
        idx = -1
        for kw in ("игру ", "игра ", "game "):
            i = low.find(kw)
            if i >= 0:
                idx = i + len(kw)
                break
        if idx < 0:  # «добавь cyberpunk путь ...» — берём текст после слова «добавь/добавить»
            m0 = re.search(r"(?i)\b(добав\w*|запомни)\b", low)
            idx = m0.end() + 1
        rest = text[idx:].strip()
        pm = re.search(r"(?i)\b(?:путь|path)\b[:\s]*(.+)$", rest)
        if pm:
            name = rest[:pm.start()].strip(" ,")
            path_ = pm.group(1).strip('" ')
        else:
            parts = rest.split("|")
            name = parts[0].strip()
            path_ = parts[1].strip() if len(parts) > 1 else ""
        if not name:
            speak("Не расслышал название игры. Пример: Джарвис, добавь игру Ведьмак, путь D игры ведьмак.")
            return
        add_game(name, path_)
        if path_:
            speak(f"Игра {name} добавлена в меню, сэр.")
        else:
            speak(f"Игра {name} добавлена без пути. Откройте меню и укажите путь к файлу кнопкой «Добавить игру».")
        return

    # запустить игру
    m = re.search(r"(запуст\w*|открой|включ\w*|стартов\w*)\s+(?:игру\s+)?(.+?)\s*$", t)
    if m and re.search(r"(запуст|включ|стартов)", t):
        name = m.group(2)
        g = find_game(name)
        if g:
            ok, msg = launch_path(g["path"])
            speak(f"Запускаю {g['name']}." if ok else f"Не удалось запустить {g['name']}: {msg}")
        else:
            speak(f"Ярлык «{name}» не найден. Скажите: Джарвис, открой меню, и добавьте его.")
        return

    speak("Команда не распознана. Основные: «Джарвис, открой меню», «Джарвис, добавь игру …», «Джарвис, запусти …».")


# ----------------------------------------------------------------------------
# Точка входа
# ----------------------------------------------------------------------------
def main():
    print("=" * 62)
    print("  J.A.R.V.I.S. — голосовой помощник с игровым меню")
    print("  Команды: «Джарвис открой меню» / «добавь игру …» / «запусти …»")
    print("  Меню также открывается горячими клавишами Ctrl+Alt+M")
    print("=" * 62)
    init_tts()

    # горячие клавиши (необязательно)
    try:
        import keyboard
        keyboard.add_hotkey("ctrl+alt+m", open_menu)
        print("[hotkey] Ctrl+Alt+M — открыть меню")
    except Exception:
        pass

    mode = "text" if "--text" in sys.argv else "voice"
    if mode == "voice":
        listen_loop(handle_command)
    else:
        text_mode(handle_command)


if __name__ == "__main__":
    main()
