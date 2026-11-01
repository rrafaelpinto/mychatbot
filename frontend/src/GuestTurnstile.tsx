import { useEffect, useRef } from "react";

type TurnstileInstance = {
  render: (element: HTMLElement, options: {
    sitekey: string;
    action: string;
    callback: (token: string) => void;
    "expired-callback": () => void;
    "error-callback": () => void;
  }) => string;
  remove: (id: string) => void;
};

declare global {
  interface Window { turnstile?: TurnstileInstance }
}

export function GuestTurnstile({ siteKey, onToken, onError }: {
  siteKey: string;
  onToken: (token: string) => void;
  onError: (message: string) => void;
}) {
  const container = useRef<HTMLDivElement>(null);

  useEffect(() => {
    let widget: string | null = null;
    let disposed = false;
    const mount = () => {
      if (disposed || !container.current || !window.turnstile || widget !== null) return;
      widget = window.turnstile.render(container.current, {
        sitekey: siteKey,
        action: "candidate_chat",
        callback: onToken,
        "expired-callback": () => onToken(""),
        "error-callback": () => { onToken(""); onError("Bot verification unavailable."); },
      });
    };
    const existing = document.querySelector<HTMLScriptElement>("script[data-resumebot-turnstile]");
    const script = existing ?? document.createElement("script");
    if (!existing) {
      script.dataset.resumebotTurnstile = "true";
      script.src = "https://challenges.cloudflare.com/turnstile/v0/api.js?render=explicit";
      script.async = true;
      script.defer = true;
      document.head.appendChild(script);
    }
    const fail = () => { if (!disposed) onError("Could not load bot verification."); };
    script.addEventListener("load", mount);
    script.addEventListener("error", fail);
    mount();
    return () => {
      disposed = true;
      script.removeEventListener("load", mount);
      script.removeEventListener("error", fail);
      if (widget !== null && window.turnstile) window.turnstile.remove(widget);
      onToken("");
    };
  }, [siteKey, onToken, onError]);

  return <div className="guest-turnstile" ref={container} aria-label="Bot verification" />;
}
