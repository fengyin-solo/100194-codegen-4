"""社区噪音光影投诉台账业务规则：登记查重、答复流转与超期督办口径都收在这里。"""
from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Any

from app.store import store

MODULE = "complaint"
REQUIRED_FIELDS = ["投诉来源", "投诉类型", "受理时间", "影响时段"]
COMPLAINT_TYPES = ["噪音投诉", "光影投诉"]
STATUS_ORDER = ["待答复", "已答复"]
REPLY_LIMIT_DAYS = 5  # 受理后 5 天内必须答复，超期未答复自动进入督办清单
REPLY_ACTION = "提交答复"


def _parse_moment(raw: object) -> datetime | None:
    """把受理时间、答复期限解析成 datetime；兼容日期与日期时间两种写法。"""
    text = str(raw or "").strip()
    if not text:
        return None
    for fmt in ("%Y-%m-%d %H:%M", "%Y-%m-%dT%H:%M", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
        try:
            return datetime.strptime(text, fmt)
        except ValueError:
            continue
    return None


def _reply_deadline(moment: datetime) -> str:
    """督办时限：从受理时间起算 REPLY_LIMIT_DAYS 天。"""
    return (moment + timedelta(days=REPLY_LIMIT_DAYS)).strftime("%Y-%m-%d")


def _dup_key(values: dict[str, Any]) -> tuple[str, str, str]:
    """重复投诉判定口径：同一来源、同一类型、同一影响时段视为同一件事。"""
    return (
        str(values.get("投诉来源") or "").strip(),
        str(values.get("投诉类型") or "").strip(),
        str(values.get("影响时段") or "").strip(),
    )


class ComplaintService:
    def _refresh_flags(self) -> None:
        """按当天日期重算每条的待答复/超期标记，保证台账、督办与运营概览口径一致。"""
        today = date.today()
        for row in store.rows(MODULE):
            replied = row.get("status") == STATUS_ORDER[-1]
            deadline = _parse_moment(row.get("答复期限"))
            overdue = bool(deadline) and not replied and deadline.date() < today
            row["pending"] = not replied
            row["abnormal"] = overdue

    def list_entries(
        self,
        *,
        keyword: str | None = None,
        status: str | None = None,
        page: int = 1,
        size: int = 20,
    ) -> tuple[list[dict[str, Any]], int]:
        self._refresh_flags()
        rows = store.rows(MODULE)
        if keyword:
            rows = [
                row
                for row in rows
                if keyword in str(row.get("投诉编号", ""))
                or keyword in str(row.get("投诉来源", ""))
                or keyword in str(row.get("投诉类型", ""))
            ]
        if status:
            rows = [row for row in rows if row.get("status") == status]
        total = len(rows)
        start = max(page - 1, 0) * size
        return rows[start:start + size], total

    def supervision_entries(self) -> list[dict[str, Any]]:
        """督办清单：超过答复期限仍未答复的主记录，按超期天数倒序。"""
        self._refresh_flags()
        today = date.today()
        items: list[dict[str, Any]] = []
        for row in store.rows(MODULE):
            if row.get("status") == STATUS_ORDER[-1]:
                continue
            deadline = _parse_moment(row.get("答复期限"))
            if deadline is None or deadline.date() >= today:
                continue
            item = dict(row)
            item["超期天数"] = (today - deadline.date()).days
            items.append(item)
        items.sort(key=lambda item: int(item["超期天数"]), reverse=True)
        return items

    def summary(self) -> dict[str, int]:
        """台账概览：待答复、督办中与重复合并数量，答复成功后随列表一起刷新。"""
        self._refresh_flags()
        rows = store.rows(MODULE)
        return {
            "待答复": sum(1 for row in rows if row.get("pending")),
            "已答复": sum(1 for row in rows if not row.get("pending")),
            "督办中": sum(1 for row in rows if row.get("abnormal")),
            "重复合并": sum(int(row.get("重复次数", 0)) for row in rows),
        }

    def get_entry(self, entry_id: int) -> dict[str, Any] | None:
        self._refresh_flags()
        return store.find(MODULE, entry_id)

    def create_entry(self, values: dict[str, Any]) -> tuple[dict[str, Any] | None, list[str], str]:
        """登记投诉；缺必填字段时报明原因，命中重复时并入既有主记录。"""
        missing = [field for field in REQUIRED_FIELDS if not str(values.get(field) or "").strip()]
        if missing:
            return None, missing, ""
        moment = _parse_moment(values.get("受理时间"))
        if moment is None:
            return None, ["受理时间（格式应为 YYYY-MM-DD 或 YYYY-MM-DD HH:MM）"], ""
        complaint_type = str(values.get("投诉类型")).strip()
        if complaint_type not in COMPLAINT_TYPES:
            return None, [f"投诉类型（应为{'或'.join(COMPLAINT_TYPES)}）"], ""
        deadline_text = str(values.get("答复期限") or "").strip()
        if deadline_text and _parse_moment(deadline_text) is None:
            return None, ["答复期限（格式应为 YYYY-MM-DD）"], ""

        key = _dup_key(values)
        for master in store.rows(MODULE):
            if _dup_key(master) == key:
                return self._merge_duplicate(master, values, moment), [], "merged"

        rows = store.rows(MODULE)
        entry: dict[str, Any] = {"id": max((int(row.get("id", 0)) for row in rows), default=0) + 1}
        entry["投诉编号"] = f"COMP-{int(entry['id']):04d}"
        for field in REQUIRED_FIELDS:
            entry[field] = str(values.get(field)).strip()
        entry["受理时间"] = moment.strftime("%Y-%m-%d %H:%M")
        entry["答复期限"] = deadline_text or _reply_deadline(moment)
        entry["核查结论"] = ""
        entry["答复内容"] = ""
        entry["答复时间"] = ""
        entry["备注"] = str(values.get("备注") or "").strip()
        entry["status"] = STATUS_ORDER[0]
        entry["重复次数"] = 0
        entry["重复记录"] = []
        rows.append(entry)
        self._refresh_flags()
        return entry, [], "created"

    def _merge_duplicate(
        self,
        master: dict[str, Any],
        values: dict[str, Any],
        moment: datetime,
    ) -> dict[str, Any]:
        """重复投诉挂到同一条主记录下；未答复的主记录督办时限按最早那次受理时间重算。"""
        master.setdefault("重复记录", []).append({
            "受理时间": moment.strftime("%Y-%m-%d %H:%M"),
            "投诉来源": str(values.get("投诉来源")).strip(),
            "投诉类型": str(values.get("投诉类型")).strip(),
            "影响时段": str(values.get("影响时段")).strip(),
            "备注": str(values.get("备注") or "").strip(),
        })
        master["重复次数"] = len(master["重复记录"])
        if master.get("status") != STATUS_ORDER[-1]:
            earliest = _parse_moment(master.get("受理时间"))
            if earliest is None or moment < earliest:
                earliest = moment
            master["受理时间"] = earliest.strftime("%Y-%m-%d %H:%M")
            master["答复期限"] = _reply_deadline(earliest)
        self._refresh_flags()
        return master

    def run_action(
        self,
        entry_id: int,
        action: str,
        values: dict[str, Any],
    ) -> tuple[dict[str, Any] | None, str]:
        entry = store.find(MODULE, entry_id)
        if entry is None:
            return None, f"投诉记录 {entry_id} 不存在或已归档"
        if action != REPLY_ACTION:
            return None, f"动作「{action}」不属于投诉台账可执行范围"
        if entry.get("status") == STATUS_ORDER[-1]:
            return None, "该投诉已答复，无需重复提交"
        missing = [
            field
            for field in ("核查结论", "答复内容")
            if not str(values.get(field) or "").strip()
        ]
        if missing:
            return None, f"{'、'.join(missing)}不能为空，请补充后重新提交"
        entry["核查结论"] = str(values.get("核查结论")).strip()
        entry["答复内容"] = str(values.get("答复内容")).strip()
        entry["答复时间"] = datetime.now().strftime("%Y-%m-%d %H:%M")
        entry["status"] = STATUS_ORDER[-1]
        self._refresh_flags()
        return entry, "投诉已答复，督办清单与运营概览同步更新"
