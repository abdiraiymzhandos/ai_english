"""Shared dashboard/workbook dataset. All intervals are half-open UTC instants."""
from collections import Counter, defaultdict
from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from django.contrib.auth import get_user_model
from django.db.models import Count, Max, OuterRef, Q, Subquery
from django.utils import timezone

from lessons.models import QuizAttempt
from . import crm
from .models import Event, Purchase, Visit
from .taxonomy import LABELS

ZONE = ZoneInfo('Asia/Almaty')
PRESETS = {'seven':'Соңғы 7 толық күн', 'today':'Бүгін', 'yesterday':'Кеше', 'fourteen':'Соңғы 14 толық күн',
           'thirty':'Соңғы 30 толық күн', 'month':'Осы ай', 'previous':'Өткен ай', 'custom':'Өзге аралық'}
STAGES = ['Алғашқы сабақты ашты','Бірінші сабақты аяқтады','Екінші сабақты аяқтады','Үшінші сабақты аяқтады',
          'Ұсынысты көрді','Сатып алуды таңдады','WhatsApp-қа бағытталды','Сатып алуы расталды']
METRICS = [
    ('registrations','Тіркелгендер'), ('active','Белсенді қолданушылар'), ('visits','Сапарлар'),
    ('opened','Сабақ ашқандар'), ('first','Бірінші сабақты аяқтады'), ('second','Екінші сабақты аяқтады'),
    ('third','Үшінші сабақты аяқтады'), ('free','Үш тегін сабақты аяқтады'), ('view','Ұсынысты көрді'),
    ('click','Сатып алуды таңдады'), ('wa','WhatsApp-қа бағытталды'), ('paid','Расталған сатып алушылар'),
    ('revenue','Расталған түсім, ₸'), ('reg_rate','Тіркелу → сатып алу'), ('free_rate','Үш сабақ → ұсыныс'),
    ('wa_rate','Ұсыныс → WhatsApp'), ('paid_rate','Ұсыныс → сатып алу')]
RATES = {'reg_rate','free_rate','wa_rate','paid_rate'}
EVENT_FIELDS = ('id','user_id','visit_id','at','kind','origin','page','path','lesson','track',
                'visit__source','visit__campaign','visit__visitor_id','visit__platform','visit__medium','visit__content','context')
LIMIT_USERS, LIMIT_EVENTS = 10000, 50000


class ReportError(ValueError):
    pass


def options(params, now):
    today = now.astimezone(ZONE).date()
    preset = params.get('preset','seven')
    mode = params.get('mode','activity')
    if preset not in PRESETS or mode not in ('activity','cohort'):
        raise ReportError('Есеп түрін және аралықты таңдаңыз.')
    if preset == 'custom':
        try:
            a,b = (date.fromisoformat(params.get(k,'')) for k in ('start','end'))
        except ValueError:
            raise ReportError('Екі күнді де дұрыс енгізіңіз.')
    elif preset in ('today','yesterday'):
        a = b = today - timedelta(days=preset == 'yesterday')
    elif preset == 'month':
        a,b = today.replace(day=1),today
    elif preset == 'previous':
        b = today.replace(day=1)-timedelta(days=1)
        a = b.replace(day=1)
    else:
        b = today-timedelta(days=1)
        a = today-timedelta(days={'seven':7,'fourteen':14,'thirty':30}[preset])
    if b < a or (b-a).days >= 731 or b == date.max:
        raise ReportError('Басы соңынан кейін болмауы керек. 731 күнге дейін таңдаңыз.')
    return a,b,mode


def ratio(n,d):
    return n/d if d else None


def bounded(qs, limit):
    rows = list(qs[:limit+1])
    if len(rows) > limit:
        raise ReportError('Жолдар саны шектен асты. Қысқа аралықты таңдаңыз.')
    return rows


def advances_stage(step, event, track):
    kind, lesson = event['kind'], event['lesson']
    if step == 0:
        return kind == 'lesson_opened' and lesson in (1, 251)
    if step in (1, 2, 3):
        offset = 250 if track == 'ru' else 0
        return kind == 'lesson_completed' and event['track'] == track and lesson == offset + step
    return kind == {4:'paywall_viewed', 5:'paywall_purchase_clicked', 6:'whatsapp_opened'}.get(step)


def daily_chart(trend, start, end):
    """Insert zero points at gap edges so sparse historical ranges don't draw false plateaus."""
    end = max(start, end)
    days = {start, end}
    for day in trend:
        days.add(day)
        if day > start:
            days.add(day - timedelta(days=1))
        if day < end:
            days.add(day + timedelta(days=1))
    width_days = max(1, (end - start).days)
    peak = max((len(counts['active']) for counts in trend.values()), default=0)
    lines = {}
    for key in ('active', 'view'):
        points = []
        for day in sorted(days):
            count = len(trend.get(day, {}).get(key, ()))
            x = 500 if start == end else 1000 * (day - start).days / width_days
            y = 96 - 90 * count / max(1, peak)
            points.append(f'{x:.2f},{y:.2f}')
        lines[key] = ' '.join(points)
    return dict(lines, start=start, end=end, peak=peak)


def report(params, *, include_internal=False, contacts=False):
    now = timezone.now()
    a,b,mode = options(params,now)
    if params.get('sort', 'priority') not in crm.SORTS or params.get('segment', '') not in crm.FILTERS:
        raise ReportError('Клиент сүзгісін және сұрыптау ретін таңдаңыз.')
    start = datetime.combine(a,time.min,ZONE)
    end = datetime.combine(b+timedelta(days=1),time.min,ZONE)
    cutoff = now if mode == 'cohort' else min(now,end)
    User = get_user_model()
    registered = User.objects.filter(date_joined__gte=start,date_joined__lt=end)
    internal = User.objects.filter(Q(is_staff=True) | Q(is_superuser=True) | Q(groups__name='OqyAI Analytics Test')).values('pk')
    if not include_internal:
        registered = registered.exclude(pk__in=internal)
    reg_ids = set(bounded(registered.values_list('id', flat=True), LIMIT_USERS))
    events = Event.objects.filter(at__gte=start,at__lt=cutoff)
    purchases = Purchase.objects.filter(confirmed_at__gte=start,confirmed_at__lt=cutoff)
    retained = Event.objects.filter(at__lte=now)
    if not include_internal:
        retained = retained.exclude(Q(user_id__in=internal) | Q(visit__user_id__in=internal))
        events = retained.filter(at__gte=start, at__lt=cutoff)
        purchases = purchases.exclude(user_id__in=internal)
    if mode == 'cohort':
        events = events.filter(user_id__in=reg_ids)
        purchases = purchases.filter(user_id__in=reg_ids)
    rows = bounded(events.order_by('user_id','at','id').values(*EVENT_FIELDS), LIMIT_EVENTS)
    paid = dict(bounded(purchases.values_list('user_id','confirmed_at'), LIMIT_USERS))
    grouped = defaultdict(list)
    for e in rows:
        if e['user_id']:
            grouped[e['user_id']].append(e)
    ids = set(grouped) | reg_ids | set(paid)
    if len(ids)>LIMIT_USERS:
        raise ReportError('Қолданушылар саны көп. Аралықты қысқартыңыз.')
    lifetime = defaultdict(dict)
    for uid, kind, n in retained.filter(user_id__in=ids, kind__in=crm.INTENT_KINDS).values_list(
            'user_id', 'kind').annotate(n=Count('pk')):
        lifetime[uid][kind] = n
    progress = {}
    passed = QuizAttempt.objects.filter(user_id__in=list(map(str,ids)), is_passed=True)
    for row in passed.values('user_id').annotate(
        completed=Count('pk'), kk=Max('lesson_id',filter=Q(lesson_id__lte=250)), ru=Max('lesson_id',filter=Q(lesson_id__gt=250)),
        kk_free=Count('pk',filter=Q(lesson_id__in=(1,2,3))), ru_free=Count('pk',filter=Q(lesson_id__in=(251,252,253)))
    ):
        progress[int(row['user_id'])] = row
    confirmations = dict(Purchase.objects.filter(user_id__in=ids, confirmed_at__lte=now).values_list("user_id", "confirmed_at"))
    # A returning campaign is evidence of this visit, not evidence of original acquisition.
    signup = Event.objects.filter(user_id=OuterRef('pk'), kind='signup_completed', at__lt=cutoff).order_by('at')
    earliest = Visit.objects.filter(user_id=OuterRef('pk'), started__lt=cutoff).order_by('started', 'pk')
    accounts = User.objects.filter(pk__in=ids).annotate(
        source=Subquery(signup.values('visit__visitor__first_source')[:1]),
        campaign=Subquery(signup.values('visit__visitor__first_campaign')[:1]),
        earliest_visit=Subquery(earliest.values('pk')[:1]),
    )
    seen = defaultdict(set)
    trend = defaultdict(lambda: defaultdict(set))
    visited = set()
    for e in rows:
        uid = e['user_id']
        if e['visit_id']:
            visited.add(e['visit_id'])
        if uid and e['visit_id']:
            seen['active'].add(uid)
            trend[e['at'].astimezone(ZONE).date()]['active'].add(uid)
    stage_counts = [0]*9
    sources = defaultdict(lambda: defaultdict(int))
    users = []
    stage_days = defaultdict(list)
    fields = ['id','date_joined','source','campaign','earliest_visit','profile__current_lesson','profile__is_paid','profile__pk']
    if contacts:
        fields += ['username', 'profile__phone']
    for account in accounts.values(*fields).order_by('id'):
        uid, joined = account['id'], account['date_joined']
        source, campaign, earliest_visit = account['source'], account['campaign'], account['earliest_visit']
        history = grouped[uid]
        source = source or 'unknown'
        metrics = set()
        base = uid in (reg_ids if mode=='cohort' else seen['active'])
        step = 0
        funnel_track = None
        last_step_time = joined if mode=='cohort' else (history[0]['at'] if history else None)
        marks = {}
        for e in history:
            kind, lesson, stamp = e['kind'],e['lesson'],e['at']
            metric = {'lesson_opened':'opened','free_course_completed':'free','paywall_viewed':'view',
                      'paywall_purchase_clicked':'click','whatsapp_opened':'wa'}.get(kind)
            if kind=='lesson_completed' and lesson in (1,2,3,251,252,253):
                metric = ('first','second','third')[(lesson-1)%250]
            if metric:
                metrics.add(metric)
                marks.setdefault(metric,[]).append(stamp)
                trend[stamp.astimezone(ZONE).date()][metric].add(uid)
            if base and advances_stage(step, e, funnel_track) and (mode!='cohort' or stamp>=joined):
                if step==0:
                    funnel_track = e['track']
                step+=1
                stage_days[step].append((stamp-last_step_time).total_seconds()/60)
                last_step_time = stamp
        if uid in paid:
            metrics.add('paid')
            marks['paid'] = [paid[uid]]
            trend[paid[uid].astimezone(ZONE).date()]['paid'].add(uid)
            if base and step==7 and paid[uid]>=last_step_time:
                step+=1
                stage_days[step].append((paid[uid]-last_step_time).total_seconds()/60)
        if uid in reg_ids:
            metrics.add('registrations')
            marks['registrations']=[joined]
            trend[joined.astimezone(ZONE).date()]['registrations'].add(uid)
        for metric in metrics:
            seen[metric].add(uid)
            sources[(source,campaign or '')][metric]+=1
        for key,left,right in [('reg_rate','registrations','paid'),('free_rate','free','view'),
                               ('wa_rate','view','wa'),('paid_rate','view','paid')]:
            if left in marks and right in marks and max(marks[right])>=min(marks[left]):
                seen[key].add(uid)
                sources[(source,campaign or '')][key] += 1
        if base:
            for i in range(step+1):
                stage_counts[i]+=1
        activity = [e for e in history if e['visit_id']]
        meaningful = [e for e in activity if e['kind'] not in ('activity','session_started')]
        actions = [e for e in meaningful if e['kind']!='page_view']
        pages = [e for e in history if e['kind']=='page_view']
        visits = defaultdict(list)
        for e in history:
            if e['visit_id']:
                visits[e['visit_id']].append(e['at'])
        saved = progress.get(uid, {})
        last = actions[-1] if actions else None
        observed = next((label for key,label in reversed([('registrations','Тіркелді'),('opened','Сабақ ашты'),
            ('first','Бірінші сабақ'),('second','Екінші сабақ'),('third','Үшінші сабақ'),('free','Тегін курс'),
            ('view','Ұсыныс'),('click','Сатып алу батырмасы'),('wa','WhatsApp'),('paid','Сатып алды')]) if key in metrics),'Белгісіз')
        user = dict(id=uid,joined=joined,source=source,campaign=campaign or '',
            tracks=', '.join(sorted({e['track'] for e in history if e['track']})),
            first=activity[0]['at'] if activity else None,last=activity[-1]['at'] if activity else None,
            visits=len(visits),minutes=sum((max(v)-min(v)).total_seconds() for v in visits.values())/60,
            returned=len(visits)>1 or bool(visits and earliest_visit not in visits),current=account["profile__current_lesson"],highest_kk=saved.get('kk'),
            highest_ru=saved.get('ru'),free_kk=saved.get('kk_free',0),
            free_ru=saved.get('ru_free',0),view='view' in metrics,click='click' in metrics,wa='wa' in metrics,
            paid=uid in paid,verified=bool(confirmations.get(uid) and confirmations[uid] < cutoff),stage=observed,page=pages[-1]['path'] if pages else '',action=LABELS[last['kind']] if last else '',
            action_at=last['at'] if last else None,coverage='Тіркелген оқиғалар бар' if history else 'Оқиға дерегі жоқ',access=bool(account['profile__is_paid']), confirmed_at=confirmations.get(uid),
            completed=saved.get('completed', 0), free_count=max(saved.get('kk_free', 0), saved.get('ru_free', 0)),
            page_views=len(pages), hours_since=(now-activity[-1]['at']).total_seconds()/3600 if activity else None)
        if contacts:
            phone = account['profile__phone'] or ''
            user.update(name=account['username'], phone=phone, phone_status='Расталмаған' if phone else 'Көрсетілмеген',
                        whatsapp=crm.whatsapp_digits(phone), profile_id=account['profile__pk'])
        observed_counts = Counter(e['kind'] for e in history)
        for kind in ('quiz_started','quiz_completed','quiz_failed','subscription_cta_viewed','subscription_cta_clicked'):
            user[kind] = observed_counts[kind]
        for key in ('view','click','wa','first','second','third'):
            stamps = marks.get(key, [])
            user[key+'_count'] = len(stamps)
            user[key+'_first'] = stamps[0] if stamps else None
            user[key+'_last'] = stamps[-1] if stamps else None
        user['opened_first'] = next((e['at'] for e in history if e['kind']=='lesson_opened' and e['lesson'] in (1,251)), None)
        missing = []
        if source == 'unknown':
            missing.append('Acquisition source')
        if not history:
            missing.append('Event history')
        if user['completed'] and not observed_counts['lesson_completed']:
            missing.append('Dated lesson completions')
        user['missing'] = ', '.join(missing)
        crm.classify(user, lifetime[uid])
        users.append(user)
    totals = {k:len(seen[k]) for k,_ in METRICS}
    totals.update(visits=len(visited),revenue=None)
    for key,den in [('reg_rate','registrations'),('free_rate','free'),('wa_rate','view'),('paid_rate','view')]:
        totals[key]=ratio(len(seen[key]),len(seen[den]))
    funnel=[]
    for i,label in enumerate(['Тіркелген топ' if mode=='cohort' else 'Белсенді қолданушылар']+STAGES):
        n=stage_counts[i]
        prev=stage_counts[max(0,i-1)]
        funnel.append(dict(label=label,count=n,previous=ratio(n,prev),initial=ratio(n,stage_counts[0]),
                           drop=prev-n,drop_rate=ratio(prev-n,prev),minutes=(sum(stage_days[i])/len(stage_days[i]) if stage_days[i] else None)))
    source_rows = []
    for (source,campaign),v in sorted(sources.items()):
        source_rows.append([source,campaign]+[v[k] for k in ('registrations','first','free','view','click','paid')]+
                           [ratio(v['reg_rate'],v['registrations'])])
    crm_summary = crm.summary(users)
    users = crm.select_customers(users, params, contacts)
    return dict(customer_filter=params.get('segment', ''), customer_sort=params.get('sort', 'priority'),
                crm_summary=crm_summary, include_internal=include_internal, start=a,end=b,mode=mode,now=now,cutoff=cutoff,totals=totals,funnel=funnel,users=users,events=rows,
                sources=source_rows,chart=daily_chart(trend,a,cutoff.astimezone(ZONE).date() if mode=='cohort' else min(b,now.astimezone(ZONE).date())),trend=[(day,*[len(v[k]) for k in ('registrations','active','free','view','paid')]) for day,v in sorted(trend.items())],
                fresh=max((e['at'] for e in rows),default=None))
