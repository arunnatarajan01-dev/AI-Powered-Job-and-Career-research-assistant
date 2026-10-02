"""Middleware between a request and the resume, research, job, or review handler."""

from contextlib import contextmanager

from flask import has_request_context, request

from observability.traces import trace
from safety.admin_alert import notify_admin
from safety.guardrail import check_output, check_text

STEP_ORDER = (
    "bind_actor",
    "normalize",
    "input_guardrail",
    "trace",
    "handler",
    "output_guardrail",
)

_STEP_COPY = {
    "bind_actor": "Attach the signed-in user. A request with no session stays anonymous.",
    "normalize": "Trim text fields before a check or a model call.",
    "input_guardrail": "Stop unsafe input. The handler does not run after a block.",
    "trace": "Open a trace for this action and the steps inside it.",
    "handler": "Run the resume, research, job, or review action.",
    "output_guardrail": "Stop model text that leaks a secret or a hidden instruction.",
}


def pipeline_steps():
    """The middleware chain, in the order every agent action uses."""
    return [{"name": name, "detail": _STEP_COPY[name]} for name in STEP_ORDER]


def _normalize(fields):
    cleaned = {}
    for key, value in (fields or {}).items():
        if isinstance(value, str):
            cleaned[key] = value.strip()
        elif value is None:
            cleaned[key] = ""
        else:
            cleaned[key] = value
    return cleaned


def _client_addr(remote_addr):
    if remote_addr:
        return remote_addr
    if has_request_context():
        return request.remote_addr or "unknown"
    return "unknown"


class _Gate:
    def __init__(self, actor, fields, notify, endpoint, remote_addr):
        self.actor = actor or "anonymous"
        self.fields = fields
        self.notify = notify
        self.endpoint = endpoint
        self.remote_addr = remote_addr
        self.trace = None
        self.blocked = None
        self.output_blocked = None
        self.output_screened = False
        self.steps = ["bind_actor", "normalize"]

    def _alert(self, result, field, excerpt):
        if not self.notify or result.category == "invalid_input":
            return
        notify_admin(
            endpoint=self.endpoint,
            category=result.category,
            reason=result.reason,
            field=field,
            excerpt=excerpt or "",
            remote_addr=self.remote_addr,
        )

    def screen_output(self, text):
        """Run the output step. Call this before leaving the middleware block."""
        if self.output_screened or self.trace is None:
            return self.output_blocked
        self.output_screened = True
        with self.trace.span("output_guardrail") as span:
            result = check_output(text)
            if result.allowed:
                return None
            span["status"] = "blocked"
            span["attributes"]["category"] = result.category
            self.trace.status = "blocked"
            self._alert(result, "model_output", text)
            self.output_blocked = result
            return result


@contextmanager
def agent_middleware(
    name,
    route,
    actor="",
    fields=None,
    guard_fields=(),
    guard_output=False,
    notify=True,
    remote_addr="",
    **meta,
):
    """Run bind, normalize, input guardrail, and a trace around one agent action."""
    gate = _Gate(
        actor=actor,
        fields=_normalize(fields),
        notify=notify,
        endpoint=route,
        remote_addr=_client_addr(remote_addr),
    )
    with trace(
        name,
        actor=gate.actor,
        route=route,
        middleware=" > ".join(STEP_ORDER),
        **meta,
    ) as current:
        gate.trace = current
        gate.steps.extend(["input_guardrail", "trace"])
        targets = list(guard_fields) if guard_fields else []
        if not targets:
            with current.span("input_guardrail", fields=0):
                pass
        for field in targets:
            with current.span("input_guardrail", field=field) as span:
                result = check_text(gate.fields.get(field), field)
                if result.allowed:
                    continue
                span["status"] = "blocked"
                span["attributes"]["category"] = result.category
                current.status = "blocked"
                gate._alert(result, field, gate.fields.get(field))
                gate.blocked = result
                break
        try:
            yield gate
        finally:
            gate.steps.append("handler")
            if guard_output:
                gate.steps.append("output_guardrail")
