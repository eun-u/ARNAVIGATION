from __future__ import annotations

import argparse
import json
import sys
import tempfile
import urllib.request
from pathlib import Path

from playwright.sync_api import Page, sync_playwright


BASE_URL = "http://127.0.0.1:8000"

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")


def get_demo() -> dict:
    with urllib.request.urlopen(f"{BASE_URL}/graph", timeout=10) as response:
        return json.load(response)["metadata"]["demo"]


def set_demo_edge(edge_id: str, blocked: bool) -> None:
    payload = json.dumps(
        {
            "blocked": blocked,
            "reason": "construction" if blocked else None,
            "status_source": "manual",
            "verified": False,
            "actor": "ui-smoke",
        }
    ).encode("utf-8")
    request = urllib.request.Request(
        f"{BASE_URL}/edges/{edge_id}/status",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="PATCH",
    )
    with urllib.request.urlopen(request, timeout=10):
        pass


def page_metrics(page: Page) -> dict:
    return page.evaluate(
        """
        () => {
          const root = document.documentElement;
          const candidates = [...document.querySelectorAll('button, select, summary, a, textarea, label')]
            .filter((el) => {
              const style = getComputedStyle(el);
              return el.offsetParent !== null && !el.hidden && style.display !== 'none' && style.visibility !== 'hidden';
            });
          const smallTargets = candidates
            .map((el) => {
              const box = el.getBoundingClientRect();
              return {
                id: el.id || '',
                label: (el.getAttribute('aria-label') || el.textContent || '').trim().slice(0, 32),
                tag: el.tagName,
                width: Math.round(box.width),
                height: Math.round(box.height),
              };
            })
            .filter((item) => item.width < 44 || item.height < 44);
          return {
            overflow: root.scrollWidth - root.clientWidth,
            scrollWidth: root.scrollWidth,
            clientWidth: root.clientWidth,
            scrollY: Math.round(window.scrollY),
            scrollHeight: root.scrollHeight,
            smallTargets,
          };
        }
        """
    )


def capture(page: Page, output_dir: Path, results: list[dict], name: str, errors: list[str], extra: dict | None = None) -> None:
    path = output_dir / f"{name}.png"
    page.screenshot(path=str(path), full_page=True)
    results.append(
        {
            "viewport": name,
            "screenshot": str(path),
            "page_errors": list(errors),
            **(extra or {}),
            **page_metrics(page),
        }
    )


def run_flow(page: Page, output_dir: Path, results: list[dict], prefix: str, expected_after: int, full_trace: bool) -> None:
    page_errors: list[str] = []
    page.on("pageerror", lambda error: page_errors.append(str(error)))
    page.goto(BASE_URL, wait_until="domcontentloaded")
    page.wait_for_function("document.querySelector('#mobile-app')?.dataset.source === 'live'", timeout=15_000)
    page.wait_for_timeout(320)
    capture(page, output_dir, results, f"{prefix}-welcome", page_errors)

    page.locator("#enter-app-button").click()
    page.wait_for_function("document.querySelector('#home-screen')?.hidden === false")
    page.wait_for_timeout(220)
    capture(page, output_dir, results, f"{prefix}-home", page_errors)
    if full_trace:
        page.locator(".home-header [data-go='settings']").click()
        page.wait_for_function("document.querySelector('#settings-screen')?.hidden === false")
        page.wait_for_timeout(220)
        capture(page, output_dir, results, f"{prefix}-settings", page_errors)
        page.locator("[data-setting='contrast']").click()
        page.locator(".settings-header [data-go='home']").click()
        page.wait_for_function("document.querySelector('#home-screen')?.hidden === false")
    page.locator(".route-portal").click()
    page.wait_for_function("document.querySelector('#plan-screen')?.hidden === false")
    page.wait_for_timeout(320)
    capture(page, output_dir, results, f"{prefix}-plan", page_errors)

    page.locator("#find-route-button").click()
    page.wait_for_function("document.querySelector('#route-screen')?.hidden === false")
    page.wait_for_function("document.querySelector('#accessible-distance')?.textContent !== '—'", timeout=15_000)
    page.wait_for_timeout(650)
    capture(page, output_dir, results, f"{prefix}-route", page_errors)

    if full_trace:
        page.locator("#open-explain-button").click()
        page.wait_for_function("document.querySelector('#explain-screen')?.hidden === false")
        page.wait_for_timeout(320)
        capture(page, output_dir, results, f"{prefix}-explain", page_errors)
        page.go_back()
        page.wait_for_function("document.querySelector('#route-screen')?.hidden === false")
        page.go_forward()
        page.wait_for_function("document.querySelector('#explain-screen')?.hidden === false")
        page.locator("[data-go='navigate']").click()
    else:
        page.locator("#start-ar-button").click()

    page.wait_for_function("document.querySelector('#ar-screen')?.hidden === false")
    page.wait_for_timeout(2_800)
    capture(page, output_dir, results, f"{prefix}-ar", page_errors)

    page.locator("#simulate-obstacle-button").click()
    page.wait_for_function(
        f"document.querySelector('#remaining-distance')?.textContent.replace(/[^0-9]/g, '') === '{expected_after}'",
        timeout=15_000,
    )
    page.wait_for_timeout(450)
    capture(
        page,
        output_dir,
        results,
        f"{prefix}-reroute",
        page_errors,
        {
            "distance": page.locator("#remaining-distance").inner_text(),
            "banner_visible": page.locator("#reroute-banner").is_visible(),
        },
    )

    if full_trace:
        page.locator("#report-from-ar-button").click()
        page.wait_for_function("document.querySelector('#report-screen')?.hidden === false")
        page.wait_for_timeout(320)
        page.locator(".report-types label").first.click()
        page.locator("#report-note").fill("보도 공사로 통행 폭이 좁아 보입니다. 현장 검수가 필요합니다.")
        capture(page, output_dir, results, f"{prefix}-report", page_errors)
        page.locator("#save-report-button").click()
        page.wait_for_function("document.querySelector('#report-complete')?.hidden === false")
        page.wait_for_timeout(220)
        capture(
            page,
            output_dir,
            results,
            f"{prefix}-report-saved",
            page_errors,
            {
                "local_drafts": page.evaluate("JSON.parse(localStorage.getItem('navi.reportDrafts') || '[]').length"),
                "local_only_copy": page.locator("#report-complete").inner_text(),
            },
        )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path, default=Path(tempfile.gettempdir()) / "navi-mobile-ui-qa")
    args = parser.parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)

    demo = get_demo()
    demo_edge = demo["block_edge"]
    expected_after = round(demo["expected"]["accessible_after"]["distance_m"])
    set_demo_edge(demo_edge, False)
    results: list[dict] = []

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        viewports = [
            ("mobile-360", 360, 800, False),
            ("mobile-390", 390, 844, True),
            ("mobile-430", 430, 932, False),
            ("tablet-1024", 1024, 900, False),
        ]
        for prefix, width, height, full_trace in viewports:
            context = browser.new_context(viewport={"width": width, "height": height}, locale="ko-KR")
            page = context.new_page()
            run_flow(page, args.output_dir, results, prefix, expected_after, full_trace)
            context.close()
            set_demo_edge(demo_edge, False)

        fallback_context = browser.new_context(viewport={"width": 390, "height": 844}, locale="ko-KR")
        fallback_page = fallback_context.new_page()
        fallback_errors: list[str] = []
        fallback_page.on("pageerror", lambda error: fallback_errors.append(str(error)))
        fallback_page.route("**/graph", lambda route: route.abort())
        fallback_page.goto(BASE_URL, wait_until="domcontentloaded")
        fallback_page.wait_for_function("document.querySelector('#system-fallback')?.hidden === false", timeout=15_000)
        fallback_page.locator("#continue-demo-button").click()
        fallback_page.wait_for_function("document.querySelector('#mobile-app')?.dataset.source === 'demo'")
        fallback_page.locator("#enter-app-button").click()
        fallback_page.wait_for_function("document.querySelector('#home-screen')?.hidden === false")
        fallback_page.locator(".route-portal").click()
        fallback_page.locator("#find-route-button").click()
        fallback_page.wait_for_function("document.querySelector('#route-screen')?.hidden === false")
        fallback_page.wait_for_timeout(500)
        capture(
            fallback_page,
            args.output_dir,
            results,
            "mobile-390-demo-fallback",
            fallback_errors,
            {"data_source": fallback_page.locator("#mobile-app").get_attribute("data-source")},
        )
        fallback_context.close()

        context = browser.new_context(viewport={"width": 390, "height": 844}, locale="ko-KR")
        page = context.new_page()
        page_errors: list[str] = []
        page.on("pageerror", lambda error: page_errors.append(str(error)))
        page.goto(f"{BASE_URL}/review", wait_until="domcontentloaded")
        page.wait_for_selector(".candidate-card", timeout=15_000)
        capture(page, args.output_dir, results, "review-mobile", page_errors, {"cards": page.locator(".candidate-card").count()})
        context.close()
        browser.close()

    print(json.dumps(results, ensure_ascii=False, indent=2))
    failures = [result for result in results if result.get("overflow") != 0 or result.get("page_errors") or result.get("smallTargets")]
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
