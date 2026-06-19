from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

_PROMPT_PRIORITY_PREAMBLE = (
    "[PRIORITY RULES]\n"
    "You are Aida, a warm human-like hotel booking assistant.\n"
    "Use the latest user message and verified hotel data as truth. Never invent room capacity, prices, dates, or availability.\n"
    "For guest-sent media, name an exact room/category only when the latest message contains verified media context with "
    "`confidence_policy: you may use this context as verified`; otherwise ask one concise clarification and do not guess. "
    "Do not continue booking a room category that came only from an earlier unverified media guess.\n"
    "All prices must be in Kyrgyz som; never use rubles, ₽, dollars, or тенге.\n"
    "Keep replies natural, concise, emotionally warm, and use appropriate emojis.\n"
    "Do not start guest replies with generic phrases like 'Вот что могу подсказать'.\n"
    "Transfer to a manager only when a server tool succeeds or policy explicitly allows/needs handoff.\n"
    "If the guest asks a side question, answer it briefly and return to the current funnel step."
)


@dataclass(frozen=True)
class PromptSection:
    key: str
    role: str
    title: str
    content: str


class PromptAssembler(list):
    """
    List-compatible prompt builder.

    Existing OpenAI calls expect a plain list of {role, content} messages, so
    this class intentionally behaves like a list while keeping section metadata
    for diagnostics and future prompt-preview UI.
    """

    def __init__(self):
        super().__init__()
        self._sections: list[PromptSection] = []

    @property
    def sections(self) -> list[PromptSection]:
        return list(self._sections)

    def add_system(self, key: str, title: str, content: str | None) -> None:
        content = (content or '').strip()
        if not content:
            return
        title = (title or key).strip()
        body = f'[{title}]\n{content}' if title else content
        self._sections.append(PromptSection(key=key, role='system', title=title, content=content))
        self.append({'role': 'system', 'content': body})

    def add_raw_system(self, key: str, content: str | None) -> None:
        content = (content or '').strip()
        if not content:
            return
        title = _extract_section_title(content) or key
        self._sections.append(PromptSection(key=key, role='system', title=title, content=content))
        self.append({'role': 'system', 'content': content})

    def add_history(self, history: Iterable[dict] | None) -> None:
        for message in history or []:
            if message and message.get('role') and message.get('content') is not None:
                self.append(message)

    def add_user(self, content: str | None) -> None:
        self.append({'role': 'user', 'content': content or ''})

    def to_messages(self) -> list[dict]:
        return list(self)

    def section_keys(self) -> list[str]:
        return [section.key for section in self._sections]


def _extract_section_title(content: str) -> str:
    first_line = (content or '').strip().splitlines()[0] if (content or '').strip() else ''
    if first_line.startswith('[') and first_line.endswith(']'):
        return first_line.strip('[]')
    return ''


def consolidate_system_messages(messages: list[dict] | None) -> list[dict]:
    """Merge scattered system messages into one high-priority block."""
    system_parts: list[str] = []
    other_messages: list[dict] = []
    for message in messages or []:
        role = message.get('role')
        content = message.get('content')
        if role == 'system' and content:
            system_parts.append(str(content).strip())
        else:
            other_messages.append(message)
    if not system_parts:
        return list(messages or [])
    merged_system = _PROMPT_PRIORITY_PREAMBLE + "\n\n" + "\n\n".join(
        part for part in system_parts if part
    )
    return [{'role': 'system', 'content': merged_system}] + other_messages


def trim_messages_for_model(messages: list[dict] | None, *, max_dialog_messages: int = 18) -> list[dict]:
    """Keep all system/tool context and the latest dialog turns to reduce prompt dilution."""
    messages = list(messages or [])
    system_messages = [message for message in messages if message.get('role') == 'system']
    non_system = [message for message in messages if message.get('role') != 'system']
    if len(non_system) <= max_dialog_messages:
        return messages
    return system_messages + non_system[-max_dialog_messages:]


def build_scheduling_instruction() -> str:
    return (
        "You have the capability to schedule follow-ups or outreach at a specific date/time. "
        "If the guest asks to talk or get information at a specific time (e.g. 'сегодня в 19:00', 'завтра утром'), "
        "or if you need to check something and promise to write back at a specific time, you MUST explicitly "
        "promise to contact them at that time (e.g. 'Хорошо, я напишу вам сегодня в 19:00' or 'Я уточню этот вопрос и свяжусь с вами завтра в 10:00').\n"
        "The system will automatically parse your promise or the guest's requested time and schedule a message to be sent exactly then. "
        "Do NOT say that you cannot write to them at a specific time or that you don't have the ability to do so."
    )


def build_pooled_message_instruction() -> str:
    return (
        "The user sent several short messages in quick succession — "
        "they are combined below as a SINGLE conversation turn.\n"
        "Read ALL lines carefully and extract any information provided "
        "(names, preferences, quantities, dates, questions, requests). "
        "Treat everything you extracted as already known — do NOT ask again "
        "for information already present in the combined text. "
        "Address ALL their points together in ONE natural, concise reply."
    )


def build_stage_tool_policy_instruction(allowed_tools: Iterable[str] | None) -> str:
    tools = sorted(str(tool) for tool in (allowed_tools or []) if str(tool).strip())
    if not tools:
        return ''
    return (
        "Only these tools are available on the current funnel stage: "
        + ", ".join(tools)
        + ". Do not promise or imply actions that require unavailable tools. "
        "If the guest asks for something outside the allowed tools, answer briefly if useful, "
        "then return to the current stage goal and collect the missing required fields."
    )


def build_separate_room_request_instruction() -> str:
    return (
        "The guest is asking for separate sleeping places or separate room options. "
        "Do NOT limit the answer to family rooms. Use standard/comfort room combinations "
        "from get_room_options and present several accommodation variants when available. "
        "If the exact adult/child count changed and is ambiguous, state your assumption briefly "
        "and ask a concise clarification after showing the likely variants."
    )


def build_selected_media_instruction(selected_media) -> str:
    cat = selected_media.get_category_display()
    mtype = selected_media.media_type
    mtitle = selected_media.title
    return (
        f"You are about to send a {mtype} titled '{mtitle}' ({cat}) — "
        f"it will be delivered automatically as a SEPARATE Telegram message right after your text reply. "
        f"In your text reply, just mention it naturally in plain conversational text. "
        f"The guest's media request is already handled; do NOT transfer only because of the media request. "
        f"If the same message also contains a large group, sports camp, corporate, complaint, or refund request, handle that separately. "
        f"CRITICAL: Do NOT embed images with markdown syntax like ![...](attachment:...) or any URL. "
        f"Write ONLY conversational plain text — the photo will be sent separately."
    )


def build_media_library_instruction() -> str:
    return (
        "You have a media library with photos, videos, and documents. "
        "Only share media when the guest EXPLICITLY asks to see photos, pictures, or visuals. "
        "Do NOT spontaneously offer to share photos — answer questions in text. "
        "Never embed images with markdown syntax like ![...] in your text replies."
    )
