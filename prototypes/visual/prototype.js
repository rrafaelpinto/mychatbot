/* Standalone fictional prototype. No credentials, requests, tracking or AI calls. */
(() => {
  "use strict";

  const pages = ["home", "profile", "agent"];
  const questionLimit = 3;
  const views = new Map(
    pages.map((name) => [name, document.getElementById(`view-${name}`)])
  );
  const nav = [...document.querySelectorAll("[data-nav]")];
  const stateSelect = document.getElementById("state-select");
  const statusArea = document.getElementById("chat-status");
  const input = document.getElementById("chat-input");
  const send = document.getElementById("send-message");
  const messages = document.getElementById("conversation-messages");
  const remaining = document.getElementById("preview-remaining");
  const scroll = document.getElementById("conversation-scroll");
  let submitted = 0;
  let previewState = "ready";

  const examples = [
    {
      matches: /backend|experience|project|api/i,
      text: "Alex has worked on backend services using Django and Python, with an emphasis on REST API design and maintainable application architecture.",
      evidence: [
        "Designed REST APIs in Django, with attention to maintainability, authorization and predictable behavior.",
        "Used automated tests, code review and CI pipelines to support safer releases."
      ]
    },
    {
      matches: /reliab|test|quality|performance|design|approach/i,
      text: "Alex focuses on predictable behavior and data integrity. The fictional profile describes experience with PostgreSQL optimization, transactional workflows and automated testing.",
      evidence: [
        "Worked with PostgreSQL data models, query optimization and reliable transactional workflows.",
        "Used automated tests, code review and CI pipelines to support safer releases."
      ]
    },
    {
      matches: /technolog|stack|python|django|postgres|skill/i,
      text: "Alex's approved sample skills include Python, Django, PostgreSQL and REST API design.",
      evidence: [
        "Designed REST APIs in Django, with attention to maintainability, authorization and predictable behavior.",
        "Worked with PostgreSQL data models, query optimization and reliable transactional workflows."
      ]
    }
  ];

  const states = {
    loading: {
      title: "Working on the answer",
      text: "The Candidate Agent is preparing a response. This is only a visual loading state.",
      kind: "loading"
    },
    empty: {
      title: "No approved information yet",
      text: "This profile has no facts approved for public answers. The assistant cannot answer until the candidate reviews and publishes them.",
      kind: "warning"
    },
    quota: {
      title: "Question limit reached",
      text: "You have used the available questions for this demo session. Come back later to continue exploring.",
      kind: "warning"
    },
    denied: {
      title: "Access restricted",
      text: "This conversation is not available for your session. Verify your access before continuing.",
      kind: "error"
    },
    unavailable: {
      title: "Candidate Agent temporarily unavailable",
      text: "Answers cannot be generated right now. You can still explore the candidate's public profile.",
      kind: "error"
    }
  };

  function route() {
    const hash = window.location.hash.slice(1).split("?")[0];
    const selected = pages.includes(hash) ? hash : "home";
    for (const [name, element] of views) {
      element.hidden = name !== selected;
    }
    for (const link of nav) {
      if (link.dataset.nav === selected) {
        link.setAttribute("aria-current", "page");
      } else {
        link.removeAttribute("aria-current");
      }
    }
    document.title = `ResumeBot | ${selected === "home" ? "Evidence-led profiles" : selected === "profile" ? "Sample profile" : "Candidate Agent"}`;
    window.scrollTo({ top: 0, behavior: "instant" });
  }

  function renderTheme() {
    const dark = document.documentElement.dataset.theme === "dark";
    const button = document.getElementById("theme-toggle");
    button.setAttribute("aria-label", dark ? "Switch to light theme" : "Switch to dark theme");
    button.setAttribute("aria-pressed", String(dark));
    button.title = dark ? "Switch to light theme" : "Switch to dark theme";
    button.querySelector(".theme-icon").innerHTML = dark
      ? '<circle cx="12" cy="12" r="4"/><path d="M12 2v2m0 16v2M4.9 4.9l1.4 1.4m11.4 11.4 1.4 1.4M2 12h2m16 0h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4"/>'
      : '<path d="M20.5 14a8.6 8.6 0 0 1-10.4-10.4 8.6 8.6 0 1 0 10.4 10.4Z"/>';
  }

  function element(tag, className, text) {
    const node = document.createElement(tag);
    if (className) node.className = className;
    if (text !== undefined) node.textContent = text;
    return node;
  }

  function evidenceList(items) {
    const details = element("details", "evidence-details");
    details.append(element("summary", "", `${items.length} verified sample facts`));
    const list = element("ul");
    for (const fact of items) list.append(element("li", "", fact));
    details.append(list);
    return details;
  }

  function appendMessage(role, content, evidence) {
    const wrapper = element("div", `message message-${role}`);
    const bubble = element("div", "message-body");
    bubble.append(element("span", "message-label", role === "user" ? "You" : "Candidate Agent"));
    bubble.append(element("p", "", content));
    if (evidence?.length) bubble.append(evidenceList(evidence));
    wrapper.append(bubble);
    messages.append(wrapper);
    scroll.scrollTop = scroll.scrollHeight;
  }

  function showState(state) {
    previewState = state;
    statusArea.replaceChildren();
    if (state !== "ready") {
      const info = states[state];
      const wrapper = element("div", `state-feedback state-${info.kind}`);
      if (state === "loading") {
        const dots = element("span", "loading-dots");
        dots.setAttribute("aria-label", "Loading");
        for (let i = 0; i < 3; i += 1) dots.append(element("i"));
        wrapper.append(dots);
      }
      wrapper.append(element("strong", "", info.title));
      wrapper.append(element("p", "", info.text));
      statusArea.append(wrapper);
    }
    const canSubmit = state === "ready" && submitted < questionLimit;
    input.disabled = !canSubmit;
    send.disabled = !canSubmit;
    document.querySelectorAll("[data-question]").forEach((button) => {
      button.disabled = !canSubmit;
    });
    if (state === "ready" && submitted >= questionLimit) {
      stateSelect.value = "quota";
      showState("quota");
      return;
    }
    if (state === "ready") {
      remaining.textContent = `${questionLimit - submitted} example questions available`;
    } else if (state === "quota") {
      remaining.textContent = "Question limit reached";
    } else {
      remaining.textContent = "UI state preview";
    }
  }

  function answerFor(question) {
    return examples.find((example) => example.matches.test(question)) || {
      text: "I do not have approved information about that topic in this fictional sample. Try a question about backend development, reliability or technology.",
      evidence: []
    };
  }

  document.getElementById("chat-form").addEventListener("submit", (event) => {
    event.preventDefault();
    if (previewState !== "ready" || submitted >= questionLimit) return;
    const question = input.value.trim();
    if (!question) return;
    appendMessage("user", question);
    const example = answerFor(question);
    appendMessage("assistant", example.text, example.evidence);
    submitted += 1;
    input.value = "";
    showState(submitted >= questionLimit ? "quota" : "ready");
  });

  document.querySelectorAll("[data-question]").forEach((button) => {
    button.addEventListener("click", () => {
      if (previewState !== "ready") return;
      input.value = button.dataset.question;
      input.focus();
    });
  });

  document.getElementById("theme-toggle").addEventListener("click", () => {
    document.documentElement.dataset.theme =
      document.documentElement.dataset.theme === "dark" ? "light" : "dark";
    renderTheme();
  });

  stateSelect.addEventListener("change", (event) => showState(event.target.value));
  window.addEventListener("hashchange", route);

  route();
  renderTheme();
  showState("ready");
})();
