import fitz

from report_to_json.images import make_tag, offload_images, reconcile_tags, render_masked_page
from report_to_json.storage import LocalDeepStorage, StoredImage, build_manifest

from conftest import make_image_bytes


def _record(tag="[IMAGE_PAGE_1_FIG_1]", bbox=(50, 100, 250, 200)):
    return StoredImage(tag=tag, page=1, figure=1, sha256="x", uri="u", format="png", width=10, height=10,
                       bbox=list(bbox))


def test_storage_is_content_addressed_and_idempotent(tmp_path):
    store = LocalDeepStorage(tmp_path)
    sha1, uri1 = store.put(b"same bytes", "png")
    sha2, uri2 = store.put(b"same bytes", "png")
    assert (sha1, uri1) == (sha2, uri2)
    assert store.get(sha1) == b"same bytes"
    assert len(list((tmp_path / "objects").rglob("*.png"))) == 1


def test_offload_stores_images_and_tags_each_placement(report_pdf, tmp_path):
    store = LocalDeepStorage(tmp_path)
    images = offload_images(str(report_pdf), store).figures
    [record] = images[3]
    assert record.tag == "[IMAGE_PAGE_3_FIG_1]" == make_tag(3, 1)
    assert record.bbox is not None and store.get(record.sha256)

    path = store.write_manifest("doc-1", build_manifest("doc-1", "acme.pdf", images[3]))
    manifest = store.read_manifest("doc-1")
    assert manifest["images"]["[IMAGE_PAGE_3_FIG_1]"]["sha256"] == record.sha256
    assert path.endswith("doc-1.json")


def test_duplicate_image_on_two_pages_is_stored_once(tmp_path):
    pdf = tmp_path / "dup.pdf"
    doc = fitz.open()
    logo = make_image_bytes((100, 100))
    for _ in range(2):
        doc.new_page().insert_image(fitz.Rect(50, 50, 150, 150), stream=logo)
    doc.save(str(pdf))
    images = offload_images(str(pdf), LocalDeepStorage(tmp_path / "store")).figures
    assert images[1][0].sha256 == images[2][0].sha256
    assert len(list((tmp_path / "store" / "objects").rglob("*.*"))) == 1


def test_masked_render_covers_the_image(report_pdf, tmp_path):
    images = offload_images(str(report_pdf), LocalDeepStorage(tmp_path)).figures
    with fitz.open(str(report_pdf)) as doc:
        page = doc[2]
        plain = render_masked_page(page, [], dpi=72)
        masked = render_masked_page(page, images[3], dpi=72)
    x0, y0, x1, y1 = images[3][0].bbox
    corner = (int(x0) + 3, int(y0) + 3)  # inside the box, away from the label text
    assert plain.getpixel(corner) != (255, 255, 255)   # the blue test image
    assert masked.getpixel(corner) == (255, 255, 255)  # replaced by the white placeholder box


def test_reconcile_tags_fixes_misreads_and_restores_dropped_tags():
    expected = [_record("[IMAGE_PAGE_1_FIG_1]"), _record("[IMAGE_PAGE_1_FIG_2]")]
    text, issues = reconcile_tags("Evidence:\n[lMAGE PAGE 1 FIG 1]\nend", expected)
    assert "[IMAGE_PAGE_1_FIG_1]" in text and "lMAGE" not in text
    assert text.rstrip().endswith("[IMAGE_PAGE_1_FIG_2]")
    assert any("misread" in i for i in issues) and any("not transcribed" in i for i in issues)


def test_reconcile_tags_is_silent_when_everything_is_right():
    text, issues = reconcile_tags("a\n[IMAGE_PAGE_1_FIG_1]\nb", [_record()])
    assert issues == [] and text == "a\n[IMAGE_PAGE_1_FIG_1]\nb"


def test_small_placements_are_layout_not_figures(tmp_path):
    # e.g. a table header rasterised into thin slices: stored, but left visible for the model to read
    pdf = tmp_path / "slices.pdf"
    doc = fitz.open()
    page = doc.new_page()
    page.insert_image(fitz.Rect(50, 50, 65, 200), stream=make_image_bytes((30, 300)))
    page.insert_image(fitz.Rect(100, 300, 400, 500), stream=make_image_bytes((300, 200), (10, 200, 10)))
    doc.save(str(pdf))
    offload = offload_images(str(pdf), LocalDeepStorage(tmp_path / "store"))
    assert [r.tag for r in offload.all_figures()] == ["[IMAGE_PAGE_1_FIG_1]"]
    assert len(offload.layout) == 1 and offload.layout[0].tag == ""
    manifest = build_manifest("d", "slices.pdf", offload.all_figures(), offload.layout)
    assert len(manifest["layout_images"]) == 1
