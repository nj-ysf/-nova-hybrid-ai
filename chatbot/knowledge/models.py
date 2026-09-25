from django.db import models
from pgvector.django import VectorField
from projects.models import ProjectBoundModel


class KnowledgeBase(ProjectBoundModel):
    name = models.CharField(max_length=150)
    policy = models.ForeignKey("projects.AccessPolicy", on_delete=models.PROTECT)
    project_relations = ("policy",)

    def __str__(self):
        return self.name


class Document(ProjectBoundModel):
    knowledge_base = models.ForeignKey(KnowledgeBase, on_delete=models.CASCADE, related_name="documents")
    policy = models.ForeignKey("projects.AccessPolicy", on_delete=models.PROTECT)
    title = models.CharField(max_length=200)
    created_at = models.DateTimeField(auto_now_add=True)
    embedding_model = models.CharField(max_length=150)
    project_relations = ("knowledge_base", "policy")

    def __str__(self):
        return self.title


class DocumentChunk(models.Model):
    document = models.ForeignKey(Document, on_delete=models.CASCADE, related_name="chunks")
    ordinal = models.PositiveIntegerField()
    text = models.TextField()
    embedding = VectorField(dimensions=768)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["document", "ordinal"], name="chunk_document_ordinal")]

    def __str__(self):
        return f"{self.document_id}:{self.ordinal}"
