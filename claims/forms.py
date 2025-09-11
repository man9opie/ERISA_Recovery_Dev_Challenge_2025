from django import forms
from .models import Note

class NoteForm(forms.ModelForm):
    class Meta:
        model = Note
        fields = ["body", "author_name"]
        widgets = {
            "body": forms.Textarea(attrs={"rows": 3, "placeholder": "Add a note...", "required": True}),
            "author_name": forms.TextInput(attrs={"placeholder": "Your name", "required": True}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # 双保险：即使有人去掉 HTML 的 required，也会被服务端拦住
        self.fields["body"].required = True
        self.fields["author_name"].required = True
