import re
from django import forms
from academy.models import Student, Parent, Subject, Group, Room, Level, SessionSchedule, User, GroupMessage

from decimal import Decimal
from finance.models import PaymentExemption, Invoice

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
    exempted_months = forms.MultipleChoiceField(
        choices=[
            ('1', '01 - Janvier / يناير'),
            ('2', '02 - Février / فبراير'),
            ('3', '03 - Mars / مارس'),
            ('4', '04 - Avril / أبريل'),
            ('5', '05 - Mai / ماي'),
            ('6', '06 - Juin / يونيو'),
            ('7', '07 - Juillet / يوليوز'),
            ('8', '08 - Août / غشت'),
            ('9', '09 - Septembre / شتنبر'),
            ('10', '10 - Octobre / أكتوبر'),
            ('11', '11 - Novembre / نونبر'),
            ('12', '12 - Décembre / دجنبر'),
        ],
        required=False,
        widget=forms.CheckboxSelectMultiple(attrs={'class': 'month-checkbox'}),
        label="Mois exonérés de paiement"
    )
    exemption_reason = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={'class': 'search-input', 'placeholder': 'Ex: Bourse d\'excellence, convention 100%, cas social...'}),
        label="Motif de l'exonération"
    )
    force_duplicate_override = forms.BooleanField(
        required=False,
        widget=forms.CheckboxInput(attrs={'class': 'status-checkbox', 'id': 'id_force_duplicate_override'}),
        label="Confirmer l'inscription malgré la détection d'un doublon / homonyme"
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
            'active',
            'has_convention',
            'convention_name',
            'discount_type',
            'discount_value'
        ]
        widgets = {
            'first_name_fr': forms.TextInput(attrs={'class': 'search-input', 'placeholder': 'Ex: Mohamed'}),
            'last_name_fr': forms.TextInput(attrs={'class': 'search-input', 'placeholder': 'Ex: Alaoui'}),
            'first_name_ar': forms.TextInput(attrs={'class': 'search-input', 'placeholder': 'مثال: محمد', 'dir': 'rtl'}),
            'last_name_ar': forms.TextInput(attrs={'class': 'search-input', 'placeholder': 'مثال: العلوي', 'dir': 'rtl'}),
            'birth_date': forms.DateInput(attrs={'class': 'search-input', 'type': 'date'}),
            'parent': forms.Select(attrs={'class': 'search-input'}),
            'active': forms.CheckboxInput(attrs={'class': 'status-checkbox'}),
            'has_convention': forms.CheckboxInput(attrs={'class': 'status-checkbox', 'id': 'id_has_convention'}),
            'convention_name': forms.TextInput(attrs={'class': 'search-input', 'placeholder': 'Ex: Convention OCP, Club Éducation, Fratrie...'}),
            'discount_type': forms.Select(attrs={'class': 'search-input'}),
            'discount_value': forms.NumberInput(attrs={'class': 'search-input', 'step': '5', 'placeholder': 'Ex: 200 (Tarif) ou 50 (DH) ou 20 (%)'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['discount_type'].required = False
        self.fields['discount_value'].required = False
        if not self.initial.get('discount_type'):
            self.initial['discount_type'] = 'custom_fee'
        if self.initial.get('discount_value') is None:
            self.initial['discount_value'] = Decimal('0.00')

        if self.instance and self.instance.pk:
            exemptions = self.instance.payment_exemptions.filter(period_year=2026)
            self.fields['exempted_months'].initial = [str(e.period_month) for e in exemptions]
            first_ex = exemptions.first()
            if first_ex:
                self.fields['exemption_reason'].initial = first_ex.reason

    def clean(self):
        cleaned_data = super().clean()
        has_conv = cleaned_data.get('has_convention')
        if not has_conv:
            if not cleaned_data.get('discount_type'):
                cleaned_data['discount_type'] = 'custom_fee'
            if cleaned_data.get('discount_value') is None:
                cleaned_data['discount_value'] = Decimal('0.00')
        else:
            if cleaned_data.get('discount_value') is None:
                cleaned_data['discount_value'] = Decimal('0.00')

        # Contrôle anti-double inscription
        fn_fr = (cleaned_data.get('first_name_fr') or '').strip()
        ln_fr = (cleaned_data.get('last_name_fr') or '').strip()
        fn_ar = (cleaned_data.get('first_name_ar') or '').strip()
        ln_ar = (cleaned_data.get('last_name_ar') or '').strip()
        birth_date = cleaned_data.get('birth_date')
        parent = cleaned_data.get('parent')
        force_override = cleaned_data.get('force_duplicate_override', False)

        current_pk = self.instance.pk if self.instance else None

        if (fn_fr and ln_fr) or (fn_ar and ln_ar):
            qs = Student.objects.all().select_related('parent')
            if current_pk:
                qs = qs.exclude(pk=current_pk)

            exact_match = None

            # 1. Même prénom/nom FR et même parent
            if parent and fn_fr and ln_fr:
                exact_match = qs.filter(
                    parent=parent,
                    first_name_fr__iexact=fn_fr,
                    last_name_fr__iexact=ln_fr
                ).first()

            # 2. Même prénom/nom FR et même date de naissance
            if not exact_match and birth_date and fn_fr and ln_fr:
                exact_match = qs.filter(
                    birth_date=birth_date,
                    first_name_fr__iexact=fn_fr,
                    last_name_fr__iexact=ln_fr
                ).first()

            # 3. Même prénom/nom AR et même parent
            if not exact_match and parent and fn_ar and ln_ar:
                exact_match = qs.filter(
                    parent=parent,
                    first_name_ar__iexact=fn_ar,
                    last_name_ar__iexact=ln_ar
                ).first()

            # 4. Même prénom/nom AR et même date de naissance
            if not exact_match and birth_date and fn_ar and ln_ar:
                exact_match = qs.filter(
                    birth_date=birth_date,
                    first_name_ar__iexact=fn_ar,
                    last_name_ar__iexact=ln_ar
                ).first()

            if exact_match and not force_override:
                parent_info = f" (Parent: {exact_match.parent.get_name()})" if exact_match.parent else ""
                bdate_info = f" - Né(e) le {exact_match.birth_date.strftime('%d/%m/%Y')}" if exact_match.birth_date else ""
                raise forms.ValidationError(
                    f"⚠️ Risque de double inscription détecté : Cet élève est déjà enregistré sous le matricule "
                    f"[{exact_match.registration_number}] {exact_match.get_bilingual_full_name()}{parent_info}{bdate_info}. "
                    "Si vous souhaitez modifier son inscription ou ses activités, ouvrez directement sa fiche existante. "
                    "Si c'est un homonyme distinct, cochez la case 'Confirmer l'inscription malgré la similitude'."
                )

        return cleaned_data

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

    def save(self, commit=True):
        student = super().save(commit=commit)
        if commit:
            selected_months = [int(m) for m in self.cleaned_data.get('exempted_months', [])]
            reason = self.cleaned_data.get('exemption_reason', '').strip() or "Exonération accordée"
            
            # Supprimer les mois qui ont été décochés
            PaymentExemption.objects.filter(student=student, period_year=2026).exclude(period_month__in=selected_months).delete()
            
            # Ajouter/Mettre à jour les mois cochés
            for m in selected_months:
                PaymentExemption.objects.update_or_create(
                    student=student,
                    period_month=m,
                    period_year=2026,
                    defaults={'reason': reason}
                )

            # Mettre à jour les factures existantes de l'élève pour l'année 2026
            base_fee, discount, final_fee = student.calculate_monthly_fee()
            for inv in Invoice.objects.filter(student=student, period_year=2026):
                if inv.period_month in selected_months:
                    inv.is_exempt = True
                    inv.status = 'exempt'
                    inv.amount_due = Decimal('0.00')
                    inv.original_amount = base_fee
                    inv.discount_amount = base_fee
                    inv.exemption_reason = reason
                    inv.save()
                elif inv.is_exempt and inv.period_month not in selected_months:
                    inv.is_exempt = False
                    inv.original_amount = base_fee
                    inv.discount_amount = discount
                    inv.amount_due = final_fee
                    inv.exemption_reason = ''
                    inv.update_totals()
                elif not inv.is_exempt and inv.status == 'unpaid' and inv.amount_paid == Decimal('0.00'):
                    # Recalculer le tarif selon la convention
                    inv.original_amount = base_fee
                    inv.discount_amount = discount
                    inv.amount_due = final_fee
                    inv.save()

        return student



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

    def clean_phone(self):
        val = self.cleaned_data.get('phone', '').strip()
        cleaned_digits = re.sub(r'[^0-9]', '', val)
        if len(cleaned_digits) < 9:
            raise forms.ValidationError("Le numéro de téléphone doit comporter au moins 9 à 10 chiffres (ex: 0661112233).")
        return val

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
        fields = ['group', 'room', 'day_of_week', 'start_time', 'end_time', 'notification_time', 'trainer_name_fr', 'trainer_name_ar']
        widgets = {
            'group': forms.Select(attrs={'class': 'search-input'}),
            'room': forms.Select(attrs={'class': 'search-input'}),
            'day_of_week': forms.Select(attrs={'class': 'search-input'}),
            'start_time': forms.TimeInput(attrs={'class': 'search-input', 'type': 'time'}),
            'end_time': forms.TimeInput(attrs={'class': 'search-input', 'type': 'time'}),
            'notification_time': forms.TimeInput(attrs={'class': 'search-input', 'type': 'time'}),
            'trainer_name_fr': forms.TextInput(attrs={'class': 'search-input', 'placeholder': 'Ex: Hassan Alaoui'}),
            'trainer_name_ar': forms.TextInput(attrs={'class': 'search-input', 'placeholder': 'مثال: حسن العلوي', 'dir': 'rtl'}),
        }


class PaymentForm(forms.ModelForm):
    security_code = forms.CharField(
        required=False,
        widget=forms.PasswordInput(attrs={
            'class': 'search-input',
            'placeholder': "Code d'autorisation",
            'style': 'letter-spacing: 0.25em; font-weight: bold; background: #FEF9C3; border: 2px solid #EAB308;'
        }),
        label="Code d'Autorisation"
    )

    # Nouveaux champs direct de Convention et Exonération lors du paiement
    is_exemption = forms.BooleanField(
        required=False,
        label="Exonérer l'élève pour ce mois (0 DH / معفى من الأداء)",
        widget=forms.CheckboxInput(attrs={'class': 'status-checkbox', 'id': 'id_is_exemption'})
    )
    exemption_reason = forms.CharField(
        required=False,
        label="Motif de l'exonération",
        widget=forms.TextInput(attrs={'class': 'search-input', 'id': 'id_exemption_reason', 'placeholder': 'Ex: Bourse d\'excellence, convention 100%, mois offert...'})
    )
    apply_discount = forms.BooleanField(
        required=False,
        label="Appliquer une réduction / Convention sur ce paiement",
        widget=forms.CheckboxInput(attrs={'class': 'status-checkbox', 'id': 'id_apply_discount'})
    )
    discount_amount = forms.DecimalField(
        required=False,
        initial=Decimal('0.00'),
        min_value=0,
        label="Montant de la réduction accordée (DH)",
        widget=forms.NumberInput(attrs={'class': 'search-input', 'id': 'id_discount_amount', 'step': '10', 'placeholder': 'Ex: 50'})
    )
    convention_name = forms.CharField(
        required=False,
        label="Nom de la convention / Organisme",
        widget=forms.TextInput(attrs={'class': 'search-input', 'id': 'id_convention_name', 'placeholder': 'Ex: Convention OCP, Club Enseignants, Fratrie...'})
    )

    # Option explicite du mois / période réglé(e) (pour régularisation des paiements tardifs ou par avance)
    MONTH_CHOICES = [
        (1, '01 - Janvier / يناير'),
        (2, '02 - Février / فبراير'),
        (3, '03 - Mars / مارس'),
        (4, '04 - Avril / أبريل'),
        (5, '05 - Mai / ماي'),
        (6, '06 - Juin / يونيو'),
        (7, '07 - Juillet / يوليوز'),
        (8, '08 - Août / غشت'),
        (9, '09 - Septembre / شتنبر'),
        (10, '10 - Octobre / أكتوبر'),
        (11, '11 - Novembre / نونبر'),
        (12, '12 - Décembre / دجنبر'),
    ]
    period_month = forms.TypedChoiceField(
        choices=MONTH_CHOICES,
        coerce=int,
        required=False,
        widget=forms.Select(attrs={'class': 'search-input', 'id': 'id_period_month'}),
        label="Mois concerné par ce versement / الشهر المؤدى عنه"
    )
    period_year = forms.IntegerField(
        initial=2026,
        required=False,
        widget=forms.NumberInput(attrs={'class': 'search-input', 'id': 'id_period_year', 'min': '2025', 'max': '2030'}),
        label="Année / السنة"
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        from datetime import date
        from finance.models import Invoice

        today = date.today()
        if not self.initial.get('payment_date'):
            if self.instance and self.instance.payment_date:
                self.initial['payment_date'] = self.instance.payment_date
            else:
                self.initial['payment_date'] = today

        # Si la date n'est pas saisie, la date du jour (date de saisie) est affectée par défaut
        self.fields['payment_date'].required = False

        if not self.initial.get('period_month'):
            if self.instance and self.instance.period_month:
                self.initial['period_month'] = self.instance.period_month
            else:
                self.initial['period_month'] = today.month
        if not self.initial.get('period_year'):
            if self.instance and self.instance.period_year:
                self.initial['period_year'] = self.instance.period_year
            else:
                self.initial['period_year'] = today.year

        self.fields['invoice'].required = False
        self.fields['invoice'].empty_label = "-- Attribution automatique à la facture impayée du mois --"
        self.fields['invoice'].queryset = Invoice.objects.filter(status__in=['unpaid', 'partial']).select_related('student', 'group')
        self.fields['invoice'].label_from_instance = lambda obj: f"{obj.student.get_full_name('fr')} — {obj.get_period_label('fr')} (Reste: {obj.get_balance()} DH)"

        def format_student_option(st):
            lbl = f"{st.registration_number} - {st.get_full_name('fr')} ({st.get_full_name('ar')})"
            if st.has_convention:
                lbl += f" 🏷️ [Convention: {st.convention_name or 'Partenaire'}]"
            ex_count = st.payment_exemptions.count()
            if ex_count > 0:
                lbl += f" 🌟 [{ex_count} mois exonéré(s)]"
            return lbl

        self.fields['student'].label_from_instance = format_student_option

    def clean_payment_date(self):
        val = self.cleaned_data.get('payment_date')
        if not val:
            from django.utils import timezone
            return timezone.localdate()
        return val

    def clean(self):
        cleaned_data = super().clean()
        if not cleaned_data.get('payment_date'):
            from django.utils import timezone
            cleaned_data['payment_date'] = timezone.localdate()

        is_ex = cleaned_data.get('is_exemption')
        amt = cleaned_data.get('amount')
        if is_ex:
            cleaned_data['amount'] = Decimal('0.00')
        elif amt is not None and amt <= Decimal('0.00'):
            self.add_error('amount', "Le montant du paiement doit être supérieur à 0 DH (ou cochez 'Exonérer ce mois' pour 0 DH).")
        return cleaned_data

    class Meta:
        from finance.models import Payment
        model = Payment
        fields = ['student', 'invoice', 'period_month', 'period_year', 'amount', 'payment_date', 'payment_method', 'reference', 'notes']
        widgets = {
            'student': forms.Select(attrs={'class': 'search-input', 'id': 'id_student_select'}),
            'invoice': forms.Select(attrs={'class': 'search-input', 'id': 'id_invoice'}),
            'period_month': forms.Select(attrs={'class': 'search-input', 'id': 'id_period_month'}),
            'period_year': forms.NumberInput(attrs={'class': 'search-input', 'id': 'id_period_year'}),
            'amount': forms.NumberInput(attrs={'class': 'search-input', 'step': '10', 'id': 'id_payment_amount'}),
            'payment_date': forms.DateInput(attrs={'class': 'search-input', 'type': 'date', 'id': 'id_payment_date'}),
            'payment_method': forms.Select(attrs={'class': 'search-input'}),
            'reference': forms.TextInput(attrs={'class': 'search-input', 'placeholder': 'N° Virement, Chèque ou Réf'}),
            'notes': forms.Textarea(attrs={'class': 'search-input', 'rows': 2, 'placeholder': 'Remarques éventuelles'}),
        }


class ExemptionForm(forms.Form):
    student = forms.ModelChoiceField(
        queryset=Student.objects.filter(active=True).order_by('last_name_fr'),
        widget=forms.Select(attrs={'class': 'search-input'}),
        label="Élève concerné / التلميذ المعني"
    )
    period_month = forms.ChoiceField(
        choices=[
            (1, '01 - Janvier / يناير'),
            (2, '02 - Février / فبراير'),
            (3, '03 - Mars / مارس'),
            (4, '04 - Avril / أبريل'),
            (5, '05 - Mai / ماي'),
            (6, '06 - Juin / يونيو'),
            (7, '07 - Juillet / يوليوز'),
            (8, '08 - Août / غشت'),
            (9, '09 - Septembre / شتنبر'),
            (10, '10 - Octobre / أكتوبر'),
            (11, '11 - Novembre / نونبر'),
            (12, '12 - Décembre / دجنبر'),
        ],
        widget=forms.Select(attrs={'class': 'search-input'}),
        label="Mois à exonérer / الشهر المعفى"
    )
    period_year = forms.IntegerField(
        initial=2026,
        widget=forms.NumberInput(attrs={'class': 'search-input'}),
        label="Année / السنة"
    )
    reason = forms.CharField(
        required=False,
        initial="Bourse / Prise en charge convention",
        widget=forms.TextInput(attrs={'class': 'search-input', 'placeholder': 'Ex: Bourse d\'excellence, convention 100%, cas social...'}),
        label="Motif de l'exonération / سبب الإعفاء"
    )


class GroupMessageForm(forms.ModelForm):
    notify_parents = forms.BooleanField(
        required=False,
        initial=True,
        label="Créer aussi une notification directe dans l'espace de chaque parent",
        widget=forms.CheckboxInput(attrs={'class': 'status-checkbox'})
    )

    class Meta:
        model = GroupMessage
        fields = ['title', 'message_type', 'content']
        widgets = {
            'title': forms.TextInput(attrs={
                'class': 'search-input',
                'placeholder': 'Titre ou objet (ex: Préparation tournoi, Consigne séance, Rappel...)'
            }),
            'message_type': forms.Select(attrs={'class': 'search-input'}),
            'content': forms.Textarea(attrs={
                'class': 'search-input',
                'rows': 4,
                'placeholder': 'Rédigez le message ou l\'annonce à destination des parents de ce groupe...'
            }),
        }



