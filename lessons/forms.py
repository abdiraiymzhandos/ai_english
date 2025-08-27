from django import forms
from django.contrib.auth.models import User
from django.contrib.auth.forms import UserCreationForm
from django.core.validators import RegexValidator

phone_validator = RegexValidator(
    regex=r'^\+7\d{10}$',
    message="Телефон нөмірі +7XXXXXXXXXX форматында болуы тиіс"
)

class CustomRegisterForm(UserCreationForm):
    phone = forms.CharField(
        max_length=12,
        required=True,
        label='Телефон нөмірі',
        validators=[phone_validator],
        widget=forms.TextInput(attrs={
            'class': 'form-input',
            'placeholder': '+7XXXXXXXXXX'
        })
    )

    class Meta:
        model = User
        fields = ['username', 'phone', 'password1', 'password2']
        labels = {
            'username': 'Пайдаланушы аты',
            'password1': 'Құпиясөз',
            'password2': 'Құпиясөзді растау',
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        self.fields['username'].widget.attrs.update({
            'class': 'form-input',
            'placeholder': 'Пайдаланушы аты'
        })
        self.fields['password1'].widget.attrs.update({
            'class': 'form-input',
            'placeholder': 'Құпиясөз'
        })
        self.fields['password2'].widget.attrs.update({
            'class': 'form-input',
            'placeholder': 'Құпиясөзді қайталаңыз'
        })

    def clean_username(self):
        username = self.cleaned_data.get('username')
        if User.objects.filter(username=username).exists():
            raise forms.ValidationError("Бұл пайдаланушы аты бұрыннан алынған.")
        return username

    def clean_password2(self):
        password1 = self.cleaned_data.get("password1")
        password2 = self.cleaned_data.get("password2")

        if password1 and password2 and password1 != password2:
            raise forms.ValidationError("Құпиясөздер сәйкес келмейді.")
        
        return password2
