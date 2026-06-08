from auditlog.models import LogEntry
from rest_framework import serializers

ACTION_LABELS = {
    LogEntry.Action.CREATE: 'create',
    LogEntry.Action.UPDATE: 'update',
    LogEntry.Action.DELETE: 'delete',
}


class AuditLogSerializer(serializers.Serializer):
    """Serializer for audit log entries."""
    id = serializers.IntegerField()
    timestamp = serializers.DateTimeField()
    action = serializers.SerializerMethodField()
    actor = serializers.SerializerMethodField()
    object_type = serializers.SerializerMethodField()
    object_repr = serializers.CharField()
    changes = serializers.SerializerMethodField()

    def get_action(self, obj):
        return ACTION_LABELS.get(obj.action, 'unknown')

    def get_actor(self, obj):
        if obj.actor:
            return {'id': obj.actor.id, 'email': obj.actor.email, 'name': obj.actor.name}
        return None

    def get_object_type(self, obj):
        if obj.content_type:
            return obj.content_type.model
        return None

    def get_changes(self, obj):
        return obj.changes_dict
