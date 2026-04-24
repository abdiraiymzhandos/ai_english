from django import forms

from .models import ClassGroup, ClassStudent, Lesson


class MultipleFileInput(forms.ClearableFileInput):
    allow_multiple_selected = True


class MultipleImageField(forms.ImageField):
    widget = MultipleFileInput

    def clean(self, data, initial=None):
        if not data:
            return []
        if not isinstance(data, (list, tuple)):
            data = [data]

        cleaned = []
        errors = []
        for item in data:
            try:
                cleaned.append(super().clean(item, initial))
            except forms.ValidationError as exc:
                errors.extend(exc.error_list)

        if errors:
            raise forms.ValidationError(errors)

        return cleaned


class ClassGroupForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["school_name"].required = True

    class Meta:
        model = ClassGroup
        fields = ["school_name", "name"]
        labels = {
            "school_name": "Мектеп атауы",
            "name": "Сынып атауы",
        }
        widgets = {
            "name": forms.TextInput(attrs={
                "class": "form-input",
                "placeholder": "Мысалы: 7A",
            }),
            "school_name": forms.TextInput(attrs={
                "class": "form-input",
                "placeholder": "Мысалы: №12 мектеп",
            }),
        }


class ClassStudentForm(forms.ModelForm):
    class Meta:
        model = ClassStudent
        fields = ["full_name", "notes"]
        labels = {
            "full_name": "Оқушы аты-жөні",
            "notes": "Ескертпе",
        }
        widgets = {
            "full_name": forms.TextInput(attrs={
                "class": "form-input",
                "placeholder": "Оқушының аты",
            }),
            "notes": forms.TextInput(attrs={
                "class": "form-input",
                "placeholder": "Мысалы: ауысым, ерекше белгі",
            }),
        }


class StudentPhotoForm(forms.Form):
    image = MultipleImageField(
        required=False,
        label="Оқушының фотосы",
        widget=MultipleFileInput(attrs={
            "class": "form-input",
            "accept": "image/*",
            "multiple": True,
        }),
    )

    def clean_image(self):
        images = self.cleaned_data.get("image", [])
        if images and len(images) > 10:
            raise forms.ValidationError("Бір уақытта 10 фотоға дейін ғана жүктеуге болады.")
        return images


class ClassroomSessionSelectForm(forms.Form):
    group = forms.ModelChoiceField(queryset=ClassGroup.objects.none(), label="Сынып")
    lesson = forms.ModelChoiceField(queryset=Lesson.objects.all().order_by("id"), label="Сабақ")

    def __init__(self, teacher, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["group"].queryset = ClassGroup.objects.filter(teacher=teacher).order_by("school_name", "name")
        self.fields["group"].empty_label = "Сыныпты таңдаңыз"
        self.fields["group"].label_from_instance = (
            lambda obj: f"{obj.school_name} · {obj.name}" if obj.school_name else obj.name
        )
        self.fields["lesson"].empty_label = "Сабақты таңдаңыз"
        self.fields["lesson"].label_from_instance = lambda obj: f"{obj.id}. {obj.title}"
        self.fields["group"].widget.attrs.update({"class": "form-input"})
        self.fields["lesson"].widget.attrs.update({"class": "form-input"})
