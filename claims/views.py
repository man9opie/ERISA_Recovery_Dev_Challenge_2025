# claims/views.py
from django.db.models import Q, F
from django.shortcuts import render, get_object_or_404
from django.views.decorators.http import require_http_methods
from django.core.paginator import Paginator

from django.shortcuts import render, get_object_or_404
from django.views.decorators.http import require_POST   # ← 加这一行
from .models import Claim


from .models import Claim
from .forms import NoteForm  # 要有包含 author_name / body 的表单

import json

PAGE_SIZE = 50  # 每页行数，可自行调整

@require_http_methods(["GET"])
def index(request):
    """列表页：搜索 + 过滤 + 排序 + 分页"""
    q = (request.GET.get("q") or "").strip()
    status = (request.GET.get("status") or "").strip()               # "", "denied", "paid", "under_review"
    date_order = (request.GET.get("date") or "newest").strip()       # "newest" | "oldest"
    page = request.GET.get("page")                                   # 交给 get_page 自处理

    qs = Claim.objects.all()

    # 支持多词 AND 搜索：Claim ID / Patient / Insurer
    if q:
        for token in q.split():
            qs = qs.filter(
                Q(claim_id__icontains=token) |
                Q(patient_name__icontains=token) |
                Q(insurer__icontains=token)
            )

    # 状态过滤
    if status in {"denied", "paid", "under_review"}:
        qs = qs.filter(status=status)

    # 日期排序（兼容空值）
    if date_order == "oldest":
        qs = qs.order_by(F("discharge_date").asc(nulls_first=True), "created_at")
    else:
        qs = qs.order_by(F("discharge_date").desc(nulls_last=True), "-created_at")

    # 只取表格需要的字段以减轻渲染压力
    qs = qs.only(
        "id", "claim_id", "patient_name",
        "billed_amount", "paid_amount",
        "status", "insurer",
        "discharge_date", "created_at"
    )

    paginator = Paginator(qs, PAGE_SIZE)
    page_obj = paginator.get_page(page)

    is_htmx = bool(request.headers.get("HX-Request"))
    ctx = {
        "claims": page_obj.object_list,
        "page_obj": page_obj,
        "paginator": paginator,
        "is_htmx": is_htmx,  # 让模板知道是不是 HTMX 请求（用于输出 OOB 分页）
    }

    # HTMX 请求只回表格片段（片段里会顺带输出 OOB 分页同步外部导航）
    if is_htmx:
        return render(request, "claims/_claim_table.html", ctx)

    # 首次加载/整页
    return render(request, "claims/index.html", ctx)


@require_http_methods(["GET"])
def claim_detail(request, pk):
    """点击 View 加载详情面板"""
    claim = get_object_or_404(Claim, pk=pk)
    return render(request, "claims/_detail_panel.html",
                  {"claim": claim, "note_form": NoteForm()})


@require_http_methods(["POST"])
def add_note(request, pk):
    """添加备注，返回刷新后的备注卡片片段"""
    claim = get_object_or_404(Claim, pk=pk)
    form = NoteForm(request.POST)
    if form.is_valid():
        note = form.save(commit=False)
        note.claim = claim
        note.save()
        return render(request, "claims/_notes_card.html",
                      {"claim": claim, "note_form": NoteForm()})
    resp = render(request, "claims/_notes_card.html",
                  {"claim": claim, "note_form": form})
    resp.status_code = 400
    return resp


def flag_confirm(request, pk):
    """返回一个确认弹窗的片段（HTMX 载入到 #modal）"""
    claim = get_object_or_404(Claim, pk=pk)
    # 已经标记过就什么都不弹
    if claim.need_review:
        return render(request, "claims/_flag_button.html", {"claim": claim})
    return render(request, "claims/_confirm_review.html", {"claim": claim})

@require_POST
def flag_set(request, pk):
    claim = get_object_or_404(Claim, pk=pk)
    if not claim.need_review:
        claim.need_review = True
        claim.save(update_fields=["need_review"])

    # 返回更新后的红旗片段（或占位）
    resp = render(request, "claims/_flag_button.html", {"claim": claim})
    # 关键：让前端收到一个自定义事件“close-modal”
    resp["HX-Trigger"] = json.dumps({"close-modal": {"id": claim.pk}})
    return resp