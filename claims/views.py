# claims/views.py
import re
import json
from decimal import Decimal

from django.db.models import Q, F, Case, When, Value, DecimalField, ExpressionWrapper, Avg
from django.core.paginator import Paginator
from django.shortcuts import render, redirect, get_object_or_404
from django.views.decorators.http import require_http_methods, require_POST
from django.contrib.auth import logout

from .models import Claim
from .forms import NoteForm

PAGE_SIZE = 50


# ---------- Helpers to extract info from detail_info ----------
def _extract_cpt_list(info):
    """从 detail_info 里尽最大可能取出 CPT 列表，兼容多种 key 和字符串分隔"""
    if not isinstance(info, dict):
        return []
    low = { (k or "").strip().lower(): v for k, v in info.items() }

    candidates = [
        low.get("cpt_codes"),
        low.get("cpt"),
        low.get("cpts"),
        low.get("cpt code"),
        low.get("cpt codes"),
        low.get("codes"),
    ]
    raw = next((v for v in candidates if v), None)

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


def _extract_insurer(claim, info):
    """优先 claim.insurer；其次从 detail_info 里找"""
    if getattr(claim, "insurer", ""):
        return claim.insurer
    if not isinstance(info, dict):
        return ""
    low = { (k or "").strip().lower(): v for k, v in info.items() }
    return low.get("insurer") or low.get("payer") or low.get("insurance") or ""


def _extract_denial(claim, info):
    if getattr(claim, "denial_reason", ""):
        return claim.denial_reason
    if isinstance(info, dict):
        for key in ("denial_reason", "denial", "denial reason"):
            if key in {k.lower(): v for k, v in info.items()}:
                return info.get(key)
    return ""


# ---------- Welcome / guest / logout ----------
@require_http_methods(["GET"])
def welcome(request):
    return render(request, "claims/welcome.html")


@require_http_methods(["GET"])
def continue_as_guest(request):
    """访客进入用户页（就是列表页）"""
    return redirect("claims:index")


@require_http_methods(["GET"])
def logout_view(request):
    logout(request)
    return redirect("claims:welcome")


# ---------- Admin dashboard ----------
@require_http_methods(["GET"])
def admin_dashboard(request):
    """
    展示：所有 need_review=True 的 claims 列表，
    以及平均 underpayment（billed - paid 的正值平均）。
    """
    # underpayment = max(billed - paid, 0)
    underpay_expr = Case(
        When(billed_amount__gt=F("paid_amount"),
             then=ExpressionWrapper(F("billed_amount") - F("paid_amount"),
                                    output_field=DecimalField(max_digits=12, decimal_places=2))),
        default=Value(Decimal("0.00")),
        output_field=DecimalField(max_digits=12, decimal_places=2)
    )

    flagged = (Claim.objects
               .filter(need_review=True)
               .annotate(underpayment=underpay_expr)
               .order_by("-created_at"))

    avg_underpay_all = (Claim.objects
                        .annotate(underpayment=underpay_expr)
                        .aggregate(avg=Avg("underpayment"))["avg"]) or Decimal("0.00")

    ctx = {
        "flagged_claims": flagged,
        "avg_underpay_all": avg_underpay_all,
    }
    return render(request, "claims/admin_dashboard.html", ctx)


# ---------- User list page ----------
@require_http_methods(["GET"])
def index(request):
    q = (request.GET.get("q") or "").strip()
    status = (request.GET.get("status") or "").strip()          # "", "denied", "paid", "under_review"
    date_order = (request.GET.get("date") or "newest").strip()   # "newest" | "oldest"
    page = request.GET.get("page")

    qs = Claim.objects.all()

    # 多词 AND 搜索：Claim ID / Patient / Insurer
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

    # 表格需要字段
    qs = qs.only(
        "id", "claim_id", "patient_name",
        "billed_amount", "paid_amount",
        "status", "insurer",
        "discharge_date", "created_at",
        "need_review",
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
    if is_htmx:
        return render(request, "claims/_claim_table.html", ctx)
    return render(request, "claims/index.html", ctx)


# ---------- Claim detail panel (for HTMX) ----------
@require_http_methods(["GET"])
def claim_detail(request, pk):
    claim = get_object_or_404(Claim, pk=pk)
    info = claim.detail_info if isinstance(claim.detail_info, dict) else {}

    ctx = {
        "claim": claim,
        "note_form": NoteForm(),
        "insurer_display": _extract_insurer(claim, info),
        "cpt_list": _extract_cpt_list(info),
        "denial_text": _extract_denial(claim, info),
    }
    # 注意：模板名按你项目里现有的来；如果你的文件名是 _detail_panel.html，请对应替换
    return render(request, "claims/_detail_panel.html", ctx)


# ---------- Notes ----------
@require_http_methods(["POST"])
def add_note(request, pk):
    claim = get_object_or_404(Claim, pk=pk)
    form = NoteForm(request.POST)
    if form.is_valid():
        note = form.save(commit=False)
        note.claim = claim
        note.save()
        # 成功后只回 notes 列表片段（通常是 claims/_notes_list.html）
        return render(request, "claims/_notes_list.html", {"claim": claim})

    # 校验失败也回列表（或回表单），状态 400 便于前端处理
    resp = render(request, "claims/_notes_list.html", {"claim": claim})
    resp.status_code = 400
    return resp


# ---------- Flag (Review) ----------
@require_http_methods(["GET"])
def flag_confirm(request, pk):
    """返回确认弹窗片段（HTMX 载入到 #modal）"""
    claim = get_object_or_404(Claim, pk=pk)
    if claim.need_review:
        # 已标记就直接返回更新后的红旗按钮（也可以返回“已标记”的提示片段）
        return render(request, "claims/_flag_button.html", {"claim": claim})
    return render(request, "claims/_confirm_review.html", {"claim": claim})


@require_POST
def flag_set(request, pk):
    claim = get_object_or_404(Claim, pk=pk)
    if not claim.need_review:
        claim.need_review = True
        claim.save(update_fields=["need_review"])

    resp = render(request, "claims/_flag_button.html", {"claim": claim})
    # 让前端关闭弹窗（和你之前模板中的 JS 对应）
    resp["HX-Trigger"] = json.dumps({"close-modal": {"id": claim.pk}})
    return resp
