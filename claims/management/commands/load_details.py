# claims/management/commands/load_details.py
import csv, re
from django.core.management.base import BaseCommand, CommandError
from claims.models import Claim

def parse_cpts(raw):
    if raw is None:
        return []
    if isinstance(raw, (list, tuple)):
        return [str(x).strip() for x in raw if str(x).strip()]
    s = str(raw).strip()
    if not s:
        return []
    parts = re.split(r"[,\s|;]+", s)
    return [p for p in parts if p]

class Command(BaseCommand):
    help = "Merge detail info (CPT, denial_reason, etc.) into existing claims by claim_id."

    def add_arguments(self, parser):
        parser.add_argument("path", help="CSV/TSV path")
        parser.add_argument("--delimiter", default=",", help="CSV delimiter, e.g. ',' or '|'")
        parser.add_argument("--dry-run", action="store_true",
                            help="Preview changes without writing DB")

    def handle(self, path, delimiter, dry_run, *args, **kwargs):
        try:
            f = open(path, newline="", encoding="utf-8")
        except OSError as e:
            raise CommandError(f"Cannot open file: {e}")

        reader = csv.DictReader(f, delimiter=delimiter)
        if "claim_id" not in reader.fieldnames:
            raise CommandError("Missing 'claim_id' column in file.")

        updated = 0
        missing = 0
        for row in reader:
            claim_id = (row.get("claim_id") or "").strip()
            if not claim_id:
                continue

            try:
                claim = Claim.objects.get(claim_id=claim_id)
            except Claim.DoesNotExist:
                missing += 1
                self.stdout.write(self.style.WARNING(f"Skip claim_id={claim_id}: not found"))
                continue

            info = dict(claim.detail_info or {})
            # 合并常见字段
            if "denial_reason" in row and row["denial_reason"]:
                info["denial_reason"] = row["denial_reason"].strip()

            # 解析 CPT
            cpt_raw = None
            for key in ("cpt_codes", "cpt", "cpts", "cpt code", "cpt codes", "codes"):
                if key in row and row[key]:
                    cpt_raw = row[key]
                    break
            cpts = parse_cpts(cpt_raw)
            if cpts:
                info["cpt_codes"] = cpts  # 统一用 cpt_codes 存

            if info != (claim.detail_info or {}):
                self.stdout.write(f"claim_id={claim_id} detail_info -> {info}")
                if not dry_run:
                    claim.detail_info = info
                    claim.save(update_fields=["detail_info"])
                updated += 1

        self.stdout.write(self.style.SUCCESS(
            f"Done. updated={updated}, missing={missing}, dry_run={dry_run}"
        ))
