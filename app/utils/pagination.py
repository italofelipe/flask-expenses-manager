from typing import Any, Dict, List


class PaginatedResponse:
    @staticmethod
    def format(
        data: List[Any], total: int, page: int, page_size: int
    ) -> Dict[str, Any]:
        return {
            "data": data,
            "total": total,
            "page": page,
            "page_size": page_size,
            "has_next_page": page * page_size < total,
        }
