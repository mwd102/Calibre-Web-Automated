"""The upload endpoint serves both XHR and normal browser form submissions."""

from flask import Flask

from cps.editbooks import _upload_response


def test_native_upload_redirects_to_result_page():
    app = Flask(__name__)
    with app.test_request_context("/upload", method="POST"):
        response = _upload_response("/tasks")

    assert response.status_code == 303
    assert response.location == "/tasks"


def test_xhr_upload_preserves_json_destination():
    app = Flask(__name__)
    with app.test_request_context(
        "/upload", method="POST", headers={"X-Requested-With": "XMLHttpRequest"}
    ):
        response = _upload_response("/tasks")

    assert response.status_code == 200
    assert response.get_json() == {"location": "/tasks"}
