"""社区噪音光影投诉台账接口：登记、检索、答复与超期督办。"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Query

from app.schemas import ActionResult, EntryPayload, PageResult
from app.services.complaint import ComplaintService

router = APIRouter(prefix="/api/complaint", tags=["投诉台账"])

service = ComplaintService()

LIST_FIELDS = ["投诉编号", "投诉来源", "受理时间", "影响时段", "核查结论", "答复期限", "重复投诉数", "状态"]
STATUSES = ["待答复", "已答复"]


@router.get("", response_model=PageResult[dict])
def list_entries(
    keyword: str | None = Query(default=None, description="按投诉编号、投诉来源、影响时段或核查结论检索"),
    status: str | None = Query(default=None, description="待答复、已答复"),
    page: int = 1,
    size: int = 20,
) -> PageResult[dict]:
    """按关键词与状态过滤投诉台账；检索不到时返回空页，由前端给出空态提示。"""
    if size > 200:
        raise HTTPException(status_code=400, detail="每页最多 200 条，请缩小分页范围")
    items, total = service.list_entries(keyword=keyword, status=status, page=page, size=size)
    return PageResult(items=items, total=total, page=page, size=size)


@router.get("/stats")
def stats() -> dict[str, int]:
    """台账统计：待答复、超期督办、已答复与累计重复投诉数。"""
    return service.stats()


@router.get("/supervision")
def supervision() -> dict[str, Any]:
    """超期未答复的督办清单：按答复期限升序，最紧急的排前面。"""
    items = service.supervision()
    return {"items": items, "total": len(items)}


@router.get("/export")
def export_entries() -> dict[str, Any]:
    """导出投诉台账：返回当前全量主记录，重复投诉已并入主记录。"""
    items, total = service.list_entries(page=1, size=10000)
    return {"module": "complaint", "total": total, "items": items}


@router.get("/{entry_id}", response_model=dict)
def get_entry(entry_id: int) -> dict:
    """读取单条投诉主记录；不存在时给出可读的错误说明。"""
    entry = service.get_entry(entry_id)
    if entry is None:
        raise HTTPException(status_code=404, detail=f"投诉记录 {entry_id} 不存在或已归档")
    return entry


@router.post("", response_model=ActionResult)
def create_entry(payload: EntryPayload) -> ActionResult:
    """登记投诉；投诉来源或影响时段缺失时说明原因，重复投诉并入既有主记录。"""
    entry, message, ok = service.create_entry(payload.values)
    return ActionResult(ok=ok, message=message, entry=entry)


@router.post("/{entry_id}/actions", response_model=ActionResult)
def run_action(entry_id: int, payload: EntryPayload) -> ActionResult:
    """对单条投诉提交答复；核查结论为空或重复答复会被拦下并说明原因。"""
    action = str(payload.values.get("action") or "").strip()
    entry, message, ok = service.run_action(entry_id, action, payload.values)
    return ActionResult(ok=ok, message=message, entry=entry)
