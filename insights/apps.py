from django.apps import AppConfig


class InsightsConfig(AppConfig):
    name = 'insights'
    verbose_name = 'OqyAI аналитикасы'
    default_auto_field = 'django.db.models.BigAutoField'

    def ready(self):
        from django.contrib.auth.signals import user_logged_in, user_logged_out
        from .tracking import schedule_event
        def auth_event(sender, request, user, **kwargs):
            if request and user and request.resolver_match and request.resolver_match.url_name in ('login','register','logout'):
                page = request.resolver_match.url_name
                schedule_event(request, 'logout_clicked' if page == 'logout' else 'login_completed',
                             page=page, path=request.path)
        user_logged_in.connect(auth_event, weak=False, dispatch_uid='insights.login')
        user_logged_out.connect(auth_event, weak=False, dispatch_uid='insights.logout')
