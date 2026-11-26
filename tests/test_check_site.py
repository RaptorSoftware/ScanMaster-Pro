"""Тесты проверки сайта: ловит поломки выпуска и не поднимает ложных тревог.

Запуск: python -m pytest tests -q
"""

import re
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from check_site import ROOT, check  # noqa: E402


def site_copy(tmp_path: Path) -> Path:
    """Копия сайта вне git-репозитория."""
    target = tmp_path / "site"
    shutil.copytree(ROOT, target, ignore=shutil.ignore_patterns(".git", ".superpowers", "__pycache__"))
    return target


def edit(site: Path, old: str, new: str) -> None:
    page = site / "index.html"
    text = page.read_text(encoding="utf-8")
    assert old in text
    page.write_text(text.replace(old, new, 1), encoding="utf-8")


def badge(site: Path) -> str:
    return re.search(r'class="version-badge">([^<]+)<', (site / "index.html").read_text(encoding="utf-8")).group(1)


def test_current_site_passes():
    assert check(ROOT) == []


def test_copy_outside_git_raises_no_false_alarm(tmp_path):
    assert check(site_copy(tmp_path)) == []


def test_badge_must_match_latest_release(tmp_path):
    site = site_copy(tmp_path)
    edit(site, f'class="version-badge">{badge(site)}<', 'class="version-badge">v9.9.9<')
    assert any("releases" in error and "9.9.9" in error for error in check(site))


def test_missing_english_text_is_reported(tmp_path):
    site = site_copy(tmp_path)
    edit(site, '"final-button": "Download ScanMaster Pro",', "")
    assert any("final-button" in error for error in check(site))


def test_badge_suffix_is_reported(tmp_path):
    site = site_copy(tmp_path)
    edit(site, f'class="version-badge">{badge(site)}<', f'class="version-badge">{badge(site)} Stable<')
    assert any("version-badge" in error for error in check(site))
