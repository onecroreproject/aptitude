"""
URL configuration for exam_platform project.
Routes all app URLs through the exams app and serves media in development.
"""

from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path("django-admin/", admin.site.urls),
    path('', include('exams.urls')),
]

# Admin branding
admin.site.site_header = "Aptipro Management"
admin.site.site_title = "Aptipro Admin Portal"
admin.site.index_title = "Welcome to Aptipro Portal"

# Serve media files during development
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
