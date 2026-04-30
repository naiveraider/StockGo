from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from sqlmodel import Session, select

from app.models.llm_policy import LlmPolicy


@dataclass(frozen=True)
class PolicyDefinition:
    key: str
    title: str
    description: str
    placeholders: tuple[str, ...]
    system_prompt: str
    user_prompt: str


POLICY_DEFINITIONS: dict[str, PolicyDefinition] = {
    "short_term_bias": PolicyDefinition(
        key="short_term_bias",
        title="Short-term bias",
        description="LLM strategy for single-ticker short-term bias reports.",
        placeholders=("price_summary", "headline_list"),
        system_prompt=(
            "You are a stock analyst. You must be concise, evidence-based, and avoid making up facts. "
            "Use the provided price feature text and headlines only."
        ),
        user_prompt=(
            "Price summary:\n{{price_summary}}\n\n"
            "Recent headlines (most recent first):\n{{headline_list}}\n\n"
            "Task:\n"
            "1) Summarize key events impacting the stock (3-6 bullets)\n"
            "2) Predict short-term market bias (UP/DOWN/NEUTRAL)\n"
            "3) Provide reasoning in 2-3 sentences citing evidence indices like [0], [1]\n"
            "Return JSON only."
        ),
    ),
    "long_term_bias": PolicyDefinition(
        key="long_term_bias",
        title="Long-term bias",
        description="LLM strategy for single-ticker long-term bias reports.",
        placeholders=("price_summary", "headline_list"),
        system_prompt=(
            "You are a long-horizon equity analyst. Stay evidence-based, avoid invented facts, and use only the "
            "provided price feature text and headlines when present."
        ),
        user_prompt=(
            "Price summary across the longer lookback window:\n{{price_summary}}\n\n"
            "Relevant headlines (most recent first, may be empty):\n{{headline_list}}\n\n"
            "Task:\n"
            "1) Summarize the most important long-term signals for the stock (3-6 bullets)\n"
            "2) Predict long-term bias (UP/DOWN/NEUTRAL)\n"
            "3) Provide reasoning in 2-3 sentences citing evidence indices like [0], [1] when headlines are available\n"
            "Return JSON only."
        ),
    ),
    "short_term_pick": PolicyDefinition(
        key="short_term_pick",
        title="Short-term pick",
        description="LLM strategy for 2-4 week idea generation.",
        placeholders=("idea_count", "candidate_set"),
        system_prompt=(
            "Act as a professional short-term equity trader. Use only the supplied candidate data. "
            "Do not invent options activity, catalyst dates, or technical levels that are not supported by the input. "
            "If data is missing, say Not available. Return JSON only."
        ),
        user_prompt=(
            "Goal: Identify U.S. stocks suitable for a 2-4 week holding period.\n\n"
            "Constraints:\n"
            "- Market: U.S. stocks\n"
            "- Time horizon: 1 month\n"
            "- Risk tolerance: medium-high\n"
            "- Prefer stocks with strong catalysts\n\n"
            "Screen for:\n"
            "- Upcoming catalysts (earnings, product launches, macro events)\n"
            "- High relative volume / unusual options activity when available\n"
            "- Strong momentum (recent breakout or trend continuation)\n"
            "- News sentiment (bullish/neutral/negative)\n\n"
            "For each stock provide:\n"
            "1. Ticker and company name\n"
            "2. Why it may move in the next 2-4 weeks\n"
            "3. Key catalyst (with expected date if possible)\n"
            "4. Technical setup (support/resistance, trend)\n"
            "5. Bull case vs bear case\n"
            "6. Clear entry range and exit strategy\n"
            "7. Risk level (low / medium / high)\n\n"
            "Return exactly {{idea_count}} high-conviction ideas only. Avoid generic large-cap picks unless the catalyst is clear.\n\n"
            "Candidate set:\n{{candidate_set}}"
        ),
    ),
    "long_term_pick": PolicyDefinition(
        key="long_term_pick",
        title="Long-term pick",
        description="LLM strategy for 3-year idea generation.",
        placeholders=("idea_count", "candidate_set"),
        system_prompt=(
            "Act as a long-term fundamental investor with a 3+ year horizon. Use only the supplied candidate data. "
            "Do not invent financial metrics or management commentary beyond the provided inputs. If data is missing, "
            "say Not available. Return JSON only."
        ),
        user_prompt=(
            "Goal: Identify high-quality stocks to hold for 3 years.\n\n"
            "Constraints:\n"
            "- Market: U.S. stocks\n"
            "- Time horizon: 3 years\n"
            "- Risk tolerance: medium\n\n"
            "Screen for:\n"
            "- Strong revenue and earnings growth\n"
            "- Durable competitive advantage (moat)\n"
            "- Large and growing market (TAM)\n"
            "- Solid balance sheet\n"
            "- Capable management\n\n"
            "For each stock provide:\n"
            "1. Ticker and company name\n"
            "2. Business model explanation (simple)\n"
            "3. Growth drivers for the next 3 years\n"
            "4. Competitive advantage (moat)\n"
            "5. Risks and threats\n"
            "6. Valuation (cheap / fair / expensive with reasoning)\n"
            "7. Why it could outperform the market over 3 years\n\n"
            "Return exactly {{idea_count}} high-conviction ideas. Avoid meme stocks or purely speculative plays.\n\n"
            "Candidate set from the full U.S. stock universe with cached fundamentals:\n{{candidate_set}}"
        ),
    ),
}


def list_policy_definitions() -> list[PolicyDefinition]:
    return [POLICY_DEFINITIONS[key] for key in POLICY_DEFINITIONS]


def get_policy_definition(key: str) -> PolicyDefinition:
    try:
        return POLICY_DEFINITIONS[key]
    except KeyError as exc:
        raise ValueError(f"Unsupported policy key: {key}") from exc


def ensure_default_llm_policies(engine) -> None:
    with Session(engine) as session:
        changed = False
        for definition in list_policy_definitions():
            existing = session.get(LlmPolicy, definition.key)
            if existing is None:
                session.add(
                    LlmPolicy(
                        key=definition.key,
                        title=definition.title,
                        description=definition.description,
                        system_prompt=definition.system_prompt,
                        user_prompt=definition.user_prompt,
                    )
                )
                changed = True
        if changed:
            session.commit()


def list_policies(session: Session) -> list[LlmPolicy]:
    return session.exec(select(LlmPolicy).order_by(LlmPolicy.key)).all()


def get_policy_prompts(session: Session | None, key: str) -> tuple[str, str]:
    definition = get_policy_definition(key)
    if session is None:
        return definition.system_prompt, definition.user_prompt

    policy = session.get(LlmPolicy, key)
    if policy is None:
        return definition.system_prompt, definition.user_prompt
    return policy.system_prompt, policy.user_prompt


def upsert_policy(
    session: Session,
    *,
    key: str,
    system_prompt: str,
    user_prompt: str,
    updated_by_user_id: int | None,
) -> LlmPolicy:
    definition = get_policy_definition(key)
    policy = session.get(LlmPolicy, key)
    now = datetime.now(timezone.utc)
    if policy is None:
        policy = LlmPolicy(
            key=definition.key,
            title=definition.title,
            description=definition.description,
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            updated_at=now,
            updated_by_user_id=updated_by_user_id,
        )
    else:
        policy.title = definition.title
        policy.description = definition.description
        policy.system_prompt = system_prompt
        policy.user_prompt = user_prompt
        policy.updated_at = now
        policy.updated_by_user_id = updated_by_user_id
    session.add(policy)
    session.commit()
    session.refresh(policy)
    return policy


def render_policy_template(template: str, values: dict[str, str]) -> str:
    rendered = template
    for key, value in values.items():
        rendered = rendered.replace(f"{{{{{key}}}}}", value)
    return rendered