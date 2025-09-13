# claims/views.py
from __future__ import annotations

import json
import re
from typing import List

from django.core.paginator import Paginator
from django.db.models import F, Q
from django.shortcuts import get_object_or_404, render
from django.views.decorators.http import require_http_methods, require_POST

from .forms import NoteForm
from .models import Claim

PAGE_SIZE = 50  # 每页行数，可按需调整


# ---------------------------
# helpers：把 detail_info 做容错解析
# ---------------------------
def _extract_cpt_list(info) -> List[str]:
    """
    从 detail_info 里尽最大可能取出 CPT 列表：
    - 兼容 key: cpt_codes / cpt / cpts / cpt code / cpt codes / codes
    - 兼容字符串或列表，字符串支持逗号、空格、分号、竖线等分隔
    """
    if not isinstance(info, dict):
        return []
    low = {(k or "").strip().lower(): v for k, v in info.items()}

    candidates = [
        low.get("cpt_codes"),
        low.get("cpt"),
        low.get("cpts"),
        low.get("cpt code"),
        low.get("cpt codes"),
        low.get("codes"),
    ]
    raw = next((v for v in candidates if v), None)

    # 兜底：任意包含 "cpt" 的 key
    if raw is None:
        for k, v in low.items():
            if "cpt" in k:
                raw = v
                break

    if raw is None:
        return []

    if isinstance(raw, (list, tuple)):
        return [str(x).strip() for x in raw if str(x).strip()]

    if isinstance(raw, str):
        parts = re.split(r"[,\s|;]+", raw.strip())
        return [p for p in parts if p]

    return []


def _extract_insurer(claim: Claim, info) -> str:
    """优先用 claim.insurer；其次从 detail_info 里找别名。"""
    if getattr(claim, "insurer", ""):
        return claim.insurer
    if not isinstance(info, dict):
        return ""
    low = {(k or "").strip().lower(): v for k, v in info.items()}
    return low.get("insurer") or low.get("payer") or low.get("insurance") or ""


def _extract_denial(info, claim: Claim) -> str:
    """
    统一抽取“否认原因”文本：
    - 兼容 detail_info.denial_reason / detail_info.denial / detail_info.denialreason
    - 兜底为模型字段 claim.denial_reason（若存在）
    - 返回字符串，拿不到时返回空串
    """
    if isinstance(info, dict):
        low = {(k or "").strip().lower(): v for k, v in info.items()}
        val = (
            low.get("denial_reason")
            or low.get("denial")
            or low.get("denialreason")
        )
        if isinstance(val, (list, tuple)):
            val = ", ".join(map(str, val))
        if val:
            return str(val)
    return getattr(claim, "denial_reason", "") or ""


# ---------------------------
# 视图
# ---------------------------
@require_http_methods(["GET"])
def index(request):
    """列表页：搜索 + 过滤 + 排序 + 分页（支持 HTMX 部分刷新）"""
    q = (request.GET.get("q") or "").strip()
    status = (request.GET.get("status") or "").strip()          # "", "denied", "paid", "under_review"
    date_order = (request.GET.get("date") or "newest").strip()  # "newest" | "oldest"
    page = request.GET.get("page")

    qs = Claim.objects.all()

    # 多词 AND 搜索：Claim ID / Patient / Insurer
    if q:
        for token in q.split():
            qs = qs.filter(
                Q(claim_id__icontains=token)
                | Q(patient_name__icontains=token)
                | Q(insurer__icontains=token)
            )

    # 状态过滤
    if status in {"denied", "paid", "under_review"}:
        qs = qs.filter(status=status)

    # 日期排序（兼容空值）
    if date_order == "oldest":
        qs = qs.order_by(F("discharge_date").asc(nulls_first=True), "created_at")
    else:
        qs = qs.order_by(F("discharge_date").desc(nulls_last=True), "-created_at")

    # 只取表格需要字段
    qs = qs.only(
        "id",
        "claim_id",
        "patient_name",
        "billed_amount",
        "paid_amount",
        "status",
        "insurer",
        "discharge_date",
        "created_at",
    )

    paginator = Paginator(qs, PAGE_SIZE)
    page_obj = paginator.get_page(page)

    is_htmx = bool(request.headers.get("HX-Request"))
    ctx = {
        "claims": page_obj.object_list,
        "page_obj": page_obj,
        "paginator": paginator,
        "is_htmx": is_htmx,
    }

    # HTMX 请求只返回表格片段
    if is_htmx:
        return render(request, "claims/_claim_table.html", ctx)

    # 首次加载整页
    return render(request, "claims/index.html", ctx)


@require_http_methods(["GET"])
def claim_detail(request, pk: int):
    """点击 View 加载详情面板（含 Insurer/CPT/Denial 容错解析）"""
    claim = get_object_or_404(Claim, pk=pk)
    info = claim.detail_info if isinstance(claim.detail_info, dict) else {}

    ctx = {
        "claim": claim,
        "note_form": NoteForm(),
        "insurer_display": _extract_insurer(claim, info),
        "cpt_list": _extract_cpt_list(info),
        "denial_text": _extract_denial(info, claim),
    }
    return render(request, "claims/_detail_panel.html", ctx)


@require_http_methods(["POST"])
def add_note(request, pk: int):
    """
    添加备注，返回 “仅备注列表” 片段（_notes_list.html），
    以便在 _notes_card.html 中 hx-target 到该列表进行局部刷新。
    """
    claim = get_object_or_404(Claim, pk=pk)
    form = NoteForm(request.POST)
    if form.is_valid():
        note = form.save(commit=False)
        note.claim = claim
        note.save()
        return render(request, "claims/_notes_list.html", {"claim": claim})

    # 校验失败也返回列表（附 400），前端可自行处理
    resp = render(request, "claims/_notes_list.html", {"claim": claim})
    resp.status_code = 400
    return resp


def flag_confirm(request, pk):
    """点击 'Flag for Review' 时先来这里：
       - 如果已标记，弹只读提示
       - 否则，弹确认框
    """
    claim = get_object_or_404(Claim, pk=pk)
    if claim.need_review:
        return render(request, "claims/_already_review.html", {"claim": claim})
    return render(request, "claims/_confirm_review.html", {"claim": claim})


@require_POST
def flag_set(request, pk: int):
    """确认后设置 need_review=True，并触发关闭弹窗事件"""
    claim = get_object_or_404(Claim, pk=pk)
    if not claim.need_review:
        claim.need_review = True
        claim.save(update_fields=["need_review"])

    # 返回更新后的红旗按钮片段，并触发关闭模态框
    resp = render(request, "claims/_flag_button.html", {"claim": claim})
    resp["HX-Trigger"] = json.dumps({"close-modal": {"id": claim.pk}})
    return resp
