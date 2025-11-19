from unittest import mock

import pytest
from starlette.datastructures import URL

from register_your_data_api.response_schemas import PaginatedResultsPage


@pytest.mark.parametrize(
    "page_num,page_size,total_records,expected_pages,expected_first,expected_last,expected_next,expected_prev",
    [
        (1, 1, 50, 50, "/?page=1&page_size=1", "/?page=50&page_size=1", "/?page=2&page_size=1", None),
        (1, 10, 50, 5, "/?page=1&page_size=10", "/?page=5&page_size=10", "/?page=2&page_size=10", None),
        (
            3,
            20,
            80,
            4,
            "/?page=1&page_size=20",
            "/?page=4&page_size=20",
            "/?page=4&page_size=20",
            "/?page=2&page_size=20",
        ),
        (5, 10, 50, 5, "/?page=1&page_size=10", "/?page=5&page_size=10", None, "/?page=4&page_size=10"),
    ],
)
def test_paging_result_page_values(
    page_num: int,
    page_size: int,
    total_records: int,
    expected_pages: int,
    expected_first: str,
    expected_last: str,
    expected_next: str,
    expected_prev: str,
) -> None:

    request = mock.MagicMock()
    request.url = URL("/").include_query_params(page=page_num, page_size=page_size)

    page = PaginatedResultsPage.create(["item"] * page_size, page_num, page_size, total_records, request)

    assert page.pagination.page == page_num
    assert page.pagination.page_size == page_size
    assert page.pagination.total_pages == expected_pages
    assert page.pagination.total_records == total_records

    assert page.pagination.links.first and page.pagination.links.first == expected_first
    assert page.pagination.links.last and page.pagination.links.last == expected_last
    assert (page.pagination.links.next and page.pagination.links.next == expected_next) or (
        page.pagination.links.next is None
    )
    assert (page.pagination.links.prev and page.pagination.links.prev == expected_prev) or (
        page.pagination.links.prev is None
    )
