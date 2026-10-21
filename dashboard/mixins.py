from functools import wraps

from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.contrib.auth.views import redirect_to_login
from django.core.exceptions import PermissionDenied


class StaffRequiredMixin(LoginRequiredMixin, UserPassesTestMixin):
    """Only staff members get in. Visitors go to the login page, customers get a 403 page."""

    def test_func(self):
        return self.request.user.is_staff


def staff_required(view):
    """The same rule for function views."""

    @wraps(view)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect_to_login(request.get_full_path())
        if not request.user.is_staff:
            raise PermissionDenied
        return view(request, *args, **kwargs)

    return wrapper