from .models import AuditLog

class AuditLogMiddleware:
    """
    Registra accesos de usuarios a las vistas (GET/POST).
    Solo se guarda: usuario, URL, método, IP.
    """
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)

        try:
            if request.user.is_authenticated:
                # Ignorar recursos estáticos
                if request.path.startswith(("/static/", "/media/", "/favicon.ico")):
                    return response

                AuditLog.log_action(
                    request=request,
                    user=request.user,
                    action="access",
                    model="Request",
                    description=f"Entró a {request.path} ({request.method})",
                    extra_data={
                        "path": request.path,
                        "method": request.method,
                        "query": dict(request.GET),
                    },
                )
        except Exception:
            # nunca romper la request por un error en logs
            pass

        return response
