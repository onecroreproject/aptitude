"""
URL configuration for exam_platform project.
Routes all app URLs through the exams app and serves media in development.
"""

from django.contrib import admin
from django.urls import path, include, re_path
from django.conf import settings
from django.conf.urls.static import static
from django.shortcuts import redirect
from django.views.static import serve as static_serve

urlpatterns = [
    path("django-admin/", admin.site.urls),
    path("admin/", lambda r: redirect('admin_dashboard')),
    path('', include('exams.urls')),
]

# Custom Error Handlers
handler404 = 'exams.views.error_404'
handler500 = 'exams.views.error_500'
handler403 = 'exams.views.error_403'
handler400 = 'exams.views.error_400'

# Admin branding
admin.site.site_header = "Aptipro Management"
admin.site.site_title = "Aptipro Admin Portal"
admin.site.index_title = "Welcome to Aptipro Portal"

# ── Media files (user uploads: profile photos, etc.) ──────────────────────
# WhiteNoise serves /static/ in production but does NOT serve user uploads.
# We expose /media/ via Django's static serve view in BOTH dev and production
# so that profile_photo.url works on cPanel/Passenger deployments where we
# cannot edit the Apache config to add a media alias.
urlpatterns += static(
    settings.MEDIA_URL,
    document_root=settings.MEDIA_ROOT
)

# Static files: served by WhiteNoise in production; only need Django's
# fallback in DEBUG mode for the dev runserver.
if settings.DEBUG:
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
