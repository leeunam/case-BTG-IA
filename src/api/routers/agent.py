import json
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

from src.api.deps import DbConn
from src.api.schemas.agent import ConversationItem, MessageRequest, ChatMessageItem

router = APIRouter(prefix="/agent", tags=["agent"])


@router.get("/conversations", response_model=list[ConversationItem])
def list_conversations(db: DbConn):
    rows = db.execute("""
        SELECT id, thread_id, title, created_at, last_message_at
        FROM agent_conversation
        ORDER BY last_message_at DESC
        LIMIT 50
    """).fetchall()
    return [
        ConversationItem(id=str(r[0]), thread_id=r[1], title=r[2] or "Nova conversa",
                         created_at=r[3], last_message_at=r[4])
        for r in rows
    ]


@router.post("/conversations", response_model=ConversationItem, status_code=201)
def create_conversation(db: DbConn):
    thread_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc)
    row = db.execute(
        "INSERT INTO agent_conversation (thread_id, title, created_at, last_message_at) "
        "VALUES (%s, %s, %s, %s) RETURNING id, thread_id, title, created_at, last_message_at",
        (thread_id, "Nova conversa", now, now),
    ).fetchone()
    db.commit()
    return ConversationItem(id=str(row[0]), thread_id=row[1], title=row[2],
                            created_at=row[3], last_message_at=row[4])


@router.delete("/conversations/{conversation_id}", status_code=204)
def delete_conversation(conversation_id: str, db: DbConn):
    result = db.execute(
        "DELETE FROM agent_conversation WHERE id = %s RETURNING id",
        (conversation_id,),
    ).fetchone()
    db.commit()
    if not result:
        raise HTTPException(404, "Conversation not found")


@router.get("/conversations/{thread_id}/messages", response_model=list[ChatMessageItem])
def get_conversation_messages(thread_id: str, db: DbConn):
    """Return the stored message history for a conversation thread."""
    from src.agents.fii_agent import build_agent

    existing = db.execute(
        "SELECT id FROM agent_conversation WHERE thread_id = %s", (thread_id,)
    ).fetchone()
    if not existing:
        raise HTTPException(404, "Conversation not found")

    agent = build_agent()
    config = {"configurable": {"thread_id": thread_id}}
    state = agent.get_state(config)

    result: list[ChatMessageItem] = []
    pending_tools: list[dict] = []

    for msg in state.values.get("messages", []):
        type_name = type(msg).__name__

        if type_name == "HumanMessage":
            pending_tools = []
            result.append(ChatMessageItem(role="user", content=str(msg.content)))
        elif type_name == "AIMessage":
            content = str(msg.content) if msg.content else ""
            if content:
                result.append(ChatMessageItem(
                    role="assistant",
                    content=content,
                    tool_calls=[{"name": t["name"], "content": t["content"]} for t in pending_tools],
                ))
                pending_tools = []
        elif type_name == "ToolMessage":
            pending_tools.append({
                "name": getattr(msg, "name", "") or "",
                "content": str(msg.content)[:300],
            })

    return result


@router.post("/messages")
def send_message(payload: MessageRequest, db: DbConn):
    """Stream agent response via Server-Sent Events."""
    from src.agents.fii_agent import build_agent

    thread_id = payload.thread_id
    message   = payload.message

    # Update last_message_at and auto-title from first message
    existing = db.execute(
        "SELECT id, title FROM agent_conversation WHERE thread_id = %s", (thread_id,)
    ).fetchone()
    if not existing:
        raise HTTPException(404, f"Conversation '{thread_id}' not found")

    title_update = existing[1]
    if title_update == "Nova conversa" and message:
        title_update = message[:60]
        db.execute(
            "UPDATE agent_conversation SET title = %s, last_message_at = NOW() WHERE thread_id = %s",
            (title_update, thread_id),
        )
    else:
        db.execute(
            "UPDATE agent_conversation SET last_message_at = NOW() WHERE thread_id = %s",
            (thread_id,),
        )
    db.commit()

    def event_stream():
        agent = build_agent()
        config = {"configurable": {"thread_id": thread_id}}
        try:
            for chunk in agent.stream(
                {"messages": [{"role": "user", "content": message}]},
                config=config,
                stream_mode="updates",
            ):
                for node, updates in chunk.items():
                    if node == "tools":
                        for tm in updates.get("messages", []):
                            yield f"data: {json.dumps({'type': 'tool', 'name': getattr(tm, 'name', ''), 'content': str(tm.content)[:300]})}\n\n"
                    elif node == "agent":
                        for msg in updates.get("messages", []):
                            content = getattr(msg, "content", "")
                            if content:
                                yield f"data: {json.dumps({'type': 'message', 'content': content})}\n\n"
        except Exception as exc:
            # Never expose raw exception strings — they may contain DB connection
            # strings, API keys, or other infrastructure details.
            safe_msg = "Erro interno ao processar a mensagem. Tente novamente."
            yield f"data: {json.dumps({'type': 'error', 'content': safe_msg})}\n\n"
        yield "data: [DONE]\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})
