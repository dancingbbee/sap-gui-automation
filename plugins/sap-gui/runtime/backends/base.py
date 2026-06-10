"""OS-neutral SAP control interface. Subclass per platform.

sapctl builds an OS-neutral request body from CLI args and calls these methods;
each backend translates to its platform mechanism (macOS HTTP daemon / Windows COM).
"""


class Backend:
    def health(self, timeout):
        raise NotImplementedError

    def status(self, timeout):
        raise NotImplementedError

    def start(self, timeout):
        raise NotImplementedError

    def kill_orphans(self, dry_run):
        raise NotImplementedError

    def targets(self, timeout):
        raise NotImplementedError

    def exec_(self, body, timeout):       # macOS only (JS eval); Windows returns unsupported
        raise NotImplementedError

    def snapshot(self, body, timeout):
        raise NotImplementedError

    def screenshot(self, body, timeout):
        raise NotImplementedError

    def transact(self, body, timeout):
        raise NotImplementedError
