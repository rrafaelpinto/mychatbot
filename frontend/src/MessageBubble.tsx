import type { ChatMessage, PublicFact } from "./api/types";

export function MessageBubble({ message }: { message: ChatMessage }) {
  return <div className={"message message-" + (message.role === "user" ? "user" : "assistant")}><div className="message-body">
    <strong className="message-label">{message.role === "user" ? "You" : "Candidate Agent"}</strong><p>{message.content}</p>
    {message.evidence.length > 0 && <details className="evidence-details"><summary>{message.evidence.length} supporting fact(s)</summary><ul>{message.evidence.map((fact: PublicFact) => <li key={fact.id}>{fact.content}</li>)}</ul></details>}
  </div></div>;
}

