import os
import pytest
from xml.etree import ElementTree as ET


# ── pytest-playwright: use system Chrome on hosts where playwright chromium
#    isn't available (e.g. Ubuntu 26 which is not yet in playwright's matrix)
@pytest.fixture(scope="session")
def browser_type_launch_args(browser_type_launch_args):
    return {**browser_type_launch_args, "channel": "chrome"}

FIXTURES_DIR = os.path.join(os.path.dirname(__file__), "fixtures")


# ── Playwright UI fixtures ──────────────────────────────────────────────────

@pytest.fixture(scope="module")
def live_server_ui(tmp_path_factory):
    """Flask server with a temp SQLite DB seeded with a reviewable line."""
    import threading
    from werkzeug.serving import make_server
    from app import create_app, db as _db
    from app.models import User, Line, Annotation

    db_path = tmp_path_factory.mktemp("ui") / "test_ui.db"

    test_app = create_app({
        "TESTING": True,
        "SQLALCHEMY_DATABASE_URI": f"sqlite:///{db_path}",
        "DATA_PATH": FIXTURES_DIR,
        "SECRET_KEY": "test-ui-secret",
        "WTF_CSRF_ENABLED": False,
    })

    with test_app.app_context():
        _db.create_all()

        user = User(username="uitester")
        user.set_password("uitest123")
        _db.session.add(user)
        _db.session.flush()

        line = Line(
            book_id="ui_book_001",
            page_png="sample_alto.xml",
            page_jpg="sample_alto.xml",
            alto_xml="sample_alto.xml",
            line_index=5,
            hpos=100, vpos=200, width=500, height=50,
            polygon_points="100,200 600,200 600,250 100,250",
            ocr_text="σύνεσις δὲ ἀγαθή",
        )
        _db.session.add(line)
        _db.session.flush()

        ann = Annotation(user_id=user.id, line_id=line.id, status="skip_edited")
        _db.session.add(ann)
        _db.session.commit()

    server = make_server("127.0.0.1", 0, test_app)
    port = server.socket.getsockname()[1]
    t = threading.Thread(target=server.serve_forever, daemon=True)
    t.start()

    yield f"http://127.0.0.1:{port}"

    server.shutdown()


@pytest.fixture(scope="module")
def auth_page(live_server_ui, browser):
    """Playwright page authenticated as uitester, yields (page, base_url)."""
    page = browser.new_page()
    page.goto(f"{live_server_ui}/login")
    page.fill("input[name=username]", "uitester")
    page.fill("input[name=password]", "uitest123")
    page.click("button[type=submit]")
    page.wait_for_load_state("networkidle")
    yield page, live_server_ui
    page.close()
ALTO_NS = "http://www.loc.gov/standards/alto/ns-v4#"


@pytest.fixture(scope="session")
def app():
    from app import create_app, db as _db

    test_app = create_app(
        {
            "TESTING": True,
            "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
            "DATA_PATH": FIXTURES_DIR,
            "WTF_CSRF_ENABLED": False,
        }
    )
    with test_app.app_context():
        _db.create_all()
        yield test_app
        _db.drop_all()


@pytest.fixture()
def db(app):
    from app import db as _db
    yield _db
    _db.session.rollback()


@pytest.fixture()
def loaded_lines(app, db):
    """Ingest sample_alto.xml into the test DB, yielding the Line rows."""
    from app.models import Line

    xml_rel = "sample_alto.xml"
    xml_abs = os.path.join(FIXTURES_DIR, xml_rel)
    book_id = "test_book"

    tree = ET.parse(xml_abs)
    root = tree.getroot()
    text_lines = root.findall(f".//{{{ALTO_NS}}}TextLine")

    inserted = []
    for idx, tl in enumerate(text_lines):
        string_el = tl.find(f"{{{ALTO_NS}}}String")
        if string_el is None:
            continue
        ocr_text = string_el.get("CONTENT", "").strip()
        if not ocr_text:
            continue

        polygon_el = tl.find(f".//{{{ALTO_NS}}}Polygon")
        points = polygon_el.get("POINTS", "") if polygon_el is not None else ""

        hpos = int(string_el.get("HPOS", tl.get("HPOS", 0)))
        vpos = int(string_el.get("VPOS", tl.get("VPOS", 0)))
        width = int(string_el.get("WIDTH", tl.get("WIDTH", 0)))
        height = int(string_el.get("HEIGHT", tl.get("HEIGHT", 0)))

        line = Line(
            book_id=book_id,
            page_png="test_page.png",
            page_jpg="test_page.jpg",
            alto_xml=xml_rel,
            line_index=idx,
            hpos=hpos,
            vpos=vpos,
            width=width,
            height=height,
            polygon_points=points,
            ocr_text=ocr_text,
        )
        db.session.add(line)
        inserted.append(line)

    db.session.commit()
    yield inserted

    for line in inserted:
        db.session.delete(line)
    db.session.commit()
