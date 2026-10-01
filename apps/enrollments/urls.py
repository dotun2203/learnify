from django.urls import path
from rest_framework.routers import DefaultRouter

from . import views

learn_router = DefaultRouter()
learn_router.register("enrollments", views.MyEnrollmentViewSet, basename="my-enrollment")

# Mounted at /api/v1/learn/
learn_urlpatterns = [
    path("enrollments/<uuid:enrollment_id>/lessons/<uuid:lesson_id>/",
         views.LessonAccessView.as_view(), name="learn-lesson"),
    path("notifications/", views.MyNotificationsView.as_view(), name="learn-notifications"),
    *learn_router.urls,
]

studio_router = DefaultRouter()
studio_router.register("courses", views.CourseStudentsViewSet, basename="course-students")

# Mounted at /api/v1/studio/ (adds /courses/{id}/students/ and /enroll/)
studio_urlpatterns = studio_router.urls

# Mounted at /api/v1/public/
public_urlpatterns = [
    path("academies/<slug:academy_slug>/courses/<slug:course_slug>/enroll/",
         views.PublicEnrollView.as_view(), name="public-enroll"),
]