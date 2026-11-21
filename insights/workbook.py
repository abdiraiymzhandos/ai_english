from tempfile import TemporaryFile

from openpyxl import Workbook
from openpyxl.cell import WriteOnlyCell
from openpyxl.styles import Font, PatternFill
from openpyxl.utils import get_column_letter
from datetime import datetime

from .crm import SUMMARY_LABELS
from .reports import METRICS, RATES, ZONE
from .taxonomy import DEFINITIONS as EVENT_DEFINITIONS, LABELS

USER_COLUMNS = {
    'id':'User ID','joined':'Registered','source':'First recorded source','campaign':'Campaign','tracks':'Tracks',
    'first':'First activity in scope','last':'Last activity in scope','visits':'Visits in scope',
    'minutes':'Estimated active span (min)','returned':'Returned since first retained visit','current':'Current profile lesson (now)',
    'highest_kk':'Highest passed KK (now)','highest_ru':'Highest passed RU (now)','free_kk':'Free passes KK (now)',
    'free_ru':'Free passes RU (now)','view':'Observed offer view','click':'Observed purchase click','wa':'Observed handoff',
    'paid':'Confirmed purchase in scope','verified':'Confirmed by observation cutoff','stage':'Last observed funnel stage','page':'Last page','action':'Last meaningful action',
    'action_at':'Action time','coverage':'Coverage','missing':'Missing evidence in scope',
    'segment':'Customer segment (now)', 'priority':'Follow-up priority', 'access':'Current paid access',
    'confirmed_at':'Independent confirmation time (if recorded as of generation)',
    'completed':'All saved lesson passes (now)', 'free_count':'Max free passes on one track (now)',
    'opened_first':'Observed first lesson opening', 'first_first':'First lesson passed at',
    'second_first':'Second lesson passed at','third_first':'Third lesson passed at',
    'quiz_started':'Observed quiz starts','quiz_completed':'Observed quiz passes','quiz_failed':'Observed quiz failures',
    'page_views':'Page views in scope','hours_since':'Hours since last in-scope activity at generation',
    'subscription_cta_viewed':'Continuation CTA views','subscription_cta_clicked':'Continuation CTA clicks',
    'view_count':'Paywall views in scope','view_first':'First paywall view','view_last':'Last paywall view',
    'click_count':'Purchase clicks in scope','click_last':'Last purchase click',
    'wa_count':'Handoffs in scope','wa_last':'Last handoff',
    'views':'Retained paywall views','clicks':'Retained purchase clicks','handoffs':'Retained WhatsApp handoffs',
}
DEFINITIONS = [
    ('Timezone','Asia/Almaty. Dates are inclusive. Timestamps in this workbook are local clock times.'),
    ('Activity','Events in the selected period across all registration dates. Registration counts use the account creation date.'),
    ('Cohort','Users registered during the selected dates. Their events are observed through report generation.'),
    ('Funnel','Distinct signed-in learners reaching the preceding stages in order on the same learning track for lessons 1–3. Activity starts with active users. Cohort starts with registrations. Anonymous visits do not enter person-level conversion rates.'),
    ('KPI conversion','People with both milestones in temporal order divided by distinct people with the earlier milestone. Blank means the denominator is zero.'),
    ('Drop-off','Difference between adjacent ordered stages within the observation window. It is an absence of recorded progression, not a reason for leaving.'),
    ('Durations','Time between first and last signals in a visit, summed in scope. Thirty minutes of inactivity starts a new visit. Browser closure time is unknown.'),
    ('Sources','Initial visitor attribution linked by a recorded signup. Later return campaigns do not establish how old accounts registered. Unknown means no usable attribution. Campaign is a sanitized UTM slug.'),
    ('Coverage','History begins with collection. Missing events may indicate older accounts, opt-out, network failure or retention expiry. Current profile and passed lessons are current snapshots, not dated historical milestones.'),
    ('Purchase','Explicit staff confirmation. WhatsApp handoff only proves that the site issued a redirect. Actual message delivery, app launch and payment are separate. Paid access alone is not evidence of purchase. Amounts are unknown.'),
    ('IDs','Internal numeric account IDs and random first-party visitor and visit IDs. Optional current unverified contact details appear only in Users.'),
    ('Current CRM','Each included account has one operational segment at generation. PAID takes precedence; then HOT, WARM, COLD. Evidence uses current saved progress and all retained intent through generation.'),
    ('PAID','Current course access; no prospect follow-up. Check independent confirmation separately.'),
    ('HOT','Unpaid with retained purchase click or WhatsApp redirect; high priority.'),
    ('WARM','Other unpaid learner with all three saved free passes on one track or a retained offer view; medium priority.'),
    ('COLD','Other unpaid learner; low priority. Retention, missing history or opt-out can limit evidence.'),
    ('Observation','Blank milestone timestamps and zero observed event counts indicate no retained evidence in scope. They do not establish inactivity.'),
    ('Contacts','Current unverified registration details, only in an explicitly authorized export. Stored as literal text.'),
    ('Internal accounts','Staff, superusers and explicit test-group members and their linked visits excluded by default. Device identity alone never excludes another visit.'),
    ('Daily','Daily distinct learners. Adding daily active counts can double-count returning learners.'),
]
SOURCE_HEADERS=['Source','Campaign','Registered','First lesson passed','Free course finished','Viewed offer','Purchase clicks','Confirmed buyers','Registration to sale']


def audio_context(event):
    return ' / '.join(event['context'].get(k, '') for k in ('section', 'phase', 'error')) if event['context'] else ''


def workbook(data, *, include_contacts=False):
    book = Workbook(write_only=True)
    def table(name, headers, rows, percentages=()):
        sheet=book.create_sheet(name)
        sheet.freeze_panes='A2'
        for i,title in enumerate(headers,1):
            sheet.column_dimensions[get_column_letter(i)].width=min(50,max(20,len(title)+3))
        header=[]
        for title in headers:
            c=WriteOnlyCell(sheet,value=title)
            c.font=Font(bold=True,color='FFFFFF')
            c.fill=PatternFill('solid',fgColor='383563')
            header.append(c)
        sheet.append(header)
        count=1
        for row in rows:
            cells=[]
            for index,value in enumerate(row):
                if isinstance(value,datetime):
                    value=value.astimezone(ZONE).replace(tzinfo=None)
                c=WriteOnlyCell(sheet,value=value)
                if isinstance(value,str):
                    c.data_type='s'  # Raw strings, even those starting with =, +, -, or @.
                elif isinstance(value,datetime):
                    c.number_format='yyyy-mm-dd hh:mm:ss'
                if index in percentages or (name=='Overview' and index==1 and row[0] in RATES):
                    c.number_format='0.0%'
                cells.append(c)
            sheet.append(cells)
            count+=1
        sheet.auto_filter.ref=f'A1:{get_column_letter(len(headers))}{count}'
    info=[('Report','OqyAI Analytics',''),('Start',data['start'],''),('End',data['end'],'Inclusive'),
          ('Timezone','Asia/Almaty',''),('Generated',data['now'],''),('Mode',data['mode'],''),
          ('Observation cutoff',data['cutoff'],''),('Latest event',data['fresh'],'')]
    info.extend([('Include internal accounts', data['include_internal'], 'Staff, superusers and members of OqyAI Analytics Test'),
                 ('Include current contact details', include_contacts, 'Users sheet only'),
                 ('CRM filter scope', 'Users and User_Journeys', 'Other sheets cover the full date/mode population'),
                 ('Customer filter', data['customer_filter'] or 'All', 'Search text omitted for privacy'),
                 ('Customer sort', data['customer_sort'], '')])
    info.extend((key, value, SUMMARY_LABELS[key]) for key,value in data['crm_summary'].items())
    table('Overview',['Metric','Value','Meaning'],info+[(k,data['totals'][k],v) for k,v in METRICS])
    table('Funnel',['Stage','Unique users','From previous','From initial','Drop-off','Drop-off rate','Mean minutes from previous'],
          ([v[k] for k in ('label','count','previous','initial','drop','drop_rate','minutes')] for v in data['funnel']),{2,3,5})
    columns = dict(USER_COLUMNS)
    if include_contacts:
        columns = {'id':'User ID', 'name':'Current username', 'phone':'Registered phone', 'phone_status':'Phone verification', **columns}
    def customer_row(user):
        for key in columns:
            value = user[key]
            if key in ('view','click','wa','returned'):
                value = 'Observed' if value else 'Not observed'
            elif key in ('paid', 'verified'):
                value = 'Confirmed' if value else 'No confirmation recorded'
            yield value
    table('Users',list(columns.values()),(customer_row(u) for u in data['users']))
    selected_ids = {u['id'] for u in data['users']}
    table('User_Journeys',['User ID','Visit ID','Almaty time','Event','Page','Lesson ID','Action','Origin','Track','Audio context'],
          ([e['user_id'],str(e['visit_id'] or ''),e['at'],LABELS[e['kind']],e['path'],e['lesson'],e['kind'],e['origin'],e['track'],audio_context(e)]
           for e in data['events'] if e['user_id'] in selected_ids and e['kind']!='activity'))
    table('Events',['Event UUID','User ID','Visitor ID','Visit ID','Almaty time','Type / action','Page','Path','Lesson ID',
                    'Track','Source','Medium','Campaign','Content','Platform','Origin','Audio context'],
          ([str(e['id']),e['user_id'],str(e['visit__visitor_id'] or ''),str(e['visit_id'] or ''),e['at'],e['kind'],
            e['page'],e['path'],e['lesson'],e['track'],e['visit__source'],e['visit__medium'],e['visit__campaign'],
            e['visit__content'],e['visit__platform'],e['origin'],audio_context(e)] for e in data['events']))
    table('Sources',SOURCE_HEADERS,data['sources'],{8})
    table('Definitions',['Name','Definition'],DEFINITIONS+list(EVENT_DEFINITIONS.items()))
    stream=TemporaryFile()
    book.save(stream)
    stream.seek(0)
    return stream
