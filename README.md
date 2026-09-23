# Prompt Battle – KI-Literacy Workshop

## Start lokal

python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

Dann:

cp .streamlit/secrets.toml.example .streamlit/secrets.toml

In `.streamlit/secrets.toml` den echten OpenAI API-Key eintragen.

Start:

streamlit run app.py

## Wichtig

`.streamlit/secrets.toml` ist in `.gitignore` und darf nicht zu GitHub gepusht werden.