from rest_framework.permissions import SAFE_METHODS, BasePermission


class IsAdminOrReadOnly(BasePermission):
    """Anyone can read. Only staff members can create, change or delete."""

    def has_permission(self, request, view):
        return request.method in SAFE_METHODS or bool(request.user and request.user.is_staff)


class IsStaff(BasePermission):
    """Staff members only."""

    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated and request.user.is_staff)


class IsOwnerOrStaff(BasePermission):
    """The person who created the object, or a staff member."""

    def has_object_permission(self, request, view, obj):
        return request.user.is_staff or obj.user_id == request.user.id