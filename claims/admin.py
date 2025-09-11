from django.contrib import admin
from .models import Claim, Note

@admin.register(Claim)
class ClaimAdmin(admin.ModelAdmin):
    list_display = ("claim_id", "patient_name", "billed_amount", "paid_amount",
                    "status", "insurer", "flagged")
    list_filter = ("status", "insurer", "flagged")
    search_fields = ("claim_id", "patient_name", "insurer")

@admin.register(Note)
class NoteAdmin(admin.ModelAdmin):
    list_display = ("claim", "author_name", "created_at")
    search_fields = ("claim__claim_id", "body")
