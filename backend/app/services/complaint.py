"""社区噪音光影投诉台账业务规则：登记校验、重复归并、答复流转与超期督办口径。"""
from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

from app.store import store

MODULE = "complaint"
REQUIRED_FIELDS = ["投诉来源", "影响时段"]
SOURCES = ["噪音投诉", "光影投诉"]
STATUS_PENDING = "待答复"
STATUS_REPLIED = "已答复"
REPLY_LIMIT = timedelta(days=3)
TIME_FORMAT = "%Y-%m-%d %H:%M"
TIME_INPUT_FORMATS = ["%Y-%m-%d %H:%M", "%Y-%m-%dT%H:%M", "%Y-%m-%d"]
REPLY_ACTION = "提交答复"


def _parse_time(value: Any) -> datetime | None:
    text = str(value or "").strip()
    if not text:
        return None
    for fmt in TIME_INPUT_FORMATS:
        try:
            return datetime.strptime(text, fmt)
        except ValueError:
            continue
    return None


def _fmt(moment: datetime) -> str:
    return moment.strftime(TIME_FORMAT)


class ComplaintService:
    def __init__(self) -> None:
        # 超期督办随时间变化，运营概览汇总前先按当前时间重算各行标记。
        store.register_refresher(self.refresh)

    def refresh(self) -> None:
        now = datetime.now()
        for row in store.rows(MODULE):
            replied = row.get("status") == STATUS_REPLIED
            row["pending"] = not replied
            deadline = _parse_time(row.get("答复期限"))
            row["abnormal"] = bool(not replied and deadline is not None and now > deadline)
            row["状态"] = str(row.get("status") or STATUS_PENDING)

    def list_entries(
        self,
        *,
        keyword: str | None = None,
        status: str | None = None,
        page: int = 1,
        size: int = 20,
    ) -> tuple[list[dict[str, Any]], int]:
        self.refresh()
        rows = store.rows(MODULE)
        if keyword:
            rows = [
                row
                for row in rows
                if any(
                    keyword in str(row.get(field, ""))
                    for field in ("投诉编号", "投诉来源", "影响时段", "核查结论")
                )
            ]
        if status:
            rows = [row for row in rows if row.get("status") == status]
        total = len(rows)
        start = max(page - 1, 0) * size
        return rows[start:start + size], total

    def get_entry(self, entry_id: int) -> dict[str, Any] | None:
        self.refresh()
        return store.find(MODULE, entry_id)

    def create_entry(self, values: dict[str, Any]) -> tuple[dict[str, Any] | None, str, bool]:
        missing = [field for field in REQUIRED_FIELDS if not str(values.get(field) or "").strip()]
        if missing:
            return None, f"缺少必填字段：{'、'.join(missing)}，投诉来源与影响时段缺失时不允许登记", False
        source = str(values.get("投诉来源") or "").strip()
        if source not in SOURCES:
            return None, f"投诉来源「{source}」不在受理范围，只支持：{'、'.join(SOURCES)}", False
        accepted_text = str(values.get("受理时间") or "").strip()
        accepted = _parse_time(accepted_text) if accepted_text else datetime.now()
        if accepted is None:
            return None, "受理时间格式不正确，请使用 2026-10-01 08:30 这样的格式", False
        period = str(values.get("影响时段") or "").strip()
        # 重复投诉归并：同一投诉来源且影响时段一致时，挂到既有主记录下统一答复。
        for row in store.rows(MODULE):
            if str(row.get("投诉来源")) == source and str(row.get("影响时段")) == period:
                row["重复投诉数"] = int(row.get("重复投诉数", 0)) + 1
                row.setdefault("重复受理记录", []).append(_fmt(accepted))
                earliest = _parse_time(row.get("受理时间"))
                if earliest is None or accepted < earliest:
                    row["受理时间"] = _fmt(accepted)
                    row["答复期限"] = _fmt(accepted + REPLY_LIMIT)
                self.refresh()
                if row.get("status") == STATUS_REPLIED:
                    return row, f"与主记录 {row['投诉编号']} 属重复投诉，已并入；该记录已答复，核查结论沿用主记录", True
                return row, f"与主记录 {row['投诉编号']} 属重复投诉，已并入统一办理，督办时限按最早受理时间 {row['受理时间']} 计算", True
        rows = store.rows(MODULE)
        entry: dict[str, Any] = {"id": max((int(row.get("id", 0)) for row in rows), default=0) + 1}
        entry["投诉编号"] = f"COMP-{entry['id']:04d}"
        entry["投诉来源"] = source
        entry["受理时间"] = _fmt(accepted)
        entry["影响时段"] = period
        entry["核查结论"] = ""
        entry["答复期限"] = _fmt(accepted + REPLY_LIMIT)
        entry["重复投诉数"] = 0
        entry["重复受理记录"] = [_fmt(accepted)]
        entry["答复时间"] = ""
        entry["status"] = STATUS_PENDING
        rows.append(entry)
        self.refresh()
        return entry, f"投诉已登记，答复期限 {entry['答复期限']}", True

    def run_action(
        self, entry_id: int, action: str, values: dict[str, Any]
    ) -> tuple[dict[str, Any] | None, str, bool]:
        self.refresh()
        entry = store.find(MODULE, entry_id)
        if entry is None:
            return None, f"投诉记录 {entry_id} 不存在或已归档", False
        if action != REPLY_ACTION:
            return None, f"动作「{action}」不属于投诉台账可执行范围", False
        if entry.get("status") == STATUS_REPLIED:
            return None, "该投诉已答复，核查结论已存档，无需重复提交", False
        conclusion = str(values.get("核查结论") or "").strip()
        if not conclusion:
            return None, "核查结论不能为空，请补充核查结论后再提交答复", False
        entry["核查结论"] = conclusion
        entry["答复时间"] = _fmt(datetime.now())
        entry["status"] = STATUS_REPLIED
        self.refresh()
        return entry, "答复已提交，督办清单与运营概览的待答复数量已同步更新", True

    def supervision(self) -> list[dict[str, Any]]:
        """超期未答复的督办清单，按答复期限升序，最紧急的排前面。"""
        self.refresh()
        now = datetime.now()
        items: list[dict[str, Any]] = []
        for row in store.rows(MODULE):
            if not row.get("abnormal"):
                continue
            deadline = _parse_time(row.get("答复期限"))
            hours = int((now - deadline).total_seconds() // 3600) if deadline else 0
            items.append({**row, "超期小时": hours})
        items.sort(key=lambda item: str(item.get("答复期限") or ""))
        return items

    def stats(self) -> dict[str, int]:
        self.refresh()
        rows = store.rows(MODULE)
        return {
            "待答复": sum(1 for row in rows if row.get("pending")),
            "超期督办": sum(1 for row in rows if row.get("abnormal")),
            "已答复": sum(1 for row in rows if row.get("status") == STATUS_REPLIED),
            "重复投诉": sum(int(row.get("重复投诉数", 0)) for row in rows),
        }
