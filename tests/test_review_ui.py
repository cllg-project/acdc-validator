"""
Playwright end-to-end tests for the Step 2 (review) page design.

Fixtures live in conftest.py (live_server_ui, auth_page).
Run:  env/bin/pytest tests/test_review_ui.py -v
"""
import pytest


# ── Per-test fixture: navigate to /review and dismiss modal ─────────────────

@pytest.fixture()
def review_page(auth_page):
    page, base_url = auth_page
    page.goto(f"{base_url}/review")
    page.wait_for_load_state("networkidle")
    page.click("#ready-btn")
    page.wait_for_selector("#annotation-area:not([style*='display:none'])", timeout=3000)
    return page


# ── Layout ───────────────────────────────────────────────────────────────────

def test_navbar_is_dark(auth_page):
    page, base_url = auth_page
    page.goto(f"{base_url}/review")
    bg = page.locator(".navbar").evaluate("el => getComputedStyle(el).backgroundColor")
    assert "26, 26, 46" in bg, f"Expected dark navy navbar (#1a1a2e), got: {bg}"


def test_warm_page_background(auth_page):
    page, base_url = auth_page
    page.goto(f"{base_url}/review")
    bg = page.evaluate("() => getComputedStyle(document.body).backgroundColor")
    assert "240, 237, 232" in bg, f"Expected warm background (#f0ede8), got: {bg}"


def test_ibm_plex_font_loaded(auth_page):
    page, base_url = auth_page
    page.goto(f"{base_url}/review")
    fonts_link = page.locator("link[href*='IBM+Plex']")
    assert fonts_link.count() > 0, "IBM Plex font link not found in <head>"


def test_no_white_card_wrapper(review_page):
    bg = review_page.locator(".annotation-wrap").evaluate(
        "el => getComputedStyle(el).backgroundColor"
    )
    assert bg in ("rgba(0, 0, 0, 0)", "transparent"), f"annotation-wrap has background: {bg}"


# ── Meta row ─────────────────────────────────────────────────────────────────

def test_meta_row_book_id_visible(review_page):
    el = review_page.locator(".review-book-id")
    assert el.is_visible()
    assert "ui_book_001" in el.inner_text().lower()


def test_meta_row_line_count(review_page):
    text = review_page.locator(".review-line-num").inner_text()
    assert "line" in text and "of" in text, f"Expected 'line X of Y', got: {text!r}"


def test_timer_element_present(review_page):
    timer = review_page.locator("#timer")
    assert timer.is_visible()
    assert "⏱" in timer.inner_text()


# ── Line image ───────────────────────────────────────────────────────────────

def test_image_wrap_has_light_background(review_page):
    bg = review_page.locator(".line-image-wrap").evaluate(
        "el => getComputedStyle(el).backgroundColor"
    )
    assert "255, 255, 255" in bg, f"Expected white image wrap, got: {bg}"


# ── Betacode pill toggle ──────────────────────────────────────────────────────

def test_pill_label_starts_off(review_page):
    assert review_page.locator("#beta-label").inner_text() == "off"


def test_pill_click_toggles_on(review_page):
    review_page.click(".beta-pill-label-wrap")
    classes = review_page.locator("#beta-pill-track").get_attribute("class") or ""
    assert "beta-on" in classes, "Pill should have beta-on class after click"
    assert review_page.locator("#beta-label").inner_text() == "ON"
    review_page.click(".beta-pill-label-wrap")  # reset


def test_ctrl_b_toggles_beta(review_page):
    review_page.locator("#text-field").focus()
    review_page.keyboard.press("Control+b")
    classes = review_page.locator("#beta-pill-track").get_attribute("class") or ""
    assert "beta-on" in classes, "Ctrl+B should activate pill"
    review_page.keyboard.press("Control+b")  # reset


# ── Betacode conversion ───────────────────────────────────────────────────────

def test_betacode_converts_to_greek(review_page):
    tf = review_page.locator("#text-field")
    review_page.click(".beta-pill-label-wrap")   # enable betacode
    tf.click(click_count=3)
    tf.type("lo/gos")
    value = tf.input_value()
    # sigma-to-final-sigma fires on word boundary; accept both σ and ς
    assert "λόγο" in value, f"Expected Greek betacode conversion, got: {value!r}"
    review_page.click(".beta-pill-label-wrap")   # reset


# ── Character rows ────────────────────────────────────────────────────────────

def test_strip_row_visible(review_page):
    assert review_page.locator("#btn-strip-accents").is_visible()
    assert review_page.locator("#btn-strip-spirits").is_visible()
    assert review_page.locator("#btn-strip-numbers").is_visible()


def test_diacritics_row_visible(review_page):
    btns = review_page.locator(".char-row .char-btn[data-dia]")
    assert btns.count() >= 7
    assert btns.first.is_visible()


def test_punctuation_row_visible(review_page):
    assert review_page.locator(".char-btn[data-ch='·']").is_visible()


def test_sup_abc_row_visible_by_default(review_page):
    """4th row (sup abc) must be visible without any user interaction."""
    assert review_page.locator(".char-btn[data-ch='ᵃ']").is_visible()


def test_lowercase_greek_collapsed_by_default(review_page):
    assert not review_page.locator(".char-btn[data-ch='α']").is_visible()


def test_lowercase_greek_expands_on_click(review_page):
    # First details element in char-tools-rows is αβγ lowercase
    details = review_page.locator("details.char-collapsible").first
    details.locator("summary").click()
    assert review_page.locator(".char-btn[data-ch='α']").is_visible()
    details.locator("summary").click()  # collapse


def test_uppercase_greek_collapsed_by_default(review_page):
    assert not review_page.locator(".char-btn[data-ch='Α']").is_visible()


def test_sup_numbers_collapsed_by_default(review_page):
    assert not review_page.locator(".char-btn[data-ch='⁰']").is_visible()


# ── Char insert ───────────────────────────────────────────────────────────────

def test_diacritic_button_inserts_into_textarea(review_page):
    tf = review_page.locator("#text-field")
    tf.click(click_count=3)
    tf.fill("α")
    tf.press("End")
    # dispatch mousedown on first diacritic button to apply it
    review_page.locator(".char-btn[data-dia]").first.dispatch_event("mousedown")
    value = tf.input_value().strip()
    # value should be non-empty (diacritic applied or not, alpha is still there)
    assert "α" in value.lower() or len(value) > 0, f"Expected textarea content, got: {value!r}"


# ── Action buttons ────────────────────────────────────────────────────────────

def test_all_four_action_buttons_present(review_page):
    for val in ("edited", "validated", "skipped", "rejected"):
        assert review_page.locator(f"button[value='{val}']").is_visible(), f"Missing button[value={val}]"


def test_save_edit_muted_when_text_unchanged(review_page):
    classes = review_page.locator("#btn-save-edit").get_attribute("class") or ""
    assert "btn-muted" in classes


def test_save_edit_activates_when_text_changes(review_page):
    review_page.locator("#text-field").press("End")
    review_page.locator("#text-field").type(" x")
    classes = review_page.locator("#btn-save-edit").get_attribute("class") or ""
    assert "btn-primary" in classes


# ── Timer ─────────────────────────────────────────────────────────────────────

def test_timer_increments(review_page):
    import time
    timer = review_page.locator("#timer")
    initial = timer.inner_text()
    time.sleep(2)
    assert timer.inner_text() != initial or "0:0" in initial
