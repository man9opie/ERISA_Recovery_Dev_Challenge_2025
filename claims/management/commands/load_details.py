# claims/management/commands/load_details.py
import csv, json, io
from pathlib import Path
from datetime import datetime
from decimal import Decimal
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from claims.models import Claim

ALIASES = {
    "id": "claim_id", "claimid": "claim_id",
    "patient": "patient_name", "patient_name": "patient_name",
    "billed": "billed_amount", "billed_amount": "billed_amount",
    "paid": "paid_amount", "paid_amount": "paid_amount",
    "status": "status",
    "insurer": "insurer", "insurer_name": "insurer",
    "discharge_date": "discharge_date", "dos": "discharge_date",
    "cpt": "cpt_codes", "cpt_codes": "cpt_codes",
    "denial_reason": "denial_reason",
    "flagged": "flagged",
}
STATUS_MAP = {
    "denied":"denied","deny":"denied","rejected":"denied",
    "paid":"paid","approved":"paid",
    "under review":"under_review","under_review":"under_review","pending":"under_review","review":"under_review",
}
CLAIM_FIELDS = {
    "patient_name","billed_amount","paid_amount","status","insurer",
    "discharge_date","cpt_codes","denial_reason","flagged"
}

def sniff_delim(text, fallback=","):
    try:
        sample = "\n".join(text.splitlines()[:2])
        return csv.Sniffer().sniff(sample).delimiter
    except Exception:
        return fallback

def parse_date(s):
    if s in (None, "", "-"): return None
    for fmt in ("%Y-%m-%d", "%m/%d/%Y", "%Y/%m/%d"):
        try: return datetime.strptime(str(s).strip(), fmt).date()
        except Exception: pass
    return None

def parse_decimal(v):
    if v in (None, "", "-"): return None
    try: return Decimal(str(v).replace(",", ""))
    except Exception: return None

def parse_list(v):
    if not v: return []
    if isinstance(v, list): return v
    s = str(v)
    sep = "|" if "|" in s else ","
    return [x.strip() for x in s.split(sep) if x.strip()]

def norm_status(s):
    if not s: return None
    s = str(s).strip().lower()
    return STATUS_MAP.get(s, s)

class Command(BaseCommand):
    help = "Merge claim details (CSV/JSON) into existing Claim by claim_id. Safe: skips blank values."

    def add_arguments(self, parser):
        parser.add_argument("path", type=str, help="details csv or json")
        parser.add_argument("-d","--delimiter", type=str, default=None, help="CSV delimiter, e.g. '|'")
        parser.add_argument("--dry-run", action="store_true", help="Show what would change, don't write DB", default=False)
        parser.add_argument("--overwrite", action="store_true",
                            help="Allow blank values in file to overwrite existing (NOT recommended)")
        parser.add_argument("--create-missing", action="store_true",
                            help="Create minimal Claim when claim_id not found (only claim_id set)")

    @transaction.atomic
    def handle(self, *args, **opts):
        path = Path(opts["path"]).expanduser()
        if not path.exists(): raise CommandError(f"File not found: {path}")

        # 读取明细文件
        if path.suffix.lower() == ".csv":
            text = path.read_text(encoding="utf-8")
            delim = opts["delimiter"] or sniff_delim(text, ",")
            rows = list(csv.DictReader(io.StringIO(text), delimiter=delim))
        elif path.suffix.lower() == ".json":
            rows = json.loads(path.read_text(encoding="utf-8"))
            if not isinstance(rows, list): raise CommandError("JSON must be a list")
        else:
            raise CommandError("Use .csv or .json")

        updated, created_claims, skipped = 0, 0, 0

        for raw in rows:
            # 标准化键名+别名
            row = {(k or "").strip().lower(): (v.strip() if isinstance(v, str) else v) for k, v in raw.items()}
            rec = {ALIASES.get(k, k): v for k, v in row.items()}
            cid = str(rec.get("claim_id") or "").strip()
            if not cid:
                skipped += 1
                continue

            claim = Claim.objects.filter(claim_id=cid).first()
            if not claim:
                if opts["create_missing"]:
                    claim = Claim.objects.create(claim_id=cid, patient_name="")
                    created_claims += 1
                else:
                    skipped += 1
                    continue

            patch = {}

            if "patient_name" in rec and (opts["overwrite"] or rec["patient_name"] not in ("", None)):
                patch["patient_name"] = rec["patient_name"]

            if "billed_amount" in rec:
                val = parse_decimal(rec["billed_amount"])
                if opts["overwrite"] or val is not None:
                    patch["billed_amount"] = val if val is not None else claim.billed_amount

            if "paid_amount" in rec:
                val = parse_decimal(rec["paid_amount"])
                if opts["overwrite"] or val is not None:
                    patch["paid_amount"] = val if val is not None else claim.paid_amount

            if "status" in rec:
                val = norm_status(rec["status"])
                if opts["overwrite"] or val:
                    patch["status"] = val or claim.status

            if "insurer" in rec and (opts["overwrite"] or rec["insurer"] not in ("", None)):
                patch["insurer"] = rec["insurer"]

            if "discharge_date" in rec:
                val = parse_date(rec["discharge_date"])
                if opts["overwrite"] or val is not None:
                    patch["discharge_date"] = val if val is not None else claim.discharge_date

            if "cpt_codes" in rec:
                codes = parse_list(rec["cpt_codes"])
                if opts["overwrite"] or codes:
                    patch["cpt_codes"] = codes if codes else claim.cpt_codes

            if "denial_reason" in rec and (opts["overwrite"] or rec["denial_reason"] not in ("", None)):
                patch["denial_reason"] = rec["denial_reason"]

            if "flagged" in rec:
                val = rec["flagged"]
                if isinstance(val, str): val = val.strip().lower() in ("1","true","yes","y","t")
                if isinstance(val, bool) or opts["overwrite"]:
                    patch["flagged"] = bool(val) if val is not None else claim.flagged

            # 未知列并入 detail_info（不丢数据）
            known = set(ALIASES.keys()) | CLAIM_FIELDS | {"claim_id"}
            extra = {k: row[k] for k in row.keys() if k not in known}
            if extra:
                merged = {**(claim.detail_info or {}), **extra}
                patch["detail_info"] = merged

            if opts["dry_run"]:
                if patch: updated += 1
                continue

            if patch:
                for k, v in patch.items():
                    setattr(claim, k, v)
                claim.save(update_fields=list(patch.keys()))
                updated += 1

        msg = f"Updated: {updated}, created: {created_claims}, skipped: {skipped}"
        if opts["dry_run"]:
            self.stdout.write(self.style.WARNING("[DRY RUN] " + msg))
        else:
            self.stdout.write(self.style.SUCCESS("Import done. " + msg))
