from __future__ import annotations

import json
import re
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SKILL_DIR = PROJECT_ROOT / "third_party" / "skills" / "frontend-design"
CSS_PATH = PROJECT_ROOT / "static" / "app.css"
JS_PATH = PROJECT_ROOT / "static" / "app.js"
HTML_PATH = PROJECT_ROOT / "templates" / "index.html"
REPORT_PATH = PROJECT_ROOT / "models" / "frontend_skill_report.json"


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    skill = (SKILL_DIR / "SKILL.md").read_text(encoding="utf-8")
    license_text = (SKILL_DIR / "LICENSE.txt").read_text(encoding="utf-8")
    css = CSS_PATH.read_text(encoding="utf-8")
    javascript = JS_PATH.read_text(encoding="utf-8")
    html = HTML_PATH.read_text(encoding="utf-8")

    checks = {
        "skill_present": "# Frontend Design" in skill,
        "apache_license_present": "Apache License" in license_text,
        "central_color_tokens": all(
            token in css
            for token in ["--color-bg", "--color-text", "--color-accent"]
        ),
        "spacing_tokens": "--space-1" in css and "--space-7" in css,
        "radius_tokens": "--radius-sm" in css and "--radius-lg" in css,
        "shadow_token": "--shadow-matte" in css,
        "no_css_gradient": "gradient" not in css.lower(),
        "no_glow": "glow" not in css.lower(),
        "keyboard_focus": ":focus-visible" in css,
        "reduced_motion": "prefers-reduced-motion" in css,
        "responsive_layout": "@media (max-width: 800px)" in css,
        "single_page_heading": len(re.findall(r"<h1\b", html)) == 1,
        "plain_text_brand": 'class="brand" href="/">岗位匹配</a>' in html,
        "grayscale_check": "grayscale-check" in css and "grayscale-check" in javascript,
    }
    result = {
        "skill": "frontend-design",
        "source": "https://github.com/anthropics/claude-plugins-official",
        "commit": "a1ecfbc7f138a0ef455088f7f28cda2d22a0f853",
        "license": "Apache-2.0",
        "checks": checks,
        "passed": all(checks.values()),
    }
    REPORT_PATH.write_text(
        json.dumps(result, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if not result["passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
