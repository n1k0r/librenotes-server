from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from . import models


class TagAdmin(admin.ModelAdmin):
    list_display = ("__str__", "name", "author")
    search_fields = ("name", "author__username")


class NoteAdmin(admin.ModelAdmin):
    date_hierarchy = "created"
    search_fields = ("text", "author__username")
    list_display = ("__str__", "author", "created", "updated", "deleted")
    list_filter = ("deleted",)
    filter_horizontal = ("tags",)


admin.site.register(models.Tag, TagAdmin)
admin.site.register(models.Note, NoteAdmin)
admin.site.register(models.User, UserAdmin)
