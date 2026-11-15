const form = document.querySelector("#chat-form");
const input = document.querySelector("#question");
const conversation = document.querySelector("#conversation");
const sendButton = document.querySelector("#send-button");
const statusText = document.querySelector("#chat-status");
const errorText = document.querySelector("#chat-error");

let sending = false;

function addMessage(author, text, fromUser = false) {
  const message = document.createElement("article");
  message.className = "chat-message";

  if (fromUser) {
    message.classList.add("from-user");
  }

  const heading = document.createElement("strong");
  heading.textContent = author;

  const body = document.createElement("p");
  body.textContent = text;

  message.append(heading, body);
  conversation.append(message);
  conversation.scrollTop = conversation.scrollHeight;
}

form.addEventListener("submit", async (event) => {
  event.preventDefault();

  if (sending) return;

  errorText.textContent = "";

  const question = input.value.trim();

  if (!question) {
    errorText.textContent = "Please enter a question.";
    input.focus();
    return;
  }

  sending = true;
  sendButton.disabled = true;
  input.readOnly = true;
  conversation.setAttribute("aria-busy", "true");
  statusText.textContent = "Waiting for a response…";

  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), 30000);

  try {
    const response = await fetch(form.action, {
      method: "POST",
      body: new FormData(form),
      credentials: "same-origin",
      headers: {
        "X-CSRFToken": form.elements.csrfmiddlewaretoken.value,
        "Accept": "application/json",
      },
      signal: controller.signal,
    });

    const contentType = response.headers.get("content-type") || "";

    if (!contentType.includes("application/json")) {
      throw new Error("The server could not respond. Refresh the page and try again.");
    }

    const data = await response.json();

    if (!response.ok) {
      throw new Error(data.error || "Your question could not be sent.");
    }

    if (typeof data.answer !== "string" || !data.answer.trim()) {
      throw new Error("No answer was returned. Please try again.");
    }

    addMessage("You", question, true);
    addMessage("Soccer Chat", data.answer);
    input.value = "";
  } catch (error) {
    errorText.textContent = error.name === "AbortError"
      ? "The request timed out. Your question is still here; please try again."
      : error.message || "Connection failed. Please try again.";
  } finally {
    clearTimeout(timeout);
    sending = false;
    sendButton.disabled = false;
    input.readOnly = false;
    conversation.setAttribute("aria-busy", "false");
    statusText.textContent = "";
    input.focus();
  }
});