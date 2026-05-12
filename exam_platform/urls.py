"""
URL configuration for exam_platform project.
Routes all app URLs through the exams app and serves media in development.
"""

from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.shortcuts import redirect

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

# Serve media and static files during development
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
