import uuid
from datetime import datetime, timedelta

import rest_framework.utils.humanize_datetime
from django.utils import timezone
from django.utils.decorators import classonlymethod
from rest_framework import (exceptions, fields, permissions, status, views,
                            viewsets)
from rest_framework.decorators import action
from rest_framework.response import Response

from notes import models

from . import serializers
from .permissions import is_user


class TagViewSet(viewsets.ModelViewSet):
    queryset = models.Tag.objects.none()
    serializer_class = serializers.TagSerializer
    permission_classes = (
        permissions.IsAuthenticated,
        is_user("author"),
    )

    def get_queryset(self):
        return models.Tag.objects.filter(author=self.request.user)

    def perform_create(self, serializer):
        serializer.save(author=self.request.user)

    def perform_destroy(self, instance):
        instance.name = ""
        instance.deleted = True
        instance.save()


class NoteViewSet(viewsets.ModelViewSet):
    queryset = models.Note.objects.none()
    serializer_class = serializers.NoteSerializer
    permission_classes = (
        permissions.IsAuthenticated,
        is_user("author"),
    )

    def get_queryset(self):
        return models.Note.objects.filter(author=self.request.user, deleted=False)

    def perform_create(self, serializer):
        serializer.save(author=self.request.user)

    def perform_destroy(self, instance):
        instance.text = ""
        instance.tags.clear()
        instance.deleted = True
        instance.save()


class SyncViewSet(viewsets.ViewSet):
    permission_classes = (
        permissions.IsAuthenticated,
    )

    @classonlymethod
    def as_view(cls, actions=None, **initkwargs):
        actions = {"post": "sync"}
        return super().as_view(actions, **initkwargs)

    def sync(self, request):
        now = timezone.now()
        response = {
            "time": None,  # will be inserted after models updating
            "tags": [],
            "notes": [],
        }

        if "last_sync" in request.data:
            raw_last_sync = request.data["last_sync"]
            last_sync = fields.DateTimeField().to_internal_value(raw_last_sync)
        else:
            last_sync = datetime.min

        raw_tags = request.data.get("tags", [])
        self._apply_tags_changes(request, raw_tags)

        raw_notes = request.data.get("notes", [])
        self._apply_notes_changes(request, raw_notes)

        response["time"] = fields.DateTimeField().to_representation(now)
        response["tags"] += self._get_tags_changes(last_sync)
        response["notes"] += self._get_notes_changes(last_sync)

        return Response(response)

    def _apply_tags_changes(self, request, raw_tags):
        for raw_tag in raw_tags:
            try:
                tag = models.Tag.objects.get(uuid=uuid.UUID(raw_tag["uuid"]), author=request.user)
            except models.Tag.DoesNotExist:
                tag = None

            tag_serializer = serializers.TagSerializer(data=raw_tag, instance=tag, partial=True, context={"request": request})
            tag_serializer.is_valid(raise_exception=True)

            if "deleted" in tag_serializer.initial_data and tag_serializer.initial_data["deleted"]:
                try:
                    tag = models.Tag.objects.get(uuid=tag_serializer.initial_data["uuid"], author=request.user)
                    tag.name = ""
                    tag.deleted = True
                    tag.save()
                except models.Tag.DoesNotExist:
                    pass
            else:
                try:
                    tag = models.Tag.objects.get(uuid=uuid.UUID(tag_serializer.initial_data["uuid"]), author=request.user)
                    tag_serializer.update(tag, tag_serializer.validated_data)
                except models.Tag.DoesNotExist:
                    data = tag_serializer.validated_data.copy()
                    data["author"] = request.user
                    tag = tag_serializer.create(data)

    def _apply_notes_changes(self, request, raw_notes):
        for raw_note in raw_notes:
            if "tags" in raw_note:
                raw_note["tags"] = [
                    models.Tag.objects.get(uuid=uuid.UUID(tag), author=request.user).id
                    for tag in raw_note["tags"]
                ]

            try:
                note = models.Note.objects.get(uuid=raw_note["uuid"], author=request.user)
            except models.Note.DoesNotExist:
                note = None

            note_serializer = serializers.NoteSerializer(data=raw_note, instance=note, partial=True, context={"request": request})
            note_serializer.is_valid(raise_exception=True)

            if "deleted" in note_serializer.initial_data and note_serializer.initial_data["deleted"]:
                try:
                    note = models.Note.objects.get(uuid=uuid.UUID(note_serializer.initial_data["uuid"]), author=request.user)
                    note.text = ""
                    note.tags.clear()
                    note.deleted = True
                    note.save()
                except models.Note.DoesNotExist:
                    pass
            else:
                try:
                    note = models.Note.objects.get(uuid=note_serializer.initial_data["uuid"], author=request.user)
                    note_serializer.update(note, note_serializer.validated_data)
                except models.Note.DoesNotExist:
                    data = note_serializer.validated_data.copy()
                    data["author"] = request.user
                    note = note_serializer.create(data)

    def _get_tags_changes(self, since: datetime):
        result = []
        since = since.replace(microsecond=0) + timedelta(seconds=1)
        query = models.Tag.objects.filter(updated__gte=since)
        for tag in query:
            if tag.deleted:
                result.append({
                    "uuid": tag.uuid,
                    "deleted": True,
                })
            else:
                serializer = serializers.TagSerializer(tag)
                result.append(serializer.data)
        return result

    def _get_notes_changes(self, since):
        result = []
        query = models.Note.objects.filter(updated__gte=since)
        for note in query:
            if note.deleted:
                result.append({
                    "uuid": note.uuid,
                    "deleted": True,
                })
            else:
                serializer = serializers.NoteSerializer(note)
                data = serializer.data
                data["tags"] = [tag.uuid for tag in note.tags.all()]
                result.append(data)
        return result

    def list(self, request): pass  # required by router
