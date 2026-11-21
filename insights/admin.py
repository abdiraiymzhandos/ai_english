from django.contrib import admin
from django.contrib.admin.models import ADDITION, LogEntry
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator
from django.http import FileResponse
from django.template.response import TemplateResponse

from .crm import FILTERS, SEGMENT_LABELS, SORTS
from .models import PendingEvent, Visit
from .reports import METRICS, PRESETS, RATES, ReportError, report
from .taxonomy import LABELS
from .tracking import drain
from .workbook import workbook


def display(value, percentage=False):
    if value is None:
        return 'Белгісіз'
    return f'{value:.1%}' if percentage else value


@admin.register(Visit)
class AnalyticsAdmin(admin.ModelAdmin):
    def has_view_permission(self, request, obj=None):
        return request.user.has_perm('insights.view_visit')

    def has_add_permission(self, request): return False
    def has_delete_permission(self, request, obj=None): return False
    def has_change_permission(self, request, obj=None): return False

    def changelist_view(self, request, extra_context=None):
        if not request.user.has_perm('insights.view_visit'):
            raise PermissionDenied
        params = request.POST if request.method == 'POST' else request.GET
        viewer = request.user
        can_view = viewer.has_perm('insights.view_customer_contacts')
        can_export = can_view and viewer.has_perm('insights.export_customer_contacts')
        can_debug = viewer.has_perm('insights.include_internal_accounts')
        include_internal = params.get('internal') == '1'
        export_contacts = params.get('contacts') == '1'
        if (include_internal and not can_debug) or (export_contacts and (not can_export or request.method != 'POST')):
            raise PermissionDenied
        if params.get('q') and (request.method != 'POST' or (not can_view and not params['q'].isdigit())):
            raise PermissionDenied
        exporting = params.get('export') == 'xlsx'
        context = dict(
            self.admin_site.each_context(request), title='OqyAI — Сатылым аналитикасы', opts=self.model._meta,
            presets=PRESETS.items(), segments=FILTERS.items(), sorts=SORTS.items(),
            can_view=can_view, can_export=can_export, can_debug=can_debug,
            params=params, preset=params.get('preset', 'seven'), mode=params.get('mode', 'activity'),
        )
        try:
            drain(100)
            if PendingEvent.objects.exists():
                raise ReportError('Оқиғалар әлі өңделуде. Есепті кейін жаңартыңыз.')
            needs_identity = can_view and (not exporting or export_contacts or bool(params.get('q')))
            data = report(params, contacts=needs_identity, include_internal=include_internal)
        except ReportError as error:
            context['error']=str(error)
            return TemplateResponse(request,'admin/insights/visit/report.html',context,status=400)
        if exporting:
            stream=workbook(data, include_contacts=export_contacts)
            LogEntry.objects.log_action(user_id=request.user.pk,content_type_id=ContentType.objects.get_for_model(Visit).pk,
                object_id='',object_repr='Analytics XLSX',action_flag=ADDITION,
                change_message=f"{data['mode']} {data['start']} / {data['end']} ({len(data['events'])} events) contacts={export_contacts} internal={include_internal}")
            response = FileResponse(stream,as_attachment=True,filename=f"oqyai-{data['mode']}-{data['start']}-{data['end']}.xlsx",
                                content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
            response['Cache-Control'] = 'private, no-store'
            return response
        navigation = params.copy()
        for key in list(navigation):
            if key not in ('preset', 'mode', 'start', 'end', 'internal', 'segment', 'sort', 'p'):
                del navigation[key]
        users=data['users']
        selected=next((u for u in users if str(u['id'])==(params.get('user') or request.GET.get('user'))),None)
        timeline=[(e['at'],LABELS[e['kind']],e['path'],e['lesson'], e['context']) for e in data['events']
                  if selected and e['user_id']==selected['id'] and e['kind']!='activity']
        biggest_drop = max(data['funnel'][1:], key=lambda row: row['drop'])
        context.update(data, segment_cards=[(code, label, data["crm_summary"][code]) for code,label in SEGMENT_LABELS.items()], biggest_drop=biggest_drop, cards=[(label,display(data['totals'][k],k in RATES)) for k,label in METRICS],
                       navigation=navigation.urlencode(), selected=selected,timeline=Paginator(timeline,100).get_page(params.get('t')),
                       people=Paginator(users,50).get_page(params.get('p')))
        return TemplateResponse(request,'admin/insights/visit/report.html',context)
