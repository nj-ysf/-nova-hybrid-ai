from django.contrib import admin

from .models import ChatMessage, Conversation


class HistoryAdmin(admin.ModelAdmin):
    """Operator-only read access; legacy adoption uses an explicit command."""

    def has_module_permission(self, request):
        return request.user.is_superuser

    def has_view_permission(self, request, obj=None):
        return request.user.is_superuser

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(Conversation)
class ConversationAdmin(HistoryAdmin):
    list_display = ("title", "project", "user", "updated_at")
    list_filter = ("project", "updated_at")
    search_fields = ("title", "user__username")
    list_select_related = ("project", "user")


@admin.register(ChatMessage)
class ChatMessageAdmin(HistoryAdmin):
    list_display = ("conversation", "role", "classification", "created_at", "content_preview")
    list_filter = ("role", "classification", "created_at")
    search_fields = ("content", "conversation__title")
    list_select_related = ("conversation",)

    @admin.display(description="Content")
    def content_preview(self, message):
        return message.content[:120]
