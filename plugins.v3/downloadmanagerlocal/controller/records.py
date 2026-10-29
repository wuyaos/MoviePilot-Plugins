"""记录查询的分页校验与 GET/POST 参数适配；不参与业务写入。"""

from fastapi import HTTPException


PAGE_SIZES = (20, 50, 100)


def record_query(page=1, page_size=20, result_filter="all", allowed_filters=("all",)):
    """拒绝非法值，不把错误请求静默归一化为第一页。"""
    values = []
    for name, value in (("page", page), ("page_size", page_size)):
        if isinstance(value, bool) or not isinstance(value, (int, str)):
            raise HTTPException(status_code=400, detail=f"{name} 必须是整数")
        try:
            number = int(value)
        except ValueError as error:
            raise HTTPException(status_code=400, detail=f"{name} 必须是整数") from error
        values.append(number)
    page, page_size = values
    if page < 1:
        raise HTTPException(status_code=400, detail="page 必须大于等于 1")
    if page_size not in PAGE_SIZES:
        raise HTTPException(status_code=400, detail="page_size 只支持 20/50/100")
    if result_filter not in allowed_filters:
        raise HTTPException(status_code=400, detail=f"未知 result_filter：{result_filter}")
    return page, page_size, result_filter


def record_page(items, page, page_size, result_filter):
    """items 必须已完成业务筛选及稳定排序。"""
    total = len(items)
    start = (page - 1) * page_size
    return {
        "items": items[start:start + page_size],
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": max(1, -(-total // page_size)),
        "result_filter": result_filter,
    }


def record_endpoint(handler, plugin):
    """同一路径接受 GET query / POST JSON；显式 query 优先于 body。

    同时接受旧客户端的平铺 JSON 与 data 包裹形态。detail_limit 保留为兼容
    参数，但不会截断记录，分页只由 page/page_size 决定。
    """
    def query(
        page: str | None = None,
        page_size: str | None = None,
        result_filter: str | None = None,
        detail_limit: str | None = None,
        payload: dict | None = None,
    ):
        body = payload if isinstance(payload, dict) else {}
        if "data" in body:
            if not isinstance(body["data"], dict):
                raise HTTPException(status_code=400, detail="data 必须是查询对象")
            body = body["data"]
        return handler(
            plugin,
            page=page if page is not None else body.get("page", 1),
            page_size=page_size if page_size is not None else body.get("page_size", 20),
            result_filter=result_filter if result_filter is not None else body.get("result_filter", "all"),
        )
    return query
