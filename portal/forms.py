import re
from django import forms
from academy.models import Student, Parent, Subject, Group, Room, Level, SessionSchedule, User

class StudentForm(forms.ModelForm):
    registration_number = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={'class': 'search-input', 'placeholder': 'GCA-2026-00X (auto si vide)'})
    )
    groups = forms.ModelMultipleChoiceField(
        queryset=Group.objects.select_related('subject', 'level').all(),
        widget=forms.CheckboxSelectMultiple(attrs={'class': 'group-checkbox'}),
        required=False
    )

    class Meta:
        model = Student
        fields = [
            'registration_number',
            'first_name_fr', 'last_name_fr',
            'first_name_ar', 'last_name_ar',
            'birth_date',
            'parent',
            'groups',
            'active'
        ]
        widgets = {
            'first_name_fr': forms.TextInput(attrs={'class': 'search-input', 'placeholder': 'Ex: Mohamed'}),
            'last_name_fr': forms.TextInput(attrs={'class': 'search-input', 'placeholder': 'Ex: Alaoui'}),
            'first_name_ar': forms.TextInput(attrs={'class': 'search-input', 'placeholder': 'مثال: محمد', 'dir': 'rtl'}),
            'last_name_ar': forms.TextInput(attrs={'class': 'search-input', 'placeholder': 'مثال: العلوي', 'dir': 'rtl'}),
            'birth_date': forms.DateInput(attrs={'class': 'search-input', 'type': 'date'}),
            'parent': forms.Select(attrs={'class': 'search-input'}),
            'active': forms.CheckboxInput(attrs={'class': 'status-checkbox'}),
        }

    def clean_first_name_fr(self):
        val = self.cleaned_data.get('first_name_fr', '')
        val = re.sub(r'[\u064B-\u0652\u0670]', '', val)
        return re.sub(r'\s+', ' ', val).strip()

    def clean_last_name_fr(self):
        val = self.cleaned_data.get('last_name_fr', '')
        val = re.sub(r'[\u064B-\u0652\u0670]', '', val)
        return re.sub(r'\s+', ' ', val).strip()

    def clean_first_name_ar(self):
        val = self.cleaned_data.get('first_name_ar', '')
        return re.sub(r'\s+', ' ', val).strip()

    def clean_last_name_ar(self):
        val = self.cleaned_data.get('last_name_ar', '')
        return re.sub(r'\s+', ' ', val).strip()

    def clean_registration_number(self):
        reg = self.cleaned_data.get('registration_number')
        if not reg:
            # Auto-generate next registration number
            count = Student.objects.count() + 1
            reg = f"GCA-2026-{count:03d}"
            while Student.objects.filter(registration_number=reg).exists():
                count += 1
                reg = f"GCA-2026-{count:03d}"
        return reg.strip()


class ParentForm(forms.ModelForm):
    class Meta:
        model = Parent
        fields = ['full_name_fr', 'full_name_ar', 'cin', 'phone', 'email', 'preferred_language']
        widgets = {
            'full_name_fr': forms.TextInput(attrs={'class': 'search-input', 'placeholder': 'Ex: Karim Alaoui'}),
            'full_name_ar': forms.TextInput(attrs={'class': 'search-input', 'placeholder': 'مثال: كريم العلوي', 'dir': 'rtl'}),
            'cin': forms.TextInput(attrs={'class': 'search-input', 'placeholder': 'Ex: CD123456'}),
            'phone': forms.TextInput(attrs={'class': 'search-input', 'placeholder': 'Ex: 0661112233'}),
            'email': forms.EmailInput(attrs={'class': 'search-input', 'placeholder': 'Ex: parent@gmail.com'}),
            'preferred_language': forms.Select(attrs={'class': 'search-input'}),
        }

    def clean_full_name_fr(self):
        val = self.cleaned_data.get('full_name_fr', '')
        val = re.sub(r'[\u064B-\u0652\u0670]', '', val)
        return re.sub(r'\s+', ' ', val).strip()

    def clean_full_name_ar(self):
        val = self.cleaned_data.get('full_name_ar', '')
        return re.sub(r'\s+', ' ', val).strip()

    def save(self, commit=True):
        parent = super().save(commit=False)
        if not parent.user:
            # Create user account for Parent portal access
            clean_name = re.sub(r'[^a-zA-Z0-9]+', '_', parent.full_name_fr.strip().lower()).strip('_')
            username = f"parent_{clean_name}"[:25]
            if User.objects.filter(username=username).exists():
                username = f"{username}_{User.objects.count()}"[:30]
            
            user = User.objects.create_user(
                username=username,
                email=parent.email or f"{username}@gca.ma",
                password="Parent@2026",
                role="parent",
                preferred_language=parent.preferred_language or "fr"
            )
            parent.user = user

        if commit:
            parent.save()
        return parent


class SubjectForm(forms.ModelForm):
    class Meta:
        model = Subject
        fields = ['name_fr', 'name_ar', 'color', 'icon', 'description_fr', 'description_ar']
        widgets = {
            'name_fr': forms.TextInput(attrs={'class': 'search-input', 'placeholder': 'Ex: Robotique'}),
            'name_ar': forms.TextInput(attrs={'class': 'search-input', 'placeholder': 'مثال: الروبوتيك', 'dir': 'rtl'}),
            'color': forms.TextInput(attrs={'class': 'search-input', 'type': 'color'}),
            'icon': forms.TextInput(attrs={'class': 'search-input', 'placeholder': 'Ex: robot, chess, brain'}),
            'description_fr': forms.Textarea(attrs={'class': 'search-input', 'rows': 2}),
            'description_ar': forms.Textarea(attrs={'class': 'search-input', 'rows': 2, 'dir': 'rtl'}),
        }


class GroupForm(forms.ModelForm):
    class Meta:
        model = Group
        fields = ['name_fr', 'name_ar', 'subject', 'level', 'monthly_fee']
        widgets = {
            'name_fr': forms.TextInput(attrs={'class': 'search-input', 'placeholder': 'Ex: Groupe Robotique Mercredi'}),
            'name_ar': forms.TextInput(attrs={'class': 'search-input', 'placeholder': 'مثال: مجموعة الروبوتيك الأربعاء', 'dir': 'rtl'}),
            'subject': forms.Select(attrs={'class': 'search-input'}),
            'level': forms.Select(attrs={'class': 'search-input'}),
            'monthly_fee': forms.NumberInput(attrs={'class': 'search-input', 'step': '10'}),
        }


class SessionScheduleForm(forms.ModelForm):
    class Meta:
        model = SessionSchedule
        fields = ['group', 'room', 'day_of_week', 'start_time', 'end_time', 'trainer_name_fr', 'trainer_name_ar']
        widgets = {
            'group': forms.Select(attrs={'class': 'search-input'}),
            'room': forms.Select(attrs={'class': 'search-input'}),
            'day_of_week': forms.Select(attrs={'class': 'search-input'}),
            'start_time': forms.TimeInput(attrs={'class': 'search-input', 'type': 'time'}),
            'end_time': forms.TimeInput(attrs={'class': 'search-input', 'type': 'time'}),
            'trainer_name_fr': forms.TextInput(attrs={'class': 'search-input', 'placeholder': 'Ex: Hassan Alaoui'}),
            'trainer_name_ar': forms.TextInput(attrs={'class': 'search-input', 'placeholder': 'مثال: حسن العلوي', 'dir': 'rtl'}),
        }


class PaymentForm(forms.ModelForm):
    security_code = forms.CharField(
        required=True,
        widget=forms.PasswordInput(attrs={
            'class': 'search-input',
            'placeholder': 'Code spécial (ex: 6565)',
            'style': 'letter-spacing: 0.25em; font-weight: bold; background: #FEF9C3; border: 2px solid #EAB308;'
        }),
        label="Code Spécial d'Autorisation"
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        from finance.models import Invoice
        self.fields['invoice'].required = False
        self.fields['invoice'].empty_label = "-- Attribution automatique à la facture impayée --"
        self.fields['invoice'].queryset = Invoice.objects.filter(status__in=['unpaid', 'partial']).select_related('student', 'group')
        self.fields['invoice'].label_from_instance = lambda obj: f"{obj.student.get_full_name('fr')} — {obj.get_period_label('fr')} (Reste: {obj.get_balance()} DH)"

    class Meta:
        from finance.models import Payment
        model = Payment
        fields = ['student', 'invoice', 'amount', 'payment_date', 'payment_method', 'reference', 'notes']
        widgets = {
            'student': forms.Select(attrs={'class': 'search-input'}),
            'invoice': forms.Select(attrs={'class': 'search-input'}),
            'amount': forms.NumberInput(attrs={'class': 'search-input', 'step': '10'}),
            'payment_date': forms.DateInput(attrs={'class': 'search-input', 'type': 'date'}),
            'payment_method': forms.Select(attrs={'class': 'search-input'}),
            'reference': forms.TextInput(attrs={'class': 'search-input', 'placeholder': 'N° Virement, Chèque ou Réf'}),
            'notes': forms.Textarea(attrs={'class': 'search-input', 'rows': 2, 'placeholder': 'Remarques éventuelles'}),
        }


