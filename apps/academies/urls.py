from django.urls import path
from rest_framework.routers import DefaultRouter

from .views import AcademyViewSet, SlugAvailabilityView

router = DefaultRouter()
router.register("", AcademyViewSet, basename="academy")
urlpatterns = [
    path("slug-available/", SlugAvailabilityView.as_view(), name="academy-slug-available"),
    *router.urls,
    ]
