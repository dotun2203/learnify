from django.urls import path
from rest_framework.routers import DefaultRouter

from . import views

router = DefaultRouter()
router.register("courses", views.CourseViewSet, basename="course")
router.register("modules", views.ModuleViewSet, basename="module")
router.register("lessons", views.LessonViewSet, basename="lesson")

# Mounted at /api/v1/studio/
studio_urlpatterns = router.urls

# Mounted at /api/v1/public/
public_urlpatterns = [
    path("academies/<slug:academy_slug>/courses/",
         views.PublicCourseListView.as_view(), name="public-course-list"),
    path("academies/<slug:academy_slug>/courses/<slug:course_slug>/",
         views.PublicCourseDetailView.as_view(), name="public-course-detail"),
]