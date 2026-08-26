"""Stable WSGI target for a process manager: `vmock_clone.wsgi:application`.

Configuration comes from the environment because a `module:callable` target
cannot take constructor arguments:

    VMOCK_RULES             path to an alternative rules.yaml
    VMOCK_BENCHMARK         cohort name to plot against
    VMOCK_ALLOWED_ORIGINS   comma-separated extra origins allowed to POST
    VMOCK_MAX_UPLOAD        upload ceiling in bytes (default 8MB)
"""

from __future__ import annotations

from .wsgiapp import ScoreApp

application = ScoreApp()
