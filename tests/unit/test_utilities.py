from register_your_data_api.utilities import find_item_in_suitecrm_response


def test_find_item_in_suitecrm_response_none() -> None:
    r = None
    id = "some-id"
    result = find_item_in_suitecrm_response(r, id)
    assert result is None


def test_find_item_in_suitecrm_response_not_found() -> None:
    r = {"data": [{"id": "id-1"}, {"id": "id-2"}]}
    id = "id-3"
    result = find_item_in_suitecrm_response(r, id)
    assert result is None


def test_find_item_in_suitecrm_response_found() -> None:
    r = {"data": [{"id": "id-1"}, {"id": "id-2"}]}
    id = "id-2"
    result = find_item_in_suitecrm_response(r, id)
    assert result == {"id": "id-2"}


def test_find_item_in_suitecrm_id_none_returns_none() -> None:
    r = {"data": [{"id": "id-1"}, {"id": "id-2"}]}
    id = None
    result = find_item_in_suitecrm_response(r, id)
    assert result is None
