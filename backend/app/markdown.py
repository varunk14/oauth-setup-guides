"""Render a guide as Markdown for copying and sharing."""

from __future__ import annotations

from app.schema import Evidence, Guide


def _tag(ev: Evidence, source_numbers: dict[str, int]) -> str:
    refs = [f"[{source_numbers[s]}]" for s in ev.source_ids if s in source_numbers]
    refs += [f"probe:{p}" for p in ev.probe_ids]
    text = f"`{ev.label.value}`"
    if refs:
        text += " " + " ".join(refs)
    if ev.note:
        text += f" ({ev.note})"
    return text


def render_markdown(guide: Guide, share_url: str | None = None) -> str:
    nums = {s.id: i for i, s in enumerate(guide.sources, start=1)}
    app = guide.app
    out: list[str] = []
    add = out.append

    add(f"# OAuth app setup guide: {app.name}")
    add("")
    add(
        f"**Difficulty: {guide.difficulty.level}.** {guide.difficulty.reason} "
        f"{_tag(guide.difficulty.evidence, nums)}"
    )
    add("")
    add(f"- Hands-on effort: {guide.time.hands_on}")
    add(f"- Approval wait: {guide.time.approval_wait} {_tag(guide.time.evidence, nums)}")
    if guide.time.detail:
        add(f"- Time detail: {guide.time.detail}")
    add(f"- Website: {app.website}")
    if app.developer_console_url:
        add(f"- Developer console: {app.developer_console_url}")
    if share_url:
        add(f"- Shareable link: {share_url}")
    add("")
    add(guide.summary)
    add("")

    note = guide.composio_note
    managed = {"yes": "Yes", "no": "No", "unknown": "Unknown"}[note.managed_oauth]
    add("## Composio managed OAuth")
    add("")
    add(
        f"Composio-managed OAuth app available: **{managed}** "
        f"(directory snapshot {note.snapshot_date}). {note.detail} {_tag(note.evidence, nums)}"
    )
    add("")

    add("## Steps")
    add("")
    for step in guide.steps:
        where = f" Where: {step.where_url}." if step.where_url else ""
        add(
            f"{step.order}. **{step.title}** ({step.who}). {step.action}{where} "
            f"Expected: {step.expected_result} {_tag(step.evidence, nums)}"
        )
    add("")

    if guide.requirements:
        add("## Requirements")
        add("")
        for req in guide.requirements:
            add(
                f"- **{req.name}** (required: {req.required}). {req.detail} "
                f"{_tag(req.evidence, nums)}"
            )
        add("")

    if guide.scopes:
        add("## Scopes")
        add("")
        add("| Scope | Purpose | Sensitivity | Triggers review | Evidence |")
        add("|---|---|---|---|---|")
        for sc in guide.scopes:
            review = "yes" if sc.triggers_review else "no"
            add(
                f"| `{sc.name}` | {sc.purpose} | {sc.sensitivity} | {review} | "
                f"{_tag(sc.evidence, nums)} |"
            )
        add("")

    rp = guide.review_process
    add("## Review and approval")
    add("")
    add(
        f"Review required: **{rp.required}**. {rp.trigger} Typical wait: {rp.typical_wait}. "
        f"{_tag(rp.evidence, nums)}"
    )
    if rp.what_to_submit:
        add("")
        add("What to submit:")
        add("")
        out.extend(f"- {item}" for item in rp.what_to_submit)
    if rp.common_rejections:
        add("")
        add("Common rejection reasons:")
        add("")
        out.extend(f"- {item}" for item in rp.common_rejections)
    add("")

    if guide.blockers:
        add("## Blockers and how to get past them")
        add("")
        for b in guide.blockers:
            contact = f" Contact: {b.contact}." if b.contact else ""
            add(f"- **{b.blocker}** {b.how_to_get_past}{contact} {_tag(b.evidence, nums)}")
        add("")

    avh = guide.agent_vs_human
    add("## What an agent can do vs what you must do")
    add("")
    for title, items in (
        ("The agent already did", avh.agent_did),
        ("An agent can do", avh.agent_can),
        ("You must do", avh.human_must),
    ):
        if items:
            add(f"**{title}:**")
            add("")
            out.extend(f"- {item}" for item in items)
            add("")

    if guide.nuances:
        add("## Nuances")
        add("")
        for n in guide.nuances:
            add(f"- **{n.topic.replace('_', ' ')}**: {n.detail} {_tag(n.evidence, nums)}")
        add("")

    if guide.unverified:
        add("## What we could not verify")
        add("")
        out.extend(f"- {item}" for item in guide.unverified)
        add("")

    if guide.probes:
        add("## Automated checks we ran")
        add("")
        add("| Check | Target | Outcome | Result | When (UTC) |")
        add("|---|---|---|---|---|")
        for p in guide.probes:
            add(
                f"| {p.id} ({p.kind}) | {p.target_url} | {p.outcome} | {p.summary} | "
                f"{p.ran_at.strftime('%Y-%m-%d %H:%M')} |"
            )
        add("")

    add("## Sources")
    add("")
    for s in guide.sources:
        add(f"{nums[s.id]}. [{s.title}]({s.url}) ({s.kind}, checked {s.checked_on})")
    add("")
    add(
        "Evidence labels: TESTED = our automated check observed it; SOURCED = an official or "
        "cited page states it; INFERRED = reasoned from sources or community reports; "
        "UNVERIFIED = could not be confirmed."
    )
    add("")
    gen = guide.meta
    add(
        f"_Generated by {gen.generated_by.replace('_', ' ')} on "
        f"{gen.generated_at.strftime('%Y-%m-%d')}._"
    )
    return "\n".join(out) + "\n"
