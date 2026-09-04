with open('portal/views.py', 'r', encoding='utf-8') as f:
    code = f.read()

start_marker = '@admin_required\ndef planning_view(request):'
end_marker = '@admin_required\ndef payments_list_view(request):'

start_idx = code.find(start_marker)
end_idx = code.find(end_marker)

new_planning_code = '''@admin_required
def planning_view(request):
    import calendar
    from datetime import date, datetime, time, timedelta
    from core.i18n import FRENCH_DAYS, ARABIC_DAYS, FRENCH_MONTHS, ARABIC_MONTHS

    lang = getattr(request, 'LANGUAGE_CODE', DEFAULT_LANGUAGE)
    current_view = request.GET.get('view', 'monthly')
    if current_view not in ('daily', 'monthly', 'annual'):
        current_view = 'monthly'

    room_id = request.GET.get('room')
    schedules = SessionSchedule.objects.select_related('group', 'group__subject', 'room').order_by('day_of_week', 'start_time')
    if room_id and room_id.isdigit():
        schedules = schedules.filter(room_id=int(room_id))

    rooms = Room.objects.all()
    days_dict = ARABIC_DAYS if lang == 'ar' else FRENCH_DAYS
    months_dict = ARABIC_MONTHS if lang == 'ar' else FRENCH_MONTHS

    # Today anchor
    today = date(2026, 9, 3)

    context = {
        'current_view': current_view,
        'rooms': rooms,
        'selected_room': int(room_id) if room_id and room_id.isdigit() else None,
        'today': today,
    }

    if current_view == 'daily':
        # --- DAILY VIEW ---
        date_param = request.GET.get('date')
        if date_param:
            try:
                sel_date = datetime.strptime(date_param, '%Y-%m-%d').date()
            except ValueError:
                sel_date = today
        else:
            sel_date = today

        day_of_week = sel_date.weekday()
        day_sessions = list(schedules.filter(day_of_week=day_of_week))
        
        hourly_timeline = []
        for hour in range(8, 20):
            matching = [s for s in day_sessions if s.start_time.hour == hour]
            hourly_timeline.append({
                'hour': f"{hour:02d}:00",
                'sessions': matching
            })

        context.update({
            'sel_date': sel_date,
            'day_name': days_dict.get(day_of_week, ''),
            'prev_date': (sel_date - timedelta(days=1)).strftime('%Y-%m-%d'),
            'next_date': (sel_date + timedelta(days=1)).strftime('%Y-%m-%d'),
            'day_sessions': day_sessions,
            'hourly_timeline': hourly_timeline,
            'is_today': sel_date == today,
        })

    elif current_view == 'monthly':
        # --- MONTHLY VIEW ---
        try:
            year = int(request.GET.get('year', today.year))
            month = int(request.GET.get('month', today.month))
        except (ValueError, TypeError):
            year, month = today.year, today.month

        if month < 1:
            month = 1
        elif month > 12:
            month = 12

        cal = calendar.Calendar(firstweekday=0)
        month_weeks = []
        for week in cal.monthdatescalendar(year, month):
            week_days = []
            for d in week:
                d_dow = d.weekday()
                d_sessions = [s for s in schedules if s.day_of_week == d_dow]
                week_days.append({
                    'date': d,
                    'date_str': d.strftime('%Y-%m-%d'),
                    'day_num': d.day,
                    'is_current_month': d.month == month,
                    'is_today': d == today,
                    'day_of_week': d_dow,
                    'sessions': d_sessions,
                })
            month_weeks.append(week_days)

        if month == 1:
            prev_m, prev_y = 12, year - 1
        else:
            prev_m, prev_y = month - 1, year

        if month == 12:
            next_m, next_y = 1, year + 1
        else:
            next_m, next_y = month + 1, year

        weekdays_header = [days_dict.get(i, '') for i in range(7)]

        context.update({
            'year': year,
            'month': month,
            'month_name': months_dict.get(month, ''),
            'month_weeks': month_weeks,
            'weekdays_header': weekdays_header,
            'prev_month': prev_m,
            'prev_year': prev_y,
            'next_month': next_m,
            'next_year': next_y,
        })

    elif current_view == 'annual':
        # --- ANNUAL VIEW ---
        try:
            year = int(request.GET.get('year', today.year))
        except (ValueError, TypeError):
            year = today.year

        annual_months = []
        cal = calendar.Calendar(firstweekday=0)
        total_year_sessions = 0
        subjects = Subject.objects.all()

        for m in range(1, 13):
            m_cal_days = [d for d in cal.itermonthdates(year, m) if d.month == m]
            m_total_sessions = 0
            m_subject_counts = {subj.id: {'subj': subj, 'count': 0} for subj in subjects}
            
            for d in m_cal_days:
                d_dow = d.weekday()
                for s in schedules:
                    if s.day_of_week == d_dow:
                        m_total_sessions += 1
                        if s.group.subject_id in m_subject_counts:
                            m_subject_counts[s.group.subject_id]['count'] += 1

            total_year_sessions += m_total_sessions
            annual_months.append({
                'month_num': m,
                'month_name': months_dict.get(m, ''),
                'year': year,
                'total_sessions': m_total_sessions,
                'subject_counts': [v for v in m_subject_counts.values() if v['count'] > 0],
                'is_current_month': (m == today.month and year == today.year),
            })

        context.update({
            'year': year,
            'prev_year': year - 1,
            'next_year': year + 1,
            'annual_months': annual_months,
            'total_year_sessions': total_year_sessions,
        })

    return render(request, 'portal/planning.html', context)


'''

if start_idx != -1 and end_idx != -1:
    updated_code = code[:start_idx] + new_planning_code + code[end_idx:]
    with open('portal/views.py', 'w', encoding='utf-8') as f:
        f.write(updated_code)
    print('Successfully updated planning_view in portal/views.py!')
else:
    print('Markers not found:', start_idx, end_idx)
