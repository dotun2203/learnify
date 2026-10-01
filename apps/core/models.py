import uuid

from django.db import models


class TimeStampedModel(models.Model):
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class BaseModel(TimeStampedModel):
    """UUID primary key + timestamps. Use for every domain model."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    class Meta:
        abstract = True


class TenantQuerySet(models.QuerySet):
    def for_academy(self, academy):
        return self.filter(academy=academy)


class TenantScopedModel(BaseModel):
    """Every row owned by a creator academy inherits from this."""

    academy = models.ForeignKey(
        "academies.Academy", on_delete=models.CASCADE, related_name="+", db_index=True
    )

    objects = TenantQuerySet.as_manager()

    class Meta:
        abstract = True
