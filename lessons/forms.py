# lessons/forms.py

from django import forms
from django.contrib.auth.models import User
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth import password_validation
from django.core.validators import RegexValidator
from django.contrib.auth.password_validation import MinimumLengthValidator

# +7XXXXXXXXXX форматын тексеретін валидатор
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
            'class': 'form-control',
            'placeholder': '+7XXXXXXXXXX',
            'value': '+7'
        })
    )

    class Meta:
        model = User
        fields = ['username', 'phone', 'password1', 'password2']
        labels = {
            'username': 'Логин',
            'password1': 'Құпиясөз',
            'password2': 'Құпиясөзді растау',
        }
        widgets = {
            'username': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Логин'
            }),
            'password1': forms.PasswordInput(attrs={
                'class': 'form-control',
                'placeholder': 'Құпиясөз',
                'style': 'background: rgba(255,255,255,0.1); color: #fff; border: none;'
            }),
            'password2': forms.PasswordInput(attrs={
                'class': 'form-control',
                'placeholder': 'Құпиясөзді растаңыз',
                'style': 'background: rgba(255,255,255,0.1); color: #fff; border: none;'
            }),
        }



    def clean_username(self):
        username = self.cleaned_data.get('username')
        if User.objects.filter(username=username).exists():
            raise forms.ValidationError("Бұл логин бұрыннан тіркелген.")
        return username

    def clean_password2(self):
        password1 = self.cleaned_data.get("password1")
        password2 = self.cleaned_data.get("password2")

        if password1 and password2:
            if password1 != password2:
                raise forms.ValidationError("Құпиясөздер сәйкес келмейді.")

            # Стандартты валидаторларды шақырып, шыққан қателіктерді өңдеу
            try:
                password_validation.validate_password(password2, self.instance)
            except forms.ValidationError as exc:
                # Ең алдымен минималды ұзындық мәнін аламыз
                min_len = None
                for v in password_validation.get_default_password_validators():
                    if isinstance(v, MinimumLengthValidator):
                        min_len = getattr(v, 'min_length', getattr(v, 'limit_value', None))
                        break

                new_errors = []
                for msg in exc.messages:
                    # Егер ағылшынша 'too short' хабар болса, қазақшаға ауыстырамыз
                    if 'too short' in msg.lower():
                        new_errors.append(f"Құпиясөз кем дегенде {min_len} таңбадан тұруы тиіс.")
                    else:
                        new_errors.append(msg)
                raise forms.ValidationError(new_errors)

        return password2
