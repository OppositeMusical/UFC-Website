from __future__ import annotations

import datetime as dt

from flask import Blueprint, abort, jsonify, render_template, request

from app.extensions import Session
from app.models.conversation import Conversation
from app.models.message import Message
from app.services.ai.base import ProviderError
from app.services.ai.factory import get_active_provider
from app.services.ai.prompts import CHAT_SYSTEM_PROMPT
from app.services.fighter_mentions import build_context_block, find_mentioned_fighters

bp = Blueprint("chat", __name__, url_prefix="/chat")


@bp.route("/")
def list_conversations():
    session = Session()
    try:
        conversations = session.query(Conversation).order_by(Conversation.updated_at.desc()).all()
        return render_template("chat.html", conversations=conversations, active_conversation=None, messages=[])
    finally:
        Session.remove()


@bp.route("/new", methods=["POST"])
def new_conversation():
    session = Session()
    try:
        conversation = Conversation(title="New Chat")
        session.add(conversation)
        session.commit()
        return jsonify({"conversation_id": conversation.id})
    finally:
        Session.remove()


@bp.route("/<int:conversation_id>")
def view_conversation(conversation_id: int):
    session = Session()
    try:
        conversation = session.get(Conversation, conversation_id)
        if conversation is None:
            abort(404)
        conversations = session.query(Conversation).order_by(Conversation.updated_at.desc()).all()
        return render_template(
            "chat.html",
            conversations=conversations,
            active_conversation=conversation,
            messages=conversation.messages,
        )
    finally:
        Session.remove()


@bp.route("/<int:conversation_id>/message", methods=["POST"])
def send_message(conversation_id: int):
    payload = request.get_json(silent=True) or {}
    content = (payload.get("content") or "").strip()
    if not content:
        return jsonify({"error": "content is required"}), 400

    session = Session()
    try:
        conversation = session.get(Conversation, conversation_id)
        if conversation is None:
            abort(404)

        session.add(Message(conversation_id=conversation.id, role="user", content=content))
        session.flush()

        mentioned = find_mentioned_fighters(session, content)
        context_block = ""
        if mentioned:
            context_block = "\n\nRelevant fighter stats:\n" + build_context_block(mentioned)

        history = [
            {"role": m.role, "content": m.content}
            for m in conversation.messages
            if m.role in ("user", "assistant")
        ]
        if context_block and history:
            history[-1] = {"role": "user", "content": history[-1]["content"] + context_block}

        try:
            provider = get_active_provider()
            reply = provider.generate(messages=history, system=CHAT_SYSTEM_PROMPT)
        except ProviderError as exc:
            reply = f"(Could not reach the AI provider: {exc})"

        session.add(Message(conversation_id=conversation.id, role="assistant", content=reply))
        conversation.updated_at = dt.datetime.utcnow()
        if conversation.title in (None, "New Chat") and mentioned:
            conversation.title = " vs ".join(f.name for f in mentioned[:2])
        session.commit()

        return jsonify({"reply": reply})
    finally:
        Session.remove()
