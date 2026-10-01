from .permissions import IsAcademyMember, resolve_academy


class AcademyScopedViewSetMixin:
    """Always filters by the request's academy and sets it on create.

    Every creator-studio viewset must use this so tenant data never leaks.
    """

    permission_classes = [IsAcademyMember]

    @property
    def academy(self):
        return resolve_academy(self.request)

    def get_queryset(self):
        return super().get_queryset().filter(academy=self.academy)

    def perform_create(self, serializer):
        serializer.save(academy=self.academy)
