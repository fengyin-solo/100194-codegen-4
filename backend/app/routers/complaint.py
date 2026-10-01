"""社区噪音光影投诉台账接口：登记投诉、查重合并、提交答复与超期督办。"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Query

from app.schemas import ActionResult, EntryPayload, PageResult
from app.services.complaint import ComplaintService

router = APIRouter(prefix="/api/complaint", tags=["社区投诉台账"])

service = ComplaintService()

STATUSES = ["待答复", "已答复"]


@router.get("", response_model=PageResult[dict])
def list_entries(
    keyword: str | None = Query(default=None, description="按投诉编号、投诉来源或投诉类型检索"),
    status: str | None = Query(default=None, description="待答复、已答复"),
    page: int = 1,
    size: int = 20,
) -> PageResult[dict]:
    """按关键词与状态过滤投诉台账；检索不到时返回空页，由前端给出空态提示。"""
    if size > 200:
        raise HTTPException(status_code=400, detail="每页最多 200 条，请缩小分页范围")
    items, total = service.list_entries(keyword=keyword, status=status, page=page, size=size)
    return PageResult(items=items, total=total, page=page, size=size)


@router.get("/supervision")
def supervision_entries() -> dict[str, Any]:
    """督办清单：超过答复期限仍未答复的主记录，时限按最早受理时间计算。"""
    items = service.supervision_entries()
    return {"module": "complaint", "total": len(items), "items": items}


@router.get("/summary")
def summary() -> dict[str, int]:
    """台账概览：待答复、督办中与重复合并数量，答复成功后随列表一起刷新。"""
    return service.summary()


@router.get("/export")
def export_entries() -> dict[str, Any]:
    """导出投诉台账清单：返回当前全量数据。"""
    items, total = service.list_entries(page=1, size=10000)
    return {"module": "complaint", "total": total, "items": items}


@router.get("/{entry_id}", response_model=dict)
def get_entry(entry_id: int) -> dict:
    """读取单条投诉明细（含重复投诉记录）；不存在时给出可读的错误说明。"""
    entry = service.get_entry(entry_id)
    if entry is None:
        raise HTTPException(status_code=404, detail=f"投诉记录 {entry_id} 不存在或已归档")
    return entry


@router.post("", response_model=ActionResult)
def create_entry(payload: EntryPayload) -> ActionResult:
    """登记一条社区投诉；投诉来源、影响时段等必填字段缺失时不允许提交并说明原因。"""
    entry, missing, outcome = service.create_entry(payload.values)
    if missing:
        return ActionResult(ok=False, message=f"缺少或非法的必填字段：{'、'.join(missing)}")
    if outcome == "merged" and entry is not None:
        return ActionResult(
            ok=True,
            message=(
                f"与主记录 {entry.get('投诉编号')} 为重复投诉，已并入该记录统一答复；"
                f"督办时限按最早受理时间 {entry.get('受理时间')} 计算"
            ),
            entry=entry,
        )
    return ActionResult(ok=True, message="社区投诉已登记", entry=entry)


@router.post("/{entry_id}/actions", response_model=ActionResult)
def run_action(entry_id: int, payload: EntryPayload) -> ActionResult:
    """对单条投诉提交答复；校验不通过时说明原因，前端保留已填内容可重试。"""
    action = str(payload.values.get("action") or "").strip()
    entry, message = service.run_action(entry_id, action, payload.values)
    if entry is None:
        return ActionResult(ok=False, message=message)
    return ActionResult(ok=True, message=message, entry=entry)
