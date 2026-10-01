from django.contrib import admin
from django.urls import include, path
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView

from apps.academies.views import PublicAcademyView
from apps.courses.urls import public_urlpatterns as course_public_urls
from apps.courses.urls import studio_urlpatterns as course_studio_urls
from apps.enrollments.urls import learn_urlpatterns as learn_urls

from apps.enrollments.urls import public_urlpatterns as enroll_public_urls
from apps.enrollments.urls import studio_urlpatterns as enroll_studio_urls

# API areas are split by WHAT they operate on, not by user type:
#   auth/      anyone / any logged-in user       (accounts)
#   academies/ list + create my academies         (academies)
#   studio/    academy members, X-Academy header  (courses, billing, analytics…) — later
#   learn/     enrolled students                  (enrollments, assessments, tutor) — later
#   public/    anyone: sales pages, checkout, certificate verify — later
#   platform/  Learnify team (IsPlatformAdmin) — later

studio_urls = [
    *course_studio_urls,
    *enroll_studio_urls,
]

public_urls = [
    path("academies/<slug:slug>/", PublicAcademyView.as_view(), name="public-academy"),
    *course_public_urls,
    *enroll_public_urls,
]
api_v1 = [
    path("auth/", include("apps.accounts.urls")),
    path("academies/", include("apps.academies.urls")),
    path("studio/", include(studio_urls)),
    path("learn/", include(learn_urls)),
    path("public/", include(public_urls))
]

urlpatterns = [
    path("admin/", admin.site.urls),
    path("health/", include("apps.core.urls")),
    path("api/v1/", include(api_v1)),
    path("api/schema/", SpectacularAPIView.as_view(), name="schema"),
    path("api/docs/", SpectacularSwaggerView.as_view(url_name="schema"), name="swagger-ui"),
]