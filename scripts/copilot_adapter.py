#!/usr/bin/env python3
"""Адаптер к M365 Copilot (веб) через Playwright под залогиненной сессией: для second_opinion.py.
С ЯВНЫМ выбором сильной модели (никогда не оставляет "Auto"). Сохранённая сессия, окно для входа один раз,
дальше сам. Нужны Playwright (подтягивает `uv run --with playwright`) и установленный Microsoft Edge: адаптер
работает через него, браузер скачивать не нужно. Необязательный: без него цепочка второго мнения идёт дальше.

Подключение к цепочке: AI_TOOLKIT_COPILOT_CMD="uv run --with playwright python <путь>/scripts/copilot_adapter.py -"
(запрос читается со STDIN, ответ в STDOUT, вложения как --file).

Разовая авторизация (нужен браузер, делает человек):
    ! python scripts/copilot_adapter.py --login

Спросить (по умолчанию — новый чат, модель "gpt-latest" — НЕ Auto):
    python scripts/copilot_adapter.py "текст вопроса" [--model gpt-latest|auto|quick|think-deeper]
                                      [--out файл.md] [--continue] [--headless]
                                      [--wait-timeout 180]

Меню селектора модели Copilot Basic — ДВА уровня (снято вживую 04.08.2026):
  верхний уровень (radio):     Auto / Quick response / Think deeper
  пункт "GPT" (подменю):       GPT 5.6 Think deeper / GPT 5.5 Quick response — в момент
                                проверки; версии сдвигаются с обновлениями Microsoft.

  gpt-latest   — ПО УМОЛЧАНИЮ. Заходит в подменю "GPT" и берёт ПЕРВЫЙ (самый новый) пункт
                 ПО ПОЗИЦИИ, не по номеру версии — переживёт выход GPT 5.7 без правки кода.
                 Это явный выбор конкретной модели OpenAI, а не общий "Think deeper" Copilot.
  think-deeper — верхнеуровневый режим Copilot "Think longer for better answers" (не привязан
                 к конкретному провайдеру/версии) — используй, если нужно именно это, не GPT.
  auto         — "Decides how long to think" — САМ решает. НЕ использовать по умолчанию
                 (ровно то, от чего просили уйти — непредсказуемое качество/модель).
  quick        — "Answers right away" — быстро, но мельче.

⚠ Селекторы завязаны на текущую вёрстку m365.cloud.microsoft/chat. Если Microsoft поменяет
UI — сломается здесь первым; чинить по образцу accessibility-дампа страницы
(при поломке обновлять MODEL_MENU_LABEL/GPT_SUBMENU_TRIGGER/локаторы).

Кроссплатформенно (mac/win): профиль и пути из pathlib/HOME, без хардкода.
Запрос уходит в корпоративный M365 Copilot вашей организации; решение, какие данные туда можно, за вами.
"""
import argparse
import sys
import time
from pathlib import Path

PROFILE_DIR = Path.home() / ".cache" / "ai_toolkit_copilot_profile"
COPILOT_URL = "https://m365.cloud.microsoft/chat"

# Верхнеуровневый radio-список селектора модели (см. память
# m365-copilot-basic-capability-boundary про Auto).
MODEL_MENU_LABEL = {
    "auto": "Auto",
    "quick": "Quick response",
    "think-deeper": "Think deeper",
}
# "gpt-latest" — НЕ в MODEL_MENU_LABEL: у него нет статичного текста-метки, он выбирается
# ПОЗИЦИЕЙ внутри подменю "GPT" (см. _select_model) — первый пункт = самая новая версия.
GPT_SUBMENU_TRIGGER = "GPT"
ALL_MODELS = [*MODEL_MENU_LABEL, "gpt-latest"]
DEFAULT_MODEL = "gpt-latest"

_STOP_MARKERS = ("\nMessage Copilot", "\nAI-generated content may be incorrect")

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8")
    except (AttributeError, ValueError):
        pass


# ─────────────────────────────────────────────────────────────────────────────
# Чистое ядро (без Playwright) — tests/test_copilot_delegate.py
# ─────────────────────────────────────────────────────────────────────────────

def extract_last_answer(page_text: str) -> str:
    """Полный текст страницы (боковая панель + история + новый ответ) → текст
    ТОЛЬКО последнего ответа Copilot. Ищет последнее "Copilot said:", режет на
    первом попавшемся футере (поле ввода/дисклеймер)."""
    marker = "Copilot said:"
    idx = page_text.rfind(marker)
    if idx == -1:
        return ""
    answer = page_text[idx + len(marker):]
    cut = len(answer)
    for stop in _STOP_MARKERS:
        pos = answer.find(stop)
        if pos != -1:
            cut = min(cut, pos)
    return answer[:cut].strip()


_PROGRESS_RX = __import__("re").compile(
    r"^(in progress|sorting it out|thinking|reasoning|working on it|searching|generating|"
    r"looking|analy[sz]ing|gathering|reviewing)\b.{0,60}(…|\.\.\.)$", __import__("re").I | __import__("re").S)


def is_progress(answer: str) -> bool:
    """Статус «думаю» вместо ответа: одна короткая строка вида «In progress…»."""
    a = answer.strip()
    return len(a) < 80 and "\n" not in a and bool(_PROGRESS_RX.match(a))


# ─────────────────────────────────────────────────────────────────────────────
# Playwright-обёртки
# ─────────────────────────────────────────────────────────────────────────────

# Все локаторы ниже (get_by_role name=...) завязаны на АНГЛИЙСКИЙ текст UI Copilot.
# M365 рендерит интерфейс на языке Windows/аккаунта пользователя — на узле, где он не
# английский (напр. Server PC/homepc: RU), те же локаторы молча не находят элементы, хотя
# сессия рабочая (поймано вживую 05.08.2026 на homepc: страница грузится, "Message Copilot"
# не находится, потому что реальное имя — "Сообщение для Copilot"). Чинить локали по одной
# строкой — тупик (в UI минимум два места: textbox + Model Selector, и это лишь то, что уже
# нашли). Вместо этого форсируем locale/Accept-Language контекста — M365 подчиняется им и
# отдаёт английский UI независимо от языка ОС/аккаунта (проверено вживую на homepc: без
# этого — русский, с этим — "Message Copilot"/"Model Selector" на месте).
_BROWSER_LOCALE = "en-US"
_ACCEPT_LANGUAGE = {"Accept-Language": "en-US,en;q=0.9"}


LOCK_WAIT_S = 1200          # ждать чужой запрос не дольше 20 мин


class _ProfileLock:
    """Один браузерный профиль = один запрос за раз (04.10.2026: две сессии одновременно звали
    second_opinion → «Failed to create a ProcessSingleton», ревью падало вместо ожидания).
    fcntl.flock на файле рядом с профилем; на Windows (без fcntl) — без блокировки, как раньше."""

    def __init__(self, wait_s: float = LOCK_WAIT_S):
        self.wait_s, self.fh = wait_s, None

    def __enter__(self):
        try:
            import fcntl
        except ImportError:
            return self
        PROFILE_DIR.parent.mkdir(parents=True, exist_ok=True)
        self.fh = open(PROFILE_DIR.parent / (PROFILE_DIR.name + ".lock"), "a+")
        end = time.monotonic() + self.wait_s              # монотонные часы: перевод системных не влияет
        while True:
            try:
                fcntl.flock(self.fh, fcntl.LOCK_EX | fcntl.LOCK_NB)
                return self
            except BlockingIOError:
                left = end - time.monotonic()
                if left <= 0:
                    self.fh.close()
                    self.fh = None
                    raise RuntimeError("профиль Copilot занят другим запросом дольше "
                                       f"{self.wait_s / 60:.0f} мин — повтори позже")
                time.sleep(min(5.0, left))

    def __exit__(self, *exc):
        if self.fh is not None:
            self.fh.close()                  # закрытие снимает flock
        return False


def _new_context(p, headless):
    return p.chromium.launch_persistent_context(
        str(PROFILE_DIR), headless=headless, channel="msedge", no_viewport=True,
        locale=_BROWSER_LOCALE, extra_http_headers=_ACCEPT_LANGUAGE)


def do_login():
    from playwright.sync_api import sync_playwright
    PROFILE_DIR.mkdir(parents=True, exist_ok=True)
    print("Открываю браузер. Войди в M365 своей рабочей учёткой, потом вернись сюда.")
    with sync_playwright() as p:
        ctx = p.chromium.launch_persistent_context(
            str(PROFILE_DIR), headless=False, channel="msedge",
            args=["--start-maximized"], no_viewport=True,
            locale=_BROWSER_LOCALE, extra_http_headers=_ACCEPT_LANGUAGE)
        page = ctx.pages[0] if ctx.pages else ctx.new_page()
        page.goto(COPILOT_URL)
        deadline = time.time() + 300
        ok = False
        while time.time() < deadline:
            try:
                visible = page.get_by_role("textbox", name="Message Copilot").is_visible()
            except Exception:
                visible = False
            if visible:
                ok = True
                break
            time.sleep(2)
        ctx.close()
    if ok:
        print(f"✅ Сессия сохранена в {PROFILE_DIR}.")
        return 0
    print("⚠ Не увидел готового чата за 5 мин. Запусти ещё раз и доведи логин.")
    return 1


def _select_model(page, model: str) -> None:
    """Открыть селектор модели и явно выбрать пункт — НИКОГДА не оставлять то,
    что было выбрано раньше (может оказаться Auto из прошлой сессии).

    "gpt-latest" заходит в подменю "GPT" и берёт режим «Think deeper» (иначе первый
    пункт), не текст версии, чтобы не ломаться при выходе следующей GPT-модели."""
    page.get_by_role("button", name="Model Selector").click()
    if model == "gpt-latest":
        trigger = page.locator('[role="menuitem"]', has_text=GPT_SUBMENU_TRIGGER).first
        # 24.09.2026: подменю открывается с клавиатуры (focus + →), клик в headless его не
        # раскрывает; оно теперь второй role="menu", а не listbox. Оба набора menuitemradio
        # живут в DOM одновременно, поэтому берём пункт, чей текст начинается с «GPT».
        # 19.10.2026: пункты стали role="menuitem" (выбор в aria-checked), а в подменю два
        # режима одной модели — «GPT-x Quick response» и «GPT-x Think deeper». Берём Think
        # deeper (ревью), иначе первый GPT-пункт; «GPT-» отсекает сам триггер «GPT\nOpenAI».
        trigger.focus()
        page.keyboard.press("ArrowRight")
        import re as _re
        gpt = page.locator(_ITEMS, has_text=_re.compile(r"^\s*GPT-"))
        gpt.first.wait_for()
        deeper = gpt.filter(has_text="Think deeper").first
        try:
            deeper.wait_for(timeout=3000)    # подменю может дорисовываться по пунктам
        except Exception:                    # пункта нет вовсе: берём первый GPT
            gpt.first.click()
            return
        deeper.click()                       # сбой клика не глушим, модель не подменяем
        return
    label = MODEL_MENU_LABEL[model]
    page.locator(_ITEMS, has_text=label).first.click()


_ITEMS = '[role="menuitemradio"], [role="menuitem"]'


_FILE_OK = {".md", ".txt", ".pdf", ".docx", ".xlsx", ".pptx", ".csv", ".json", ".html", ".png", ".jpg", ".jpeg"}


def _prepare_files(files) -> tuple:
    """Файлы для загрузки в чат (кнопка «Upload images and files», проверено 19.10.2026: .md читает целиком).
    Архивы Copilot не принимает; код и прочий текст (.bsl, .diff, .py, .sql, .yaml…) копируем с суффиксом .txt."""
    import atexit, shutil, tempfile
    tmp = Path(tempfile.mkdtemp(prefix="copilot-files-"))
    atexit.register(shutil.rmtree, tmp, True)          # копии (в т.ч. приватных документов) не остаются в temp (ревью 19.10)
    out = []
    for f in files or []:
        f = Path(f).expanduser()
        if f.suffix.lower() in (".zip", ".7z", ".rar", ".tar", ".gz"):
            raise RuntimeError(f"архив {f.name} Copilot не принимает: распакуй и передай файлы по отдельности")
        dst = tmp / (f.name if f.suffix.lower() in _FILE_OK else f.name + ".txt")
        if dst.exists():                                # два файла с одним именем из разных каталогов (ревью 19.10)
            dst = tmp / f"{len(out) + 1}_{dst.name}"
        shutil.copy2(f, dst)
        out.append(str(dst))
    return tmp, out


def ask(prompt: str, model: str = DEFAULT_MODEL, new_chat: bool = True,
        headless: bool = False, wait_timeout: int = 180, files=None) -> str:
    if model not in ALL_MODELS:
        raise ValueError(f"неизвестная модель {model!r}, доступно: {ALL_MODELS}")
    if not PROFILE_DIR.exists():
        raise RuntimeError("Нет сессии. Сначала: ! python scripts/copilot_adapter.py --login")
    from playwright.sync_api import sync_playwright
    with _ProfileLock(), sync_playwright() as p:
        ctx = _new_context(p, headless)
        page = ctx.pages[0] if ctx.pages else ctx.new_page()
        page.goto(COPILOT_URL)
        try:
            # 24.09.2026: вход идёт через редирект login.microsoftonline и обратно, чат появляется за 25–40 с
            # wait_for рвётся на навигации редиректа («execution context destroyed»), поэтому опрос
            # 24.09.2026: SSO через раз виснет на «Trying to sign you in» (login.microsoftonline
            # …/reprocess) — через 30 с на странице входа заходим на Copilot заново, до 4 раз.
            ready, err, end, since, tries = False, "", time.time() + 180, time.time(), 0
            while time.time() < end and not ready:
                try:
                    ready = page.get_by_role("textbox", name="Message Copilot").count() > 0
                except Exception as e:           # страница как раз перезагружается
                    err = str(e)[:120]
                if not ready:
                    if "login.microsoftonline" in page.url and time.time() - since > 30 and tries < 4:
                        tries += 1; since = time.time()
                        try:
                            page.goto(COPILOT_URL)
                        except Exception as e:
                            err = str(e)[:120]
                    time.sleep(3)
            if not ready:
                shot = Path.home() / ".ai-toolkit" / "reviews" / "copilot-fail.png"
                shot.parent.mkdir(parents=True, exist_ok=True)
                try:                            # снимок страницы входа, только владельцу (0600 с момента создания)
                    import os as _os
                    data = page.screenshot()
                    fd = _os.open(shot, _os.O_WRONLY | _os.O_CREAT | _os.O_TRUNC, 0o600)
                    with _os.fdopen(fd, "wb") as fh:
                        fh.write(data)
                except Exception:
                    pass
                raise RuntimeError(f"{err or 'нет поля ввода'}; url={page.url[:70]}; снимок {shot}")
        except Exception as e:
            ctx.close()
            raise RuntimeError(
                f"Не дождался чата M365 Copilot ({str(e)[:120]}; сессия протухла?). "
                "Повтори: ! python scripts/copilot_adapter.py --login")

        if new_chat:
            new_chat_btn = page.get_by_role("button", name="New chat")
            if new_chat_btn.count():
                new_chat_btn.first.click()

        time.sleep(3)                       # чат дорисовывается после редиректа, элементы пересоздаются
        for attempt in range(3):            # 24.09.2026: «element was detached from the DOM» на первом клике
            try:
                _select_model(page, model)
                break
            except Exception:
                if attempt == 2:
                    raise
                page.keyboard.press("Escape"); time.sleep(3)

        tmpdir = None
        if files:
            tmpdir, paths = _prepare_files(files)
            page.locator("input[type=file]").first.set_input_files(paths)
            total_kb = sum(Path(x).stat().st_size for x in paths) // 1024
            time.sleep(6 + 2 * len(paths) + total_kb // 40)   # загрузка вложений (19.10: 4 файла 380 КБ за 12 с не успели)

        box = page.get_by_role("textbox", name="Message Copilot")
        box.click()
        box.fill(prompt)
        send = page.get_by_role("button", name="Send")      # 24.09.2026: Enter больше не отправляет
        if send.count():
            send.first.click()
        else:
            box.press("Enter")

        deadline = time.time() + wait_timeout
        last_text, stable_since = "", None
        while time.time() < deadline:
            time.sleep(2)
            cur = page.locator("main").inner_text()
            # 24.09.2026: Think deeper подолгу держит статус «In progress…/Sorting it out…», текст
            # стоит на месте, и прежняя проверка «4 с без изменений» принимала статус за ответ.
            busy = (not extract_last_answer(cur) or is_progress(extract_last_answer(cur))
                    or page.get_by_role("button", name="Stop generating").count() > 0)
            if cur == last_text and not busy:
                if stable_since is None:
                    stable_since = time.time()
                elif time.time() - stable_since >= 6:
                    break
            else:
                stable_since = None
            last_text = cur

        answer = extract_last_answer(last_text)
        try:                                    # подсказки-кнопки после ответа («Предложи ещё варианты»)
            chips = {b.inner_text().strip() for b in page.get_by_role("button").all()}
            lines = answer.rstrip().split("\n")
            while lines and (not lines[-1].strip() or lines[-1].strip() in chips):
                lines.pop()
            answer = "\n".join(lines)
        except Exception:
            pass
        ctx.close()
        return answer


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("prompt", nargs="?", help="текст вопроса Copilot")
    ap.add_argument("--login", action="store_true")
    ap.add_argument("--model", choices=ALL_MODELS, default=DEFAULT_MODEL)
    ap.add_argument("--continue", dest="continue_chat", action="store_true",
                     help="не начинать новый чат, продолжить последний открытый")
    ap.add_argument("--headless", action="store_true")
    ap.add_argument("--wait-timeout", type=int, default=180)
    ap.add_argument("--out", help="сохранить ответ в файл (кроме stdout)")
    ap.add_argument("--file", action="append", default=[], metavar="ПУТЬ",
                    help="приложить файл к вопросу (повторять); Copilot читает его целиком, лимит 28 тыс. знаков не касается")
    a = ap.parse_args()

    if a.login:
        return do_login()
    if a.prompt == "-":
        a.prompt = sys.stdin.read()
    if not a.prompt:
        ap.error("нужен текст вопроса (или - для STDIN) либо --login")

    try:
        answer = ask(a.prompt, model=a.model, new_chat=not a.continue_chat,
                     headless=a.headless, wait_timeout=a.wait_timeout, files=a.file)
    except RuntimeError as e:
        print(f"⚠ {e}", file=sys.stderr)
        return 2

    if not answer:
        print("⚠ Не нашёл ответ Copilot на странице (селекторы могли устареть).", file=sys.stderr)
        return 1

    print(answer)
    if a.out:
        Path(a.out).write_text(answer, encoding="utf-8")
        print(f"\n✅ Сохранено: {a.out}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
