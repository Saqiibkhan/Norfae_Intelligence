from app.models import Expense
from app.core.tenant_context import tenant_scope


def register(client, email):
    return client.post("/auth/register", json={"email": email, "password": "correct-horse-battery-staple", "business_name": email.split("@")[0]})


def headers(auth):
    return {"Authorization": f"Bearer {auth.json()['access_token']}", "X-Business-ID": str(auth.json()["business"]["id"])}


def upload(client, headers, data, filename="statement.csv", mapping=None):
    return client.post("/expenses/import/preview", headers=headers,
        data={"mapping": mapping or '{"date":"Transaction Date","amount":"Total","description":"Details","category":"Type","reference":"Txn"}'},
        files={"file": (filename, data, "text/csv")})


def test_preview_then_confirm_imports_only_after_confirmation(api_client):
    owner = register(api_client, "csv-owner@example.com")
    csv_data = b"Transaction Date,Total,Details,Type,Txn\n2026-11-01,4500.125,Packaging,Operations,PK-001\n"
    preview = upload(api_client, headers(owner), csv_data)
    assert preview.status_code == 200, preview.text
    body = preview.json()
    assert (body["total_rows"], body["valid_rows"], body["importable_rows"]) == (1, 1, 1)
    with tenant_scope(owner.json()["business"]["id"]):
        with api_client.session_factory() as db:
            assert db.query(Expense).count() == 0
    confirm = api_client.post("/expenses/import/confirm", headers=headers(owner), data={"preview_id": body["preview_id"], "confirm": "true"})
    assert confirm.status_code == 200, confirm.text
    assert confirm.json()["imported_rows"] == 1
    with tenant_scope(owner.json()["business"]["id"]):
        with api_client.session_factory() as db:
            row = db.query(Expense).one()
            assert row.amount == 4500.13
            assert row.source == "csv_import"
            assert row.category == "Operations"
    repeated = api_client.post("/expenses/import/confirm", headers=headers(owner), data={"preview_id": body["preview_id"], "confirm": "true"})
    assert repeated.status_code == 409


def test_bom_mapping_and_duplicate_reference_preview(api_client):
    owner = register(api_client, "csv-duplicate@example.com")
    data = b"\xef\xbb\xbfDay,Value,What,Ref\n11/01/2026,12.50,Courier,R-1\n11/02/2026,8.00,Boxes,R-1\n"
    mapping = '{"date":"Day","amount":"Value","description":"What","reference":"Ref"}'
    result = upload(api_client, headers(owner), data, mapping=mapping)
    assert result.status_code == 200, result.text
    assert result.json()["duplicate_rows"] == 1
    assert result.json()["importable_rows"] == 1


def test_preview_is_business_and_user_scoped(api_client):
    owner = register(api_client, "csv-scope-owner@example.com")
    other = register(api_client, "csv-scope-other@example.com")
    result = upload(api_client, headers(owner), b"Transaction Date,Total,Details\n2026-11-01,5,Rent\n",
                    mapping='{"date":"Transaction Date","amount":"Total","description":"Details"}')
    preview_id = result.json()["preview_id"]
    denied = api_client.post("/expenses/import/confirm", headers=headers(other), data={"preview_id": preview_id, "confirm": "true"})
    assert denied.status_code == 404


def test_upload_validation_errors_are_explicit(api_client):
    owner = register(api_client, "csv-invalid@example.com")
    invalid = upload(api_client, headers(owner), b"Transaction Date,Total,Details\nnot-a-date,-5,\n",
                     mapping='{"date":"Transaction Date","amount":"Total","description":"Details"}')
    assert invalid.status_code == 200
    summary = invalid.json()
    assert summary["invalid_rows"] == 1
    assert summary["importable_rows"] == 0
    errors = summary["row_results"][0]["errors"]
    assert any("date" in e.lower() for e in errors)
    assert any("negative" in e.lower() for e in errors)
    assert any("description" in e.lower() for e in errors)


def test_bad_upload_and_mapping_rejected(api_client):
    owner = register(api_client, "csv-file-invalid@example.com")
    response = upload(api_client, headers(owner), b"hello", filename="not.csv")
    assert response.status_code == 400
    missing = upload(api_client, headers(owner), b"A,B\n1,2\n", mapping='{"date":"A","amount":"B","description":"Missing"}')
    assert missing.status_code == 400
