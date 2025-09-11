import csv, json, io
from decimal import Decimal
from pathlib import Path
from datetime import datetime
from django.core.management.base import BaseCommand, CommandError
from claims.models import Claim

ALIASES = {
    "id": "claim_id",
    "claimid": "claim_id",
    "insurer_name": "insurer",
    "payer": "insurer",
    "company": "insurer",
}
STATUS_MAP = {
    "denied": "denied", "deny": "denied", "rejected": "denied", "reject": "denied",
    "paid": "paid", "approved": "paid",
    "under review": "under_review", "under_review": "under_review",
    "review": "under_review", "pending": "under_review", "in review": "under_review",
}

class Command(BaseCommand):
    help = "Load claims from CSV or JSON into the database"

    def add_arguments(self, parser):
        parser.add_argument("path", type=str, help="Path to claims.csv or claims.json")
        parser.add_argument("-d", "--delimiter", type=str, default=None,
                            help="CSV delimiter (e.g. ',' or '|'). If omitted, will try to sniff.")

    def handle(self, *args, **opts):
        path = Path(opts["path"]).expanduser()
        if not path.exists():
            raise CommandError(f"File not found: {path}")

        if path.suffix.lower() == ".csv":
            self.load_csv(path, delimiter=opts["delimiter"])
        elif path.suffix.lower() == ".json":
            self.load_json(path)
        else:
            raise CommandError("Unsupported file type; use .csv or .json")

        self.stdout.write(self.style.SUCCESS("Claims loaded successfully."))

    def parse_date(self, s):
        if not s: return None
        for fmt in ("%Y-%m-%d", "%m/%d/%Y", "%Y/%m/%d"):
            try:
                return datetime.strptime(s.strip(), fmt).date()
            except Exception:
                pass
        return None

    def normalize_row(self, raw: dict) -> dict:
        # lower-case keys, strip spaces
        row = { (k or "").strip().lower(): (v.strip() if isinstance(v, str) else v)
                for k, v in raw.items() }

        # apply aliases
        rec = {}
        for k, v in row.items():
            rec[ALIASES.get(k, k)] = v

        # numeric fields
        for key in ("billed_amount", "paid_amount"):
            val = rec.get(key)
            rec[key] = Decimal(str(val)) if (val not in (None, "",)) else Decimal("0")

        # status normalize
        s = (rec.get("status") or "").lower()
        rec["status"] = STATUS_MAP.get(s, (s or "under_review"))

        # insurer fallback
        rec["insurer"] = rec.get("insurer", "") or rec.get("insurer_name", "") or ""

        # CPT codes (support '|' or ',')
        codes = rec.get("cpt_codes") or ""
        if isinstance(codes, str) and codes:
            sep = "|" if "|" in codes else ","
            rec["cpt_codes"] = [c.strip() for c in codes.split(sep) if c.strip()]
        elif isinstance(codes, list):
            rec["cpt_codes"] = codes
        else:
            rec["cpt_codes"] = []

        # date
        rec["discharge_date"] = self.parse_date(rec.get("discharge_date"))

        return rec

    def upsert(self, rec):
        cid = str(rec.get("claim_id") or "").strip()
        if not cid:
            self.stdout.write(self.style.WARNING("Skipped a row without claim_id"))
            return
        Claim.objects.update_or_create(
            claim_id=cid,
            defaults={
                "patient_name": rec.get("patient_name", ""),
                "billed_amount": rec.get("billed_amount", 0),
                "paid_amount": rec.get("paid_amount", 0),
                "status": rec.get("status", "under_review"),
                "insurer": rec.get("insurer", ""),
                "discharge_date": rec.get("discharge_date"),
                "cpt_codes": rec.get("cpt_codes", []),
                "denial_reason": rec.get("denial_reason", ""),
                "flagged": bool(rec.get("flagged", False)),
            },
        )

    def load_csv(self, path: Path, delimiter=None):
        text = path.read_text(encoding="utf-8")
        if delimiter is None:
            try:
                # try to sniff from the header line
                sample = "\n".join(text.splitlines()[:2])
                dialect = csv.Sniffer().sniff(sample)
                delimiter = dialect.delimiter
            except Exception:
                delimiter = ","
        reader = csv.DictReader(io.StringIO(text), delimiter=delimiter)
        for row in reader:
            rec = self.normalize_row(row)
            self.upsert(rec)

    def load_json(self, path: Path):
        data = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(data, list):
            raise CommandError("JSON must be a list of claim objects")
        for row in data:
            rec = self.normalize_row(row)
            self.upsert(rec)
