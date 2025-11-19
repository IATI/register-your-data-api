from typing import Generic, Sequence, TypeVar

from starlette.datastructures import URL
from starlette.requests import Request

from register_your_data_api.data_handling.data_schemas import BaseResponse, PaginationInfo, PaginationLinks

T = TypeVar("T")


class PaginatedResultsPage(BaseResponse, Generic[T]):
    data: Sequence[T]
    pagination: PaginationInfo

    @classmethod
    def create(
        cls,
        data: Sequence[T],
        page: int,
        page_size: int,
        total_records: int,
        request: Request | None = None,
    ) -> "PaginatedResultsPage[T]":

        base_url = request.url.remove_query_params(["page", "page_size"]) if request else URL("")

        # This is always validated earlier in the request handling process
        if page_size == 0:
            raise ValueError("page_size must be greater than 0")

        total_pages = -(-total_records // page_size)

        next_page_url = None
        if page < total_pages:
            next_page_url = str(base_url.include_query_params(page=page + 1, page_size=page_size))

        prev_page_url = None
        if page > 1:
            prev_page_url = str(base_url.include_query_params(page=min(page - 1, total_pages), page_size=page_size))

        return cls(
            data=data,
            status="success",
            error=None,
            pagination=PaginationInfo(
                page=page,
                page_size=page_size,
                total_pages=total_pages,
                total_records=total_records,
                links=PaginationLinks(
                    first=str(base_url.include_query_params(page=1, page_size=page_size)),
                    last=str(base_url.include_query_params(page=total_pages, page_size=page_size)),
                    next=next_page_url,
                    prev=prev_page_url,
                ),
            ),
        )

        return page
