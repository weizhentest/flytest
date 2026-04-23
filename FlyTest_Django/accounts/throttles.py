from rest_framework.throttling import AnonRateThrottle


class LoginRateThrottle(AnonRateThrottle):
    scope = "login"

    def allow_request(self, request, view):
        login_source = (
            request.headers.get("X-FlyTest-Login-Source")
            or request.META.get("HTTP_X_FLYTEST_LOGIN_SOURCE")
            or ""
        )
        if str(login_source).strip().lower() == "login-page":
            return True
        return super().allow_request(request, view)


class RegisterRateThrottle(AnonRateThrottle):
    scope = "register"

    def allow_request(self, request, view):
        if request.user and request.user.is_authenticated:
            return True

        self.key = self.get_cache_key(request, view)
        if self.key is None:
            return True

        self.history = self.cache.get(self.key, [])
        self.now = self.timer()

        while self.history and self.history[-1] <= self.now - self.duration:
            self.history.pop()

        return len(self.history) < self.num_requests

    def record_success(self):
        if getattr(self, "key", None) is None:
            return

        now = getattr(self, "now", self.timer())
        history = list(getattr(self, "history", []))
        history.insert(0, now)
        self.history = history
        self.cache.set(self.key, history, self.duration)
