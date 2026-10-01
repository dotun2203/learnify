from rest_framework.pagination import CursorPagination, PageNumberPagination


class DefaultPagination(PageNumberPagination):
    page_size = 20
    page_size_query_param = "page_size"
    max_page_size = 100


class TimelineCursorPagination(CursorPagination):
    """For long, append-only lists (messages, students)."""

    page_size = 50
    ordering = "-created_at"
