"""The one error type: an exit code, a message, the fix, and any extra JSON."""


class R2IError(Exception):
    """Exit codes: 2 input, 3 objects without a cached mesh, 4 validation failed."""

    def __init__(self, code, message, fix=None, **extra):
        super().__init__(message)
        self.code = code
        self.message = message
        self.fix = fix
        self.extra = extra

    def to_json(self):
        out = {"code": self.code, "message": self.message}
        if self.fix:
            out["fix"] = self.fix
        out.update(self.extra)
        return out
