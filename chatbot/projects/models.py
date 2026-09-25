from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator
from django.db import models


class Role(models.IntegerChoices):
    READER = 0, "Reader"
    EDITOR = 1, "Editor"
    ADMIN = 2, "Administrator"


class Classification(models.IntegerChoices):
    PUBLIC = 0, "Public"
    INTERNAL = 1, "Internal"
    CONFIDENTIAL = 2, "Confidential"
    RESTRICTED = 3, "Restricted"


class Tenant(models.Model):
    name = models.CharField(max_length=150)
    slug = models.SlugField(unique=True)

    def __str__(self):
        return self.name


class Project(models.Model):
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name="projects")
    name = models.CharField(max_length=150)
    slug = models.SlugField()
    enabled = models.BooleanField(default=True)
    allow_external = models.BooleanField(default=False)
    external_max_classification = models.PositiveSmallIntegerField(default=0, choices=Classification.choices)
    default_classification = models.PositiveSmallIntegerField(default=1, choices=Classification.choices)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["tenant", "slug"], name="project_tenant_slug")]

    def __str__(self):
        return f"{self.tenant_id}/{self.slug}"


class ProjectGroup(models.Model):
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name="groups")
    name = models.CharField(max_length=80)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["project", "name"], name="group_project_name")]

    def __str__(self):
        return f"{self.project_id}/{self.name}"


class Membership(models.Model):
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name="memberships")
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="project_memberships"
    )
    role = models.PositiveSmallIntegerField(choices=Role.choices, default=Role.READER)
    clearance = models.PositiveSmallIntegerField(default=0, validators=[MaxValueValidator(3)])
    groups = models.ManyToManyField(ProjectGroup, blank=True, related_name="memberships")
    can_use_external = models.BooleanField(default=False)
    active = models.BooleanField(default=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["project", "user"], name="membership_project_user")]

    def __str__(self):
        return f"{self.project_id}/{self.user}"


class AccessPolicy(models.Model):
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name="policies")
    name = models.CharField(max_length=100)
    minimum_role = models.PositiveSmallIntegerField(choices=Role.choices, default=Role.READER)
    access_level = models.PositiveSmallIntegerField(default=0, validators=[MaxValueValidator(3)])
    classification = models.PositiveSmallIntegerField(
        choices=Classification.choices, default=Classification.INTERNAL
    )
    groups = models.ManyToManyField(ProjectGroup, blank=True, related_name="policies")

    class Meta:
        indexes = [models.Index(fields=["project", "access_level", "minimum_role"])]

    def __str__(self):
        return f"{self.project_id}/{self.name}"


class ProjectBoundModel(models.Model):
    """Validate related configuration belongs to the same security boundary."""

    project = models.ForeignKey(Project, on_delete=models.CASCADE)
    project_relations: tuple[str, ...] = ()

    class Meta:
        abstract = True

    def clean(self):
        super().clean()
        for name in self.project_relations:
            if getattr(self, f"{name}_id", None) and getattr(self, name).project_id != self.project_id:
                raise ValidationError({name: "Must belong to this project."})
