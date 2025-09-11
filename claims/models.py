from django.db import models
from django.utils import timezone

class Claim(models.Model):
    STATUS_CHOICES = [
        ("denied", "Denied"),
        ("paid", "Paid"),
        ("under_review", "Under Review"),
    ]

    claim_id = models.CharField(max_length=32, unique=True)
    patient_name = models.CharField(max_length=128)
    billed_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    paid_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="under_review")
    insurer = models.CharField(max_length=128, blank=True)
    discharge_date = models.DateField(null=True, blank=True)
    cpt_codes = models.JSONField(default=list, blank=True)
    denial_reason = models.TextField(blank=True)

    flagged = models.BooleanField(default=False)
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    detail_info = models.JSONField(default=dict, blank=True)

    need_review = models.BooleanField(default=False)
    class Meta:
        ordering = ["-updated_at"]

    def __str__(self):
        return f"Claim {self.claim_id} – {self.patient_name}"


class Note(models.Model):
    claim = models.ForeignKey(Claim, on_delete=models.CASCADE, related_name="notes")
    body = models.TextField()
    author_name = models.CharField(max_length=64)
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"Note for {self.claim.claim_id}"

    @property
    def ago_one_unit(self):
        """只显示最大时间单位：2 days ago / 3 hours ago / 15 minutes ago / 10 seconds ago"""
        dt = self.created_at
        if timezone.is_aware(dt):
            dt = timezone.localtime(dt)
        now = timezone.localtime()
        delta = now - dt
        total = int(delta.total_seconds())
        future = total < 0
        total = abs(total)

        def unit(n, s):  # 简单英文复数
            return f"{n} {s if n == 1 else s + 's'}"

        if total >= 365 * 24 * 3600:
            text = unit(total // (365 * 24 * 3600), "year")
        elif total >= 30 * 24 * 3600:
            text = unit(total // (30 * 24 * 3600), "month")
        elif total >= 7 * 24 * 3600:
            text = unit(total // (7 * 24 * 3600), "week")
        elif total >= 24 * 3600:
            text = unit(total // (24 * 3600), "day")
        elif total >= 3600:
            text = unit(total // 3600, "hour")
        elif total >= 60:
            text = unit(total // 60, "minute")
        else:
            text = unit(total, "second")

        return (f"in {text}" if future else f"{text} ago")