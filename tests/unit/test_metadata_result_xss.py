import ast
from dataclasses import asdict, dataclass
from pathlib import Path
from urllib.parse import urlsplit


REPO_ROOT = Path(__file__).resolve().parents[2]


@dataclass
class MetadataSource:
    id: str
    description: str
    link: str


@dataclass
class MetadataResult:
    id: str
    title: str
    authors: list[str]
    url: str
    source: MetadataSource
    cover: str
    description: str


def _load_serializers():
    source_path = REPO_ROOT / "cps/search_metadata.py"
    module = ast.parse(source_path.read_text(encoding="utf-8"), filename=str(source_path))
    functions = [
        node
        for node in module.body
        if isinstance(node, ast.FunctionDef)
        and node.name
        in {"_safe_metadata_url", "_sanitize_metadata_record", "_serialize_metadata_records"}
    ]
    namespace = {"asdict": asdict, "urlsplit": urlsplit}
    exec(compile(ast.Module(body=functions, type_ignores=[]), str(source_path), "exec"), namespace)
    return namespace


def test_metadata_serializer_filters_provider_controlled_urls_for_flat_api_records():
    serializers = _load_serializers()
    result = MetadataResult(
        id="provider-id",
        title="<img src=x onerror=alert(1)>",
        authors=["<svg onload=alert(1)>"],
        url="javascript:alert(1)",
        source=MetadataSource(
            id="provider",
            description="<script>alert(1)</script>",
            link="data:text/html,<script>alert(1)</script>",
        ),
        cover="javascript:alert(1)",
        description="<img src=x onerror=alert(1)>",
    )

    serialized = serializers["_serialize_metadata_records"]([result])

    assert serialized == [
        {
            "id": "provider-id",
            "title": "<img src=x onerror=alert(1)>",
            "authors": ["<svg onload=alert(1)>"],
            "url": "",
            "source": {
                "id": "provider",
                "description": "<script>alert(1)</script>",
                "link": "",
            },
            "cover": "",
            "description": "<img src=x onerror=alert(1)>",
        }
    ]


def test_metadata_serializer_keeps_http_and_local_urls():
    serializers = _load_serializers()

    assert serializers["_safe_metadata_url"](" https://example.test/book ") == "https://example.test/book"
    assert serializers["_safe_metadata_url"]("/static/cover.jpg") == "/static/cover.jpg"
    assert serializers["_safe_metadata_url"]("mailto:author@example.test") == ""
    assert serializers["_safe_metadata_url"]("data:image/svg+xml,<svg>") == ""


def test_metadata_result_template_escapes_actual_book_fields():
    template = (REPO_ROOT / "cps/templates/book_edit.html").read_text(encoding="utf-8")
    result_template = template.split('id="template-book-result">', 1)[1].split("</script>", 1)[0]

    assert '<%- book.cover ||' in result_template
    assert '<%- book.source.link %>' in result_template
    assert '<%- book.source.description %>' in result_template
    assert '<%- book.url %>' in result_template
    assert '<%- book.title %>' in result_template
    assert '<%- (book.authors || []).join(" & ") %>' in result_template
    assert '<%- book.description %>' in result_template

    for field in ("book.cover", "book.url", "book.title", "book.description"):
        assert f"<%= {field} %>" not in result_template


def test_metadata_endpoints_use_sanitizing_serializer():
    source = (REPO_ROOT / "cps/search_metadata.py").read_text(encoding="utf-8")

    assert "jsonify(_serialize_metadata_records(data))" in source
    assert "data.extend(_serialize_metadata_records(result))" in source
