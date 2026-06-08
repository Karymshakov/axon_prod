from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response


class ConfigurablePageNumberPagination(PageNumberPagination):
    """
    Custom pagination with configurable page sizes.

    Query params:
    - page: Page number (default: 1)
    - page_size: Items per page (default: 25, allowed: 10, 25, 50, 100)
    """
    page_size = 25
    page_size_query_param = 'page_size'
    max_page_size = 100

    ALLOWED_PAGE_SIZES = [10, 25, 50, 100]

    def get_page_size(self, request):
        if self.page_size_query_param:
            try:
                page_size = int(request.query_params.get(self.page_size_query_param, self.page_size))
                if page_size in self.ALLOWED_PAGE_SIZES:
                    return page_size
            except (KeyError, ValueError):
                pass
        return self.page_size

    def get_paginated_response(self, data):
        return Response({
            'count': self.page.paginator.count,
            'total_pages': self.page.paginator.num_pages,
            'current_page': self.page.number,
            'page_size': self.get_page_size(self.request),
            'next': self.get_next_link(),
            'previous': self.get_previous_link(),
            'results': data,
        })
