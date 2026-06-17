# pip install streamlit
# streamlit run app.py

import json
import streamlit as st

import os
from openai import OpenAI

st.set_page_config(
    page_title="Prompt Battle Arena",
    page_icon="⚔️",
    layout="centered"
)

# Aufgaben laden
with open("tasks.json", "r", encoding="utf-8") as file:
    tasks = json.load(file)

def generate_ai_answer(student_prompt, selected_task):
    api_key = st.secrets.get("OPENAI_API_KEY", os.getenv("OPENAI_API_KEY"))
    model = st.secrets.get("OPENAI_MODEL", "gpt-5.5")

    if not api_key:
        return "Fehler: Es wurde kein OpenAI API-Key gefunden."

    client = OpenAI(api_key=api_key)

    system_prompt = """
    Du bist ein KI-Chatbot in einem KI-Literacy-Workshop für Oberstufenschüler:innen.

    Deine Aufgabe:
    - Beantworte den Prompt der Schüler:innen verständlich.
    - Bleibe bei der Workshop-Aufgabe.
    - Erfinde keine Quellen.
    - Frage nicht nach echten personenbezogenen Daten.
    - Antworte altersgerecht und nicht zu lang.
    - Gib keine Bewertung des Prompts ab. Das passiert später im Workshop.
    """

    user_input = f"""
    Workshop-Kategorie: {selected_task["level"]}
    Workshop-Titel: {selected_task["titel"]}
    Lernziel: {selected_task["lernziel"]}
    Aufgabe: {selected_task["aufgabe"]}

    Prompt der Schüler:innen:
    {student_prompt}

    Beantworte jetzt den Prompt der Schüler:innen so, als wärst du die KI, die getestet wird.
    """

    try:
        response = client.responses.create(
            model=model,
            instructions=system_prompt,
            input=user_input
        )

        return response.output_text

    except Exception as error:
        return f"Fehler bei der KI-Anfrage: {error}"

# Session-State vorbereiten
if "selected_task" not in st.session_state:
    st.session_state.selected_task = None

if "student_prompt" not in st.session_state:
    st.session_state.student_prompt = ""

if "ki_answer" not in st.session_state:
    st.session_state.ki_answer = ""

if "reflection" not in st.session_state:
    st.session_state.reflection = ""

# Überschrift
st.title("⚔️ Prompt Battle Arena")
st.write("Teste einen Prompt, reflektiere das Ergebnis und vergleiche ihn mit einem Experten-Prompt.")

# Aufgabe auswählen
st.header("1. Wählt eine Aufgabe")

task_options = {
    f"{task['farbe']} {task['level']}: {task['titel']}": task
    for task in tasks
}

selected_label = st.selectbox(
    "Welche Runde wollt ihr spielen?",
    list(task_options.keys())
)

selected_task = task_options[selected_label]
st.session_state.selected_task = selected_task

st.subheader(f"{selected_task['farbe']} {selected_task['titel']}")
st.write(f"**Lernziel:** {selected_task['lernziel']}")
st.info(selected_task["aufgabe"])

# Typischen Prompt anzeigen
with st.expander("Typischer Schüler:innen-Prompt anzeigen"):
    st.write(selected_task["typischer_prompt"])

# Prompt eingeben
st.header("2. Schreibt euren eigenen Prompt")

student_prompt = st.text_area(
    "Euer Prompt:",
    value=st.session_state.student_prompt,
    height=150,
    placeholder="Schreibt hier euren Prompt..."
)

st.session_state.student_prompt = student_prompt

# Noch keine echte KI: Platzhalterantwort
if st.button("Prompt testen"):
    if not student_prompt.strip():
        st.warning("Bitte schreibt zuerst einen Prompt.")
    else:
        with st.spinner("Die KI antwortet..."):
            st.session_state.ki_answer = generate_ai_answer(
                student_prompt,
                selected_task
            )

# Ergebnis anzeigen
if st.session_state.ki_answer:
    st.header("3. Ergebnis")
    st.write(st.session_state.ki_answer)

    st.header("4. Reflexion")
    st.session_state.reflection = st.text_area(
        "Was würdet ihr am Prompt verbessern?",
        value=st.session_state.reflection,
        height=120
    )

    st.header("5. Experten-Prompt")
    st.success(selected_task["experten_prompt"])

    st.header("6. Trick dahinter")
    st.write(selected_task["trick"])

# Reset
st.divider()

if st.button("Neue Runde starten"):
    st.session_state.selected_task = None
    st.session_state.student_prompt = ""
    st.session_state.ki_answer = ""
    st.session_state.reflection = ""
    st.rerun()

