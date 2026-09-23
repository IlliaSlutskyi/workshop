# pip install streamlit
# streamlit run app.py

import base64
import copy
import json
import os
from pathlib import Path

import streamlit as st
from openai import OpenAI


# ------------------------------------------------------------
# Grundeinstellungen
# ------------------------------------------------------------

st.set_page_config(
    page_title="Prompt Battle – KI-Literacy Workshop",
    page_icon="⚔️",
    layout="centered",
)

BASE_DIR = Path(__file__).resolve().parent

with open(BASE_DIR / "tasks.json", "r", encoding="utf-8") as file:
    TASKS = json.load(file)


def get_secret(name, default=None):
    """Liest zuerst Umgebungsvariablen, danach Streamlit-Secrets."""
    env_value = os.getenv(name)
    if env_value not in (None, ""):
        return env_value

    try:
        return st.secrets[name]
    except Exception:
        return default


OPENAI_API_KEY = get_secret("OPENAI_API_KEY")
TEXT_MODEL = get_secret("OPENAI_TEXT_MODEL", "gpt-5.6")
IMAGE_MODEL = get_secret("OPENAI_IMAGE_MODEL", "gpt-image-2")

MAX_TEXT_CALLS = int(get_secret("MAX_TEXT_CALLS_PER_SESSION", 30))
MAX_IMAGE_CALLS = int(get_secret("MAX_IMAGE_CALLS_PER_SESSION", 6))


@st.cache_resource
def create_client(api_key):
    return OpenAI(api_key=api_key)


client = create_client(OPENAI_API_KEY) if OPENAI_API_KEY else None


# ------------------------------------------------------------
# Session-State
# Jeder Browser-Tab / jede Streamlit-Session hat eigenen Zustand.
# Es wird nichts in einer Datenbank gespeichert.
# ------------------------------------------------------------

DEFAULT_STATE = {
    "text_calls": 0,
    "image_calls": 0,
    "task1": {
        "student_answer": "",
        "reflection": "",
        "expert_revealed": False,
        "expert_answer": "",
        "differences": "",
    },
    "task2": {
        "attempts": [],
        "expert_revealed": False,
        "expert_answer": "",
    },
    "task3": {
        "simple_answer": "",
        "simple_reflection": "",
        "warning_signals": "",
        "critical_answer": "",
        "expert_revealed": False,
        "expert_answer": "",
    },
    "task4": {
        "baseline_images": {},
        "improved_images": {},
        "observation": "",
        "origin_explanation": "",
        "position": "",
        "expert_revealed": False,
    },
}

if "workshop" not in st.session_state:
    st.session_state.workshop = copy.deepcopy(DEFAULT_STATE)


def reset_workshop():
    # Auch die Widget-Keys löschen, damit Textfelder wirklich leer werden.
    for key in list(st.session_state.keys()):
        del st.session_state[key]
    st.session_state.workshop = copy.deepcopy(DEFAULT_STATE)


# ------------------------------------------------------------
# KI-Hilfsfunktionen
# ------------------------------------------------------------

SYSTEM_INSTRUCTIONS = """
Du bist die KI innerhalb eines pädagogisch betreuten KI-Literacy-Workshops
für Schülerinnen und Schüler von ungefähr 12 bis 15 Jahren.

Regeln:
- Beantworte die konkrete Eingabe direkt und verständlich.
- Verbessere einen ungenauen Schüler-Prompt nicht heimlich. Folge ihm so,
  wie er formuliert wurde, damit die Wirkung verschiedener Prompts sichtbar bleibt.
- Bewerte den Prompt nicht ungefragt. Die Reflexion findet anschließend im Workshop statt.
- Antworte altersgerecht und möglichst kompakt.
- Frage nicht nach echten Namen, Adressen, Kontaktdaten oder anderen persönlichen Daten.
- Wenn eine Behauptung oder Quelle nicht verifiziert ist, stelle sie nicht als sicher belegt dar.
- Behaupte nicht, dass du gerade im Internet recherchiert oder eine externe Quelle geprüft hast,
  wenn dir dafür kein Werkzeug zur Verfügung steht.
"""


def ensure_client():
    if client is None:
        st.error(
            "Kein OPENAI_API_KEY gefunden. Lege lokal die Datei "
            "`.streamlit/secrets.toml` an."
        )
        return False
    return True


def input_is_flagged(text):
    """Moderiert Schüler-Eingaben vor dem KI-Aufruf."""
    if not text or not text.strip():
        return False

    result = client.moderations.create(
        model="omni-moderation-latest",
        input=text,
    )
    return bool(result.results and result.results[0].flagged)


def output_is_flagged(text):
    """Moderiert die erzeugte Textantwort vor der Anzeige."""
    if not text or not text.strip():
        return False

    result = client.moderations.create(
        model="omni-moderation-latest",
        input=text,
    )
    return bool(result.results and result.results[0].flagged)


def generate_text(user_prompt, source_text=None):
    if not ensure_client():
        return ""

    state = st.session_state.workshop

    if state["text_calls"] >= MAX_TEXT_CALLS:
        st.warning(
            "Für diese Sitzung wurde das Text-Limit erreicht. "
            "Startet eine neue Runde oder wendet euch an das Workshop-Team."
        )
        return ""

    if not user_prompt.strip():
        st.warning("Bitte gebt zuerst einen Prompt ein.")
        return ""

    try:
        if input_is_flagged(user_prompt):
            st.warning(
                "Diese Eingabe kann in diesem Workshop nicht an die KI gesendet werden. "
                "Formuliert sie bitte sachlich und ohne sensible oder gefährliche Inhalte."
            )
            return ""

        if source_text:
            model_input = (
                "ARBEITSTEXT:\n"
                f"{source_text}\n\n"
                "AUFTRAG DER SCHÜLER:INNEN:\n"
                f"{user_prompt}"
            )
        else:
            model_input = user_prompt

        response = client.responses.create(
            model=TEXT_MODEL,
            instructions=SYSTEM_INSTRUCTIONS,
            input=model_input,
            max_output_tokens=800,
        )

        state["text_calls"] += 1
        answer = response.output_text.strip()

        if output_is_flagged(answer):
            st.warning(
                "Die erzeugte Antwort wurde vom Sicherheitsfilter zurückgehalten. "
                "Bitte probiert eine andere Formulierung."
            )
            return ""

        return answer

    except Exception as error:
        st.error(f"Fehler bei der KI-Anfrage: {error}")
        return ""


def generate_image(prompt):
    if not ensure_client():
        return None

    state = st.session_state.workshop

    if state["image_calls"] >= MAX_IMAGE_CALLS:
        st.warning(
            "Für diese Sitzung wurde das Bild-Limit erreicht. "
            "Wendet euch an das Workshop-Team."
        )
        return None

    if not prompt.strip():
        st.warning("Es fehlt ein Bild-Prompt.")
        return None

    try:
        if input_is_flagged(prompt):
            st.warning(
                "Dieser Bild-Prompt kann in diesem Workshop nicht gesendet werden."
            )
            return None

        result = client.images.generate(
            model=IMAGE_MODEL,
            prompt=prompt,
        )

        state["image_calls"] += 1

        if not result.data or not result.data[0].b64_json:
            st.error("Die Bild-KI hat kein Bild zurückgegeben.")
            return None

        return base64.b64decode(result.data[0].b64_json)

    except Exception as error:
        st.error(
            "Fehler bei der Bildgenerierung: "
            f"{error}\n\n"
            "Hinweis: Für GPT-Image kann je nach API-Projekt eine "
            "Organisations-Verifizierung erforderlich sein."
        )
        return None


# ------------------------------------------------------------
# Wiederverwendbare UI
# ------------------------------------------------------------

def show_ai_answer(answer, title="KI-Antwort"):
    if answer:
        st.markdown(f"#### {title}")
        st.container(border=True).write(answer)


def show_takeaway(text):
    st.success(f"**Key Takeaway:** {text}")


def navigation():
    labels = [
        "1 · Erklärt es mir",
        "2 · Macht es verrückt",
        "3 · Fake News erkennen",
        "4 · Klischee-Check",
    ]

    st.sidebar.title("⚔️ Prompt Battle")
    st.sidebar.caption("Workshop-App ohne Scratch-Demo")

    selected = st.sidebar.radio(
        "Aufgabe auswählen",
        labels,
        key="navigation",
    )

    st.sidebar.divider()
    st.sidebar.caption(
        f"Text-Anfragen: {st.session_state.workshop['text_calls']}/{MAX_TEXT_CALLS}\n\n"
        f"Bild-Anfragen: {st.session_state.workshop['image_calls']}/{MAX_IMAGE_CALLS}"
    )

    if st.sidebar.button("Gesamte Sitzung zurücksetzen"):
        reset_workshop()
        st.rerun()

    return labels.index(selected) + 1


# ------------------------------------------------------------
# Aufgabe 1
# ------------------------------------------------------------

def render_task1():
    task = TASKS["task1"]
    state = st.session_state.workshop["task1"]

    st.header("1 · Erklärt es mir")
    st.subheader(task["subtitle"])

    st.markdown(f"**a)** {task['task_a']}")

    student_prompt = st.text_area(
        "Euer Prompt",
        key="task1_prompt",
        placeholder="Schreibt hier euren Prompt zur Erklärung von Abseits …",
        height=120,
    )

    if st.button("Prompt testen", key="task1_test", type="primary"):
        with st.spinner("Die KI antwortet …"):
            state["student_answer"] = generate_text(student_prompt)

    show_ai_answer(state["student_answer"])

    if state["student_answer"]:
        st.markdown(f"**b)** {task['task_b']}")
        state["reflection"] = st.text_area(
            "Was fällt euch an der Antwort auf?",
            value=state["reflection"],
            key="task1_reflection",
            height=100,
        )

        if st.button("Experten-Prompt aufdecken", key="task1_reveal"):
            state["expert_revealed"] = True

    if state["expert_revealed"]:
        st.markdown("#### Experten-Prompt")
        st.code(task["expert_prompt"], language=None)

        if st.button("Experten-Prompt testen", key="task1_expert_test"):
            with st.spinner("Die KI beantwortet den Experten-Prompt …"):
                state["expert_answer"] = generate_text(task["expert_prompt"])

        show_ai_answer(state["expert_answer"], "Antwort auf den Experten-Prompt")

        if state["expert_answer"]:
            st.markdown(f"**c)** {task['task_c']}")
            state["differences"] = st.text_area(
                "Nennt mindestens zwei Unterschiede.",
                value=state["differences"],
                key="task1_differences",
                height=110,
            )
            show_takeaway(task["takeaway"])


# ------------------------------------------------------------
# Aufgabe 2
# ------------------------------------------------------------

def render_task2():
    task = TASKS["task2"]
    state = st.session_state.workshop["task2"]

    st.header("2 · Macht es verrückt")
    st.markdown(f"**a)** {task['task_a']}")
    st.caption("Ihr könnt mehrere Varianten testen und anschließend euer bestes Ergebnis auswählen.")

    student_prompt = st.text_area(
        "Euer kreativer Prompt",
        key="task2_prompt",
        placeholder="Beispiel: Schreibe … über einen Hund / eine Katze / einen Pinguin …",
        height=130,
    )

    if st.button("Neue Variante testen", key="task2_test", type="primary"):
        with st.spinner("Die KI wird kreativ …"):
            answer = generate_text(student_prompt)
        if answer:
            state["attempts"].append(
                {"prompt": student_prompt, "answer": answer}
            )

    if state["attempts"]:
        st.markdown("#### Eure Versuche")
        for index, attempt in enumerate(state["attempts"], start=1):
            with st.expander(f"Versuch {index}", expanded=index == len(state["attempts"])):
                st.markdown("**Prompt**")
                st.write(attempt["prompt"])
                st.markdown("**KI-Antwort**")
                st.write(attempt["answer"])

        st.markdown(f"**b)** {task['task_b']}")

        if st.button("Experten-Prompt aufdecken", key="task2_reveal"):
            state["expert_revealed"] = True

    if state["expert_revealed"]:
        st.markdown("#### Experten-Prompt")
        st.code(task["expert_prompt"], language=None)

        if st.button("Experten-Prompt testen", key="task2_expert_test"):
            with st.spinner("Die KI beantwortet den Experten-Prompt …"):
                state["expert_answer"] = generate_text(task["expert_prompt"])

        show_ai_answer(state["expert_answer"], "Antwort auf den Experten-Prompt")
        show_takeaway(task["takeaway"])


# ------------------------------------------------------------
# Aufgabe 3
# ------------------------------------------------------------

def render_task3():
    task = TASKS["task3"]
    state = st.session_state.workshop["task3"]

    st.header("3 · Text-Zusammenfassung & Fake News erkennen")

    st.markdown(f"### {task['source_title']}")
    st.container(border=True).write(task["source_text"])

    st.markdown(f"**a)** {task['task_a']}")
    st.code(task["simple_prompt"], language=None)

    if st.button(
        "„Fass den Text zusammen“ testen",
        key="task3_simple_test",
        type="primary",
    ):
        with st.spinner("Die KI fasst den Text zusammen …"):
            state["simple_answer"] = generate_text(
                task["simple_prompt"],
                source_text=task["source_text"],
            )

    show_ai_answer(state["simple_answer"])

    if state["simple_answer"]:
        state["simple_reflection"] = st.text_area(
            "Was fällt euch an dieser Antwort auf?",
            value=state["simple_reflection"],
            key="task3_simple_reflection",
            height=100,
        )

        st.markdown(f"**b)** {task['task_b']}")
        state["warning_signals"] = st.text_area(
            "Notiert mindestens zwei Warnsignale.",
            value=state["warning_signals"],
            key="task3_warning_signals",
            height=120,
            placeholder="1. …\n2. …",
        )

        st.markdown(f"**c)** {task['task_c']}")
        critical_prompt = st.text_area(
            "Euer kritischer Prüf-Prompt",
            key="task3_critical_prompt",
            height=140,
            placeholder="Formuliert selbst einen Prompt, der die Behauptungen kritisch prüfen lässt …",
        )

        if st.button(
            "Kritischen Prompt testen",
            key="task3_critical_test",
        ):
            with st.spinner("Die KI prüft den Text …"):
                state["critical_answer"] = generate_text(
                    critical_prompt,
                    source_text=task["source_text"],
                )

        show_ai_answer(state["critical_answer"], "Antwort auf euren Prüf-Prompt")

        if state["critical_answer"]:
            if st.button("Experten-Prompt aufdecken", key="task3_reveal"):
                state["expert_revealed"] = True

    if state["expert_revealed"]:
        st.markdown("#### Experten-Prompt")
        st.code(task["expert_prompt"], language=None)

        expert_prompt_with_text = task["expert_prompt"].replace(
            "[Aussage]",
            task["source_text"],
        )

        if st.button("Experten-Prompt testen", key="task3_expert_test"):
            with st.spinner("Die KI prüft mit dem Experten-Schema …"):
                state["expert_answer"] = generate_text(
                    expert_prompt_with_text
                )

        show_ai_answer(state["expert_answer"], "Antwort auf den Experten-Prompt")

        if state["expert_answer"]:
            show_takeaway(task["takeaway"])


# ------------------------------------------------------------
# Aufgabe 4
# ------------------------------------------------------------

def render_task4():
    task = TASKS["task4"]
    state = st.session_state.workshop["task4"]

    st.header("4 · Klischee-Check: Denkt mit")
    st.warning(
        "Die Bilder sind KI-generiert und können Klischees enthalten. "
        "Beschreibt das Bild, ohne Eigenschaften auf echte Personen im Raum zu übertragen."
    )

    group_names = list(task["groups"].keys())
    selected_group = st.radio(
        "Wählt eure Gruppe",
        group_names,
        horizontal=True,
        key="task4_group",
    )

    base_prompt = task["groups"][selected_group]["prompt"]
    st.markdown("#### Ausgangs-Prompt")
    st.code(base_prompt, language=None)

    if st.button("Ausgangsbild generieren", key="task4_image_generate", type="primary"):
        with st.spinner("Die Bild-KI generiert …"):
            image_bytes = generate_image(base_prompt)
        if image_bytes:
            state["baseline_images"][selected_group] = image_bytes

    baseline_image = state["baseline_images"].get(selected_group)

    if baseline_image:
        st.image(
            baseline_image,
            caption=f"KI-Bild: {selected_group}",
            use_container_width=True,
        )

        st.markdown(f"**a)** {task['task_a']}")
        state["observation"] = st.text_area(
            "Was fällt euch auf?",
            value=state["observation"],
            key="task4_observation",
            height=110,
        )

        st.markdown(f"**b)** {task['task_b']}")
        state["origin_explanation"] = st.text_area(
            "Woher könnten solche Muster oder Klischees kommen?",
            value=state["origin_explanation"],
            key="task4_origin",
            height=110,
        )

        st.markdown(f"**c)** {task['task_c']}")
        state["position"] = st.text_area(
            "Eure begründete Stellungnahme",
            value=state["position"],
            key="task4_position",
            height=120,
        )

        if st.button("Möglichen Experten-Prompt aufdecken", key="task4_reveal"):
            state["expert_revealed"] = True

    if state["expert_revealed"]:
        improved_prompt = f"{base_prompt} {task['anti_bias_instruction']}"

        st.markdown("#### Möglicher Experten-Prompt")
        st.code(improved_prompt, language=None)

        if st.button(
            "Bild mit Anti-Klischee-Prompt generieren",
            key="task4_image_improved",
        ):
            with st.spinner("Die Bild-KI generiert eine zweite Variante …"):
                image_bytes = generate_image(improved_prompt)
            if image_bytes:
                state["improved_images"][selected_group] = image_bytes

        improved_image = state["improved_images"].get(selected_group)

        if improved_image:
            col1, col2 = st.columns(2)
            with col1:
                if baseline_image:
                    st.image(
                        baseline_image,
                        caption="Ausgangs-Prompt",
                        use_container_width=True,
                    )
            with col2:
                st.image(
                    improved_image,
                    caption="Mit Anti-Klischee-Hinweis",
                    use_container_width=True,
                )

        show_takeaway(task["takeaway"])


# ------------------------------------------------------------
# App
# ------------------------------------------------------------

st.title("⚔️ Prompt Battle")
st.caption("KI-Literacy-Workshop · interaktive Aufgaben 1–4")

st.info(
    "Workshop-Regel: Gebt keine echten Namen, Adressen, Telefonnummern, "
    "Passwörter oder andere persönliche Daten ein."
)

if not OPENAI_API_KEY:
    st.warning(
        "Die Oberfläche funktioniert, aber KI-Aufrufe erst, wenn "
        "`OPENAI_API_KEY` in `.streamlit/secrets.toml` gesetzt ist."
    )

current_task = navigation()

if current_task == 1:
    render_task1()
elif current_task == 2:
    render_task2()
elif current_task == 3:
    render_task3()
elif current_task == 4:
    render_task4()