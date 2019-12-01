from rest_framework import serializers

from notes import models


class TagSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.Tag
        fields = ("id", "uuid", "name")


class TagsField(serializers.PrimaryKeyRelatedField):
    def get_queryset(self):
        return models.Tag.objects.filter(author=self.context["request"].user)


class NoteSerializer(serializers.ModelSerializer):
    tags = TagsField(many=True, required=False)

    class Meta:
        model = models.Note
        fields = ("id", "uuid", "text", "tags", "created")
