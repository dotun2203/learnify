from rest_framework.permissions import BasePermission


class IsEnrolledStudent(BasePermission):
    """The student owns this enrollment. Lesson-level release checks happen
    in the service layer (lesson_availability), not here."""

    def has_object_permission(self, request, view, obj):
        student_id = getattr(obj, "student_id", None) or obj.enrollment.student_id
        return student_id == request.user.id