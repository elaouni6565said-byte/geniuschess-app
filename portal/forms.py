import re
from django import forms
from academy.models import Student, Parent, Subject, Group, Room, Level, SessionSchedule, User
from core.i18n import FRENCH_MONTHS, ARABIC_MONTHS

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
        fields = ['name_fr', 'name_ar', 'subject', 'level', 'monthly_fee', 'color']
        widgets = {
            'name_fr': forms.TextInput(attrs={'class': 'search-input', 'placeholder': 'Ex: Groupe Robotique Mercredi'}),
            'name_ar': forms.TextInput(attrs={'class': 'search-input', 'placeholder': 'مثال: مجموعة الروبوتيك الأربعاء', 'dir': 'rtl'}),
            'subject': forms.Select(attrs={'class': 'search-input'}),
            'level': forms.Select(attrs={'class': 'search-input'}),
            'monthly_fee': forms.NumberInput(attrs={'class': 'search-input', 'step': '10'}),
            'color': forms.TextInput(attrs={'class': 'search-input', 'type': 'color'}),
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


class ExpenseForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        from finance.models import ExpenseCategory
        self.fields['category'].queryset = ExpenseCategory.objects.filter(is_active=True).order_by('name_fr')
        self.fields['category'].empty_label = "-- Sélectionner une catégorie --"
        self.fields['category'].label_from_instance = lambda obj: f"{obj.icon} {obj.name_fr} ({obj.name_ar})"

    class Meta:
        from finance.models import Expense
        model = Expense
        fields = [
            'title', 'category', 'amount', 'expense_date',
            'payment_method', 'beneficiary', 'invoice_number',
            'receipt_file', 'notes'
        ]
        widgets = {
            'title': forms.TextInput(attrs={'class': 'search-input', 'placeholder': 'Ex: Loyer salle de cours Septembre 2026'}),
            'category': forms.Select(attrs={'class': 'search-input'}),
            'amount': forms.NumberInput(attrs={'class': 'search-input', 'step': '0.50', 'placeholder': '0.00'}),
            'expense_date': forms.DateInput(attrs={'class': 'search-input', 'type': 'date'}),
            'payment_method': forms.Select(attrs={'class': 'search-input'}),
            'beneficiary': forms.TextInput(attrs={'class': 'search-input', 'placeholder': 'Ex: Propriétaire du local, Fournisseur, Formateur...'}),
            'invoice_number': forms.TextInput(attrs={'class': 'search-input', 'placeholder': 'Ex: FACT-2026-089 ou Référence'}),
            'receipt_file': forms.FileInput(attrs={'class': 'search-input', 'accept': 'image/*,application/pdf'}),
            'notes': forms.Textarea(attrs={'class': 'search-input', 'rows': 2, 'placeholder': 'Détails ou remarques complémentaires'}),
        }


class ExpenseCategoryForm(forms.ModelForm):
    class Meta:
        from finance.models import ExpenseCategory
        model = ExpenseCategory
        fields = ['name_fr', 'name_ar', 'icon', 'color', 'is_active']
        widgets = {
            'name_fr': forms.TextInput(attrs={'class': 'search-input', 'placeholder': 'Ex: Matériel Pédagogique'}),
            'name_ar': forms.TextInput(attrs={'class': 'search-input', 'placeholder': 'مثال: العتاد الرياضي', 'dir': 'rtl'}),
            'icon': forms.TextInput(attrs={'class': 'search-input', 'placeholder': 'Ex: 🏢, ♟️, 🏆, ⚡, 📑'}),
            'color': forms.TextInput(attrs={'class': 'search-input', 'type': 'color'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'status-checkbox'}),
        }


class FinancialClosingForm(forms.ModelForm):
    class Meta:
        from finance.models import FinancialClosing
        model = FinancialClosing
        fields = [
            'period_type', 'year', 'month', 'title', 'status', 'closing_date',
            'initial_cash_balance', 'initial_bank_balance',
            'physical_cash_counted', 'bank_statement_balance',
            'is_locked', 'treasurer_notes', 'president_notes'
        ]
        widgets = {
            'period_type': forms.Select(attrs={'class': 'search-input'}),
            'year': forms.NumberInput(attrs={'class': 'search-input'}),
            'month': forms.Select(choices=[('', '-- Annuel (Exercice entier) --')] + [(m, f"Mois {m:02d}") for m in range(1, 13)], attrs={'class': 'search-input'}),
            'title': forms.TextInput(attrs={'class': 'search-input', 'placeholder': 'Ex: Clôture Annuelle Exercice 2026'}),
            'status': forms.Select(attrs={'class': 'search-input'}),
            'closing_date': forms.DateInput(attrs={'class': 'search-input', 'type': 'date'}),
            'initial_cash_balance': forms.NumberInput(attrs={'class': 'search-input', 'step': '0.50'}),
            'initial_bank_balance': forms.NumberInput(attrs={'class': 'search-input', 'step': '0.50'}),
            'physical_cash_counted': forms.NumberInput(attrs={'class': 'search-input', 'step': '0.50', 'placeholder': 'Comptage physique réel du coffre'}),
            'bank_statement_balance': forms.NumberInput(attrs={'class': 'search-input', 'step': '0.50', 'placeholder': 'Solde relevé bancaire arrêté'}),
            'is_locked': forms.CheckboxInput(attrs={'class': 'status-checkbox'}),
            'treasurer_notes': forms.Textarea(attrs={'class': 'search-input', 'rows': 2, 'placeholder': 'Remarques ou explications d’écarts du Trésorier Général'}),
            'president_notes': forms.Textarea(attrs={'class': 'search-input', 'rows': 2, 'placeholder': 'Avis et validation du Président de l’Association'}),
        }


class TrainerForm(forms.ModelForm):
    class Meta:
        from academy.models import Trainer
        model = Trainer
        fields = [
            'first_name_fr', 'last_name_fr', 'first_name_ar', 'last_name_ar',
            'cin', 'phone', 'email', 'specialty', 'address',
            'compensation_type', 'default_rate', 'bank_name', 'bank_rib', 'active'
        ]
        widgets = {
            'first_name_fr': forms.TextInput(attrs={'class': 'search-input', 'placeholder': 'Prénom en français'}),
            'last_name_fr': forms.TextInput(attrs={'class': 'search-input', 'placeholder': 'Nom en français'}),
            'first_name_ar': forms.TextInput(attrs={'class': 'search-input', 'placeholder': 'الاسم الشخصي بالعربية', 'dir': 'rtl'}),
            'last_name_ar': forms.TextInput(attrs={'class': 'search-input', 'placeholder': 'الاسم العائلي بالعربية', 'dir': 'rtl'}),
            'cin': forms.TextInput(attrs={'class': 'search-input', 'placeholder': 'Ex: G123456'}),
            'phone': forms.TextInput(attrs={'class': 'search-input', 'placeholder': 'Ex: 06 12 34 56 78'}),
            'email': forms.EmailInput(attrs={'class': 'search-input', 'placeholder': 'formateur@email.com'}),
            'specialty': forms.TextInput(attrs={'class': 'search-input', 'placeholder': 'Ex: Échecs / الشطرنج, Robotique...'}),
            'address': forms.Textarea(attrs={'class': 'search-input', 'rows': 2, 'placeholder': 'Adresse de résidence'}),
            'compensation_type': forms.Select(attrs={'class': 'search-input'}),
            'default_rate': forms.NumberInput(attrs={'class': 'search-input', 'step': '0.50'}),
            'bank_name': forms.TextInput(attrs={'class': 'search-input', 'placeholder': 'Ex: Attijariwafa Bank, CIH...'}),
            'bank_rib': forms.TextInput(attrs={'class': 'search-input', 'placeholder': 'RIB 24 chiffres'}),
            'active': forms.CheckboxInput(attrs={'class': 'status-checkbox'}),
        }


class TrainerPayoutForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        from academy.models import Trainer
        self.fields['trainer'].queryset = Trainer.objects.filter(active=True).order_by('last_name_fr')
        self.fields['trainer'].empty_label = "-- Sélectionner un formateur --"
        self.fields['trainer'].label_from_instance = lambda obj: obj.get_bilingual_full_name()

    class Meta:
        from finance.models import TrainerPayout
        from core.i18n import FRENCH_MONTHS
        model = TrainerPayout
        fields = [
            'trainer', 'period_month', 'period_year', 'compensation_type',
            'sessions_count', 'rate_applied', 'base_amount',
            'bonus_amount', 'bonus_description',
            'deduction_amount', 'deduction_description',
            'status', 'payment_date', 'payment_method', 'reference', 'notes'
        ]
        widgets = {
            'trainer': forms.Select(attrs={'class': 'search-input'}),
            'period_month': forms.Select(choices=[(m, f"{m:02d} - {FRENCH_MONTHS.get(m, '').capitalize()}") for m in range(1, 13)], attrs={'class': 'search-input'}),
            'period_year': forms.NumberInput(attrs={'class': 'search-input'}),
            'compensation_type': forms.Select(attrs={'class': 'search-input'}),
            'sessions_count': forms.NumberInput(attrs={'class': 'search-input', 'min': 0}),
            'rate_applied': forms.NumberInput(attrs={'class': 'search-input', 'step': '0.50'}),
            'base_amount': forms.NumberInput(attrs={'class': 'search-input', 'step': '0.50'}),
            'bonus_amount': forms.NumberInput(attrs={'class': 'search-input', 'step': '0.50'}),
            'bonus_description': forms.TextInput(attrs={'class': 'search-input', 'placeholder': 'Ex: Arbitrage tournoi, prime déplacement'}),
            'deduction_amount': forms.NumberInput(attrs={'class': 'search-input', 'step': '0.50'}),
            'deduction_description': forms.TextInput(attrs={'class': 'search-input', 'placeholder': 'Ex: Acompte sur honoraires'}),
            'status': forms.Select(attrs={'class': 'search-input'}),
            'payment_date': forms.DateInput(attrs={'class': 'search-input', 'type': 'date'}),
            'payment_method': forms.Select(attrs={'class': 'search-input'}),
            'reference': forms.TextInput(attrs={'class': 'search-input', 'placeholder': 'Ex: N° Chèque ou Réf Virement'}),
            'notes': forms.Textarea(attrs={'class': 'search-input', 'rows': 2, 'placeholder': 'Notes ou observations'}),
        }





