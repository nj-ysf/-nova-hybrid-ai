from rest_framework import serializers

from .models import ChatMessage, Conversation


class ChatRequestSerializer(serializers.Serializer):
    project_id = serializers.IntegerField(min_value=1)
    conversation_id = serializers.IntegerField(min_value=1, required=False)
    message = serializers.CharField(max_length=12000, trim_whitespace=True)
    mode = serializers.ChoiceField(choices=["auto", "local", "external"], default="auto")
    classification = serializers.IntegerField(min_value=0, max_value=3, default=0)
    knowledge_base_ids = serializers.ListField(
        child=serializers.IntegerField(min_value=1), max_length=30, required=False
    )
    stream = serializers.BooleanField(default=False)

    def validate(self, attrs):
        if attrs.pop("stream"):
            raise serializers.ValidationError(
                {
                    "stream": "The MVP chat endpoint returns JSON. Streaming transport is available only through provider adapters."
                }
            )
        unknown = set(self.initial_data) - set(self.fields)
        if unknown:
            raise serializers.ValidationError("Unknown request fields.")
        return attrs


class ConversationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Conversation
        fields = ["id", "project_id", "title", "created_at", "updated_at"]


class MessageSerializer(serializers.ModelSerializer):
    class Meta:
        model = ChatMessage
        fields = ["id", "role", "content", "created_at", "source_document_ids"]
