from auditlog.context import auditlog_value
from rest_framework_simplejwt.authentication import JWTAuthentication


class AuditlogJWTAuthentication(JWTAuthentication):
    """
    JWT authentication that also updates the auditlog context actor.

    AuditlogMiddleware captures request.user at middleware time, before DRF
    runs JWT authentication — so the actor is always None for JWT-authenticated
    requests. This class updates the mutable auditlog context dict in-place
    after successful authentication so audit log entries record the real user.
    """

    def authenticate(self, request):
        result = super().authenticate(request)
        if result is not None:
            user, _ = result
            try:
                ctx = auditlog_value.get()
                ctx['actor'] = user
            except LookupError:
                pass
        return result
