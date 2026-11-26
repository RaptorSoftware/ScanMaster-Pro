"""Проверка сайта перед публикацией: python tests/check_site.py

Без зависимостей. Код 0 и «OK» — всё в порядке; код 1 и список ошибок — нет.
Следит за тем, на что опирается выпуск новых версий: значок версии, список
возможностей feat-N, ссылка скачивания, тексты на обоих языках, картинки.
"""

import json
import re
import subprocess
import sys
from html.parser import HTMLParser
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DOWNLOAD = "https://github.com/RaptorSoftware/ScanMaster-Pro/releases/latest/download/ScanMaster.Pro.exe"
LANGS = ("ru", "en")


class Page(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.i18n_keys, self.attr_keys, self.shots, self.ids = [], [], [], []
        self.refs, self.hrefs, self.badges, self.features = [], [], [], []
        self.json_blocks = {}
        self._json_id, self._badge, self._badge_text = None, False, ""

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if "data-i18n" in a:
            self.i18n_keys.append(a["data-i18n"])
        for pair in (a.get("data-i18n-attr") or "").split(";"):
            if ":" in pair:
                self.attr_keys.append(pair.split(":", 1)[1].strip())
        if "data-shot" in a:
            self.shots.append(a["data-shot"])
        if "id" in a:
            self.ids.append(a["id"])
        for key in ("src", "href"):
            if a.get(key):
                self.refs.append(a[key])
        if tag == "a" and a.get("href"):
            self.hrefs.append(a["href"])
        if "version-badge" in (a.get("class") or "").split():
            self._badge, self._badge_text = True, ""
        if tag == "script" and a.get("type") == "application/json":
            self._json_id = a.get("id")
            self.json_blocks[self._json_id] = ""
        if tag == "span" and (a.get("data-i18n") or "").startswith("feat-"):
            self.features.append(a["data-i18n"])

    def handle_endtag(self, tag):
        if self._badge:
            self.badges.append(self._badge_text.strip())
            self._badge = False
        if tag == "script":
            self._json_id = None

    def handle_data(self, data):
        if self._badge:
            self._badge_text += data
        if self._json_id is not None:
            self.json_blocks[self._json_id] += data


def is_local(ref: str) -> bool:
    return not re.match(r"^(https?:|mailto:|data:|#|//)", ref)


def check(root: Path = ROOT) -> list:
    errors = []
    page = Page()
    page.feed((root / "index.html").read_text(encoding="utf-8"))

    texts = {}
    try:
        texts = json.loads(page.json_blocks.get("i18n", ""))
    except ValueError as error:
        errors.append(f"JSON i18n не разбирается: {error}")
    if texts:
        missing_lang = [lang for lang in LANGS if not isinstance(texts.get(lang), dict)]
        errors += [f"в i18n нет языка {lang}" for lang in missing_lang]
        if not missing_lang:
            ru, en = set(texts["ru"]), set(texts["en"])
            errors += [f"ключ {k} есть в ru, но нет в en" for k in sorted(ru - en)]
            errors += [f"ключ {k} есть в en, но нет в ru" for k in sorted(en - ru)]
            for key in sorted(set(page.i18n_keys + page.attr_keys) - (ru & en)):
                errors.append(f"нет перевода для {key}")

    if len(page.badges) != 1:
        errors.append(f"version-badge должен быть ровно один, найдено {len(page.badges)}")
    elif not re.fullmatch(r"v\d+\.\d+\.\d+", page.badges[0]):
        errors.append(f"version-badge «{page.badges[0]}» — ожидается вид vX.Y.Z")

    numbers = sorted(int(f.split("-")[1]) for f in page.features if re.fullmatch(r"feat-\d+", f))
    if len(numbers) < 12 or numbers != list(range(1, len(numbers) + 1)):
        errors.append(f"feat-N должны идти подряд с 1 и их не меньше 12: {numbers}")

    for ref in page.refs:
        if is_local(ref):
            path = root / ref.split("#")[0].split("?")[0]
            if not path.exists():
                errors.append(f"нет файла {ref}")
    for name in sorted(set(page.shots)):
        for lang in LANGS:
            if not (root / "shots" / lang / f"{name}.webp").exists():
                errors.append(f"нет снимка shots/{lang}/{name}.webp")

    if page.hrefs.count(DOWNLOAD) < 2:
        errors.append("ссылка скачивания должна встречаться не меньше двух раз")
    bad = [h for h in page.hrefs if "releases" in h and "download" in h and h != DOWNLOAD]
    errors += [f"неверная ссылка скачивания: {h}" for h in bad]
    if "about" not in page.ids:
        errors.append("нет якоря id=\"about\" (на него ведёт кнопка «Перейти на сайт» в программе)")

    try:
        releases = json.loads(page.json_blocks.get("releases", ""))
        if not isinstance(releases, list):
            raise ValueError("ожидается массив")
        for item in releases:
            ok = (isinstance(item, dict) and item.get("version")
                  and all(isinstance(item.get(f), dict) and all(item[f].get(l) for l in LANGS)
                          for f in ("date", "title", "text")))
            if not ok:
                errors.append(f"запись releases неполная: {item}")
    except ValueError as error:
        errors.append(f"JSON releases не разбирается: {error}")

    diff = subprocess.run(["git", "diff", "--quiet", "origin/main", "--", "version.json"],
                          cwd=root, capture_output=True)
    if diff.returncode == 1:
        errors.append("version.json изменён относительно origin/main — его правит только выпуск")
    return errors


def main() -> int:
    errors = check()
    for error in errors:
        print("ОШИБКА:", error)
    print("OK" if not errors else f"ошибок: {len(errors)}")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
