# claims/management/commands/load_claims.py
from __future__ import annotations

import csv
import json
import re
from pathlib import Path
from decimal import Decimal, InvalidOperation
from datetime import datetime, date

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.db.models import Q

from claims.models import Claim, Note


class Command(BaseCommand):
    help = (
        "Load/Upsert claims from CSV/JSON.\n"
        "Supports cleaning Notes and need_review before upsert."
    )

    def add_arguments(self, parser):
        parser.add_argument("path", help="Path to CSV or JSON file.")
        parser.add_argument(
            "--format",
            choices=["auto", "csv", "json"],
            default="auto",
            help="Input format (default: auto detect by extension).",
        )
        parser.add_argument(
            "--delimiter",
            default="|",
            help="CSV delimiter (default: '|').",
        )
        parser.add_argument(
            "--reset-notes",
            choices=["all", "file", "keep"],
            default="all",  # clean all notes
            help="Reset notes before load (default: all). "
                 "Use 'file' to clear only notes of claims present in the file, "
                 "or 'keep' to keep existing notes."
        )
        parser.add_argument(
            "--reset-needreview",
            choices=["all", "file"],
            help="Set need_review=False before load: 'all' on all claims; 'file' only those in this file.",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Do not write to DB; show what would happen.",
        )

    # ---------- Helpers ----------
    @staticmethod
    def _detect_format(path: Path, forced: str) -> str:
        if forced != "auto":
            return forced
        ext = path.suffix.lower()
        if ext in {".csv", ".tsv"}:
            return "csv"
        if ext in {".json", ".ndjson"}:
            return "json"
        # fallback: try read first char
        try:
            with path.open("r", encoding="utf-8") as f:
                head = f.read(1)
            return "json" if head.strip().startswith("{") or head.strip().startswith("[") else "csv"
        except Exception:
            return "csv"

    @staticmethod
    def _to_decimal(val):
        if val is None:
            return None
        if isinstance(val, (int, float, Decimal)):
            return Decimal(str(val))
        s = str(val).strip().replace(",", "")
        if s == "":
            return None
        try:
            return Decimal(s)
        except (InvalidOperation, ValueError):
            return None

    @staticmethod
    def _parse_date(value) -> date | None:
        if not value:
            return None
        if isinstance(value, (date, datetime)):
            return value.date() if isinstance(value, datetime) else value
        s = str(value).strip()
        # ISO first
        try:
            return date.fromisoformat(s)
        except Exception:
            pass
        # common patterns
        for fmt in ("%Y/%m/%d", "%m/%d/%Y", "%d/%m/%Y"):
            try:
                return datetime.strptime(s, fmt).date()
            except Exception:
                continue
        # yyyymmdd
        m = re.fullmatch(r"(\d{4})(\d{2})(\d{2})", s)
        if m:
            try:
                return date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
            except Exception:
                return None
        return None

    @staticmethod
    def _norm_status(value: str | None) -> str | None:
        if not value:
            return None
        v = str(value).strip().lower().replace("-", " ").replace("_", " ")
        if "deny" in v:
            return "denied"
        if "paid" in v or "pay" in v:
            return "paid"
        if "review" in v:
            return "under_review"
        # fallback keep original lower word (avoid raising)
        return v.replace(" ", "_")

    @staticmethod
    def _coerce_claim_id(row: dict) -> str | None:
        for key in ("claim_id", "id", "Claim ID", "claimId"):
            if key in row and str(row[key]).strip():
                return str(row[key]).strip()
        return None

    @staticmethod
    def _get_str(row: dict, *keys, default: str = "") -> str:
        for k in keys:
            if k in row and row[k] is not None:
                s = str(row[k]).strip()
                if s != "":
                    return s
        return default

    def _load_rows_csv(self, path: Path, delimiter: str) -> list[dict]:
        rows: list[dict] = []
        with path.open("r", encoding="utf-8") as f:
            reader = csv.DictReader(f, delimiter=delimiter)
            for r in reader:
                rows.append({(k or "").strip(): v for k, v in (r or {}).items()})
        return rows

    def _load_rows_json(self, path: Path) -> list[dict]:
        txt = path.read_text(encoding="utf-8").strip()
        if not txt:
            return []
        # array
        if txt.startswith("["):
            data = json.loads(txt)
            if not isinstance(data, list):
                raise CommandError("JSON root must be list when using array form.")
            return [dict(x) for x in data]
        # ndjson
        rows = []
        with path.open("r", encoding="utf-8") as f:
            for line in f:
                s = line.strip()
                if not s:
                    continue
                rows.append(json.loads(s))
        return rows

    def _load_rows(self, path: Path, fmt: str, delimiter: str) -> list[dict]:
        if fmt == "csv":
            return self._load_rows_csv(path, delimiter)
        if fmt == "json":
            return self._load_rows_json(path)
        raise CommandError(f"Unsupported format: {fmt}")

    def _row_to_defaults(self, row: dict) -> dict:
        patient_name = self._get_str(row, "patient_name", "patient", "Patient")
        billed_amount = self._to_decimal(self._get_str(row, "billed_amount", "billed"))
        paid_amount = self._to_decimal(self._get_str(row, "paid_amount", "paid"))
        status = self._norm_status(self._get_str(row, "status"))
        insurer = self._get_str(row, "insurer", "insurer_name", "payer", default="")
        discharge_date = self._parse_date(self._get_str(row, "discharge_date", "date_of_service", "dos"))

        defaults = {}
        if patient_name:
            defaults["patient_name"] = patient_name
        if billed_amount is not None:
            defaults["billed_amount"] = billed_amount
        if paid_amount is not None:
            defaults["paid_amount"] = paid_amount
        if status:
            defaults["status"] = status
        # 只有提供时才覆盖；否则保留原值
        defaults["insurer"] = insurer
        defaults["discharge_date"] = discharge_date
        return defaults

    # ---------- Main ----------
    def handle(self, *args, **opts):
        path = Path(opts["path"]).expanduser().resolve()
        if not path.exists():
            raise CommandError(f"File not found: {path}")

        fmt = self._detect_format(path, opts["format"])
        delimiter = opts["delimiter"]
        dry_run = bool(opts["dry_run"])
        reset_notes = opts.get("reset_notes")
        reset_needreview = opts.get("reset_needreview")

        rows = self._load_rows(path, fmt, delimiter)
        if not rows:
            self.stdout.write(self.style.WARNING("No rows found."))
            return

        # Get Claim id
        file_ids: list[str] = []
        normalized_rows: list[tuple[str, dict]] = []
        for r in rows:
            cid = self._coerce_claim_id(r)
            if not cid:
                continue
            file_ids.append(cid)
            normalized_rows.append((cid, r))

        if not normalized_rows:
            self.stdout.write(self.style.WARNING("No valid claim_id in file."))
            return

        file_id_set = set(file_ids)


        will_create = 0
        will_update = 0
        skipped = 0

        # dry run
        if dry_run:
            existing = set(
                Claim.objects.filter(claim_id__in=file_id_set)
                .values_list("claim_id", flat=True)
            )
            for cid, _ in normalized_rows:
                if cid in existing:
                    will_update += 1
                else:
                    will_create += 1
            self.stdout.write(self.style.NOTICE(f"[Dry-run] Rows: {len(normalized_rows)}"))
            self.stdout.write(self.style.NOTICE(f"[Dry-run] Create: {will_create}, Update: {will_update}"))
            # 备注/need_review 清理也只提示
            if reset_notes:
                self.stdout.write(self.style.NOTICE(f"[Dry-run] Would reset notes: {reset_notes}"))
            if reset_needreview:
                self.stdout.write(self.style.NOTICE(f"[Dry-run] Would reset need_review: {reset_needreview}"))
            return


        with transaction.atomic():

            if reset_notes == "all":
                Note.objects.all().delete()
            elif reset_notes == "file":
                Note.objects.filter(claim__claim_id__in=file_id_set).delete()

            if reset_needreview == "all":
                Claim.objects.update(need_review=False)
            elif reset_needreview == "file":
                Claim.objects.filter(claim_id__in=file_id_set).update(need_review=False)

            # Upsert
            for cid, row in normalized_rows:
                defaults = self._row_to_defaults(row)
                if not defaults:
                    skipped += 1
                    continue
                obj, created = Claim.objects.update_or_create(
                    claim_id=cid,
                    defaults=defaults,
                )
                if created:
                    will_create += 1
                else:
                    will_update += 1

        self.stdout.write(self.style.SUCCESS(f"Import done. Rows: {len(normalized_rows)}"))
        self.stdout.write(self.style.SUCCESS(f"Created: {will_create}, Updated: {will_update}, Skipped: {skipped}"))
        if reset_notes:
            self.stdout.write(self.style.SUCCESS(f"Notes reset: {reset_notes}"))
        if reset_needreview:
            self.stdout.write(self.style.SUCCESS(f"need_review reset: {reset_needreview}"))
