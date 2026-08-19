"""Turn individual messages into ordered conversations."""

from collections import defaultdict

from .models import MailMessage
from .privacy import Redactor


class ConversationBuilder:
    def build(self, messages: list[MailMessage], redactor: Redactor) -> list[dict[str, object]]:
        threads: dict[str, list[MailMessage]] = defaultdict(list)
        for message in messages:
            thread_id = message.references[0] if message.references else message.in_reply_to or message.id
            threads[thread_id].append(message)

        conversations: list[dict[str, object]] = []
        for thread_id, thread_messages in threads.items():
            thread_messages.sort(key=lambda message: message.sort_date)
            latest = thread_messages[-1]
            participants = sorted({address for message in thread_messages for address in [message.sender, *message.recipients] if address})
            conversations.append({
                "id": redactor.text(thread_id),
                "subject": latest.subject,
                "participants": participants,
                "message_count": len(thread_messages),
                "last_activity_at": latest.date,
                "messages": [message.to_dict() for message in thread_messages],
            })
        return sorted(conversations, key=lambda conversation: str(conversation["last_activity_at"]), reverse=True)
