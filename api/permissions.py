from rest_framework import permissions


def is_user(user_property):
    class IsUser(permissions.BasePermission):
        def has_object_permission(self, request, view, obj):
            return getattr(obj, user_property) == request.user

    return IsUser
