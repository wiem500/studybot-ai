import os
import json
import re
import streamlit as st
from groq import Groq
from dotenv import load_dotenv

load_dotenv()

# ─── Setup ───────────────────────────────────────────────────
api_key = os.getenv("GROQ_API_KEY", "")

st.set_page_config(page_title="StudyBot AI", page_icon="📚", layout="wide")
st.title("📚 StudyBot AI")

# ─── Sidebar ─────────────────────────────────────────────────
st.sidebar.title("⚙️ Configuration")

if not api_key:
    api_key = st.sidebar.text_input("🔑 Groq API Key", type="password")

COURSES = [
    "Machine Learning", "Réseaux de neurones", "NLP & Transformers",
    "Vision par ordinateur", "Statistiques & Probabilités",
    "Algorithmique", "Base de données", "Systèmes d'exploitation",
]

course = st.sidebar.selectbox("📖 Cours actuel", COURSES)
mode   = st.sidebar.radio("🧭 Mode", ["💬 Chat", "📝 Examen"])

if st.sidebar.button("🗑️ Effacer le chat"):
    st.session_state.messages = []
    st.rerun()

# ─── Session state ────────────────────────────────────────────
if "messages"       not in st.session_state: st.session_state.messages = []
if "exam_questions" not in st.session_state: st.session_state.exam_questions = []
if "exam_answers"   not in st.session_state: st.session_state.exam_answers = {}
if "exam_done"      not in st.session_state: st.session_state.exam_done = False
if "exam_score"     not in st.session_state: st.session_state.exam_score = 0

# ─── Groq client ─────────────────────────────────────────────
if not api_key:
    st.warning("⚠️ Entre ta clé Groq dans la sidebar.")
    st.stop()

client = Groq(api_key=api_key)

# ─── Functions ────────────────────────────────────────────────
def chat(user_message):
    system = f"""Tu es un assistant pédagogique expert en "{course}".
Réponds en français, de façon claire et structurée avec des exemples.
Utilise le markdown (gras, listes, code si besoin). Maximum 4 paragraphes."""

    payload = [{"role": "system", "content": system}]
    payload += st.session_state.messages
    payload.append({"role": "user", "content": user_message})

    response = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=payload,
        temperature=0.7,
        max_tokens=1024,
    )
    return response.choices[0].message.content


def generate_questions():
    prompt = f"""Génère 5 questions QCM sur "{course}".
Réponds UNIQUEMENT avec un tableau JSON valide, aucun texte avant ou après, pas de markdown.

[
  {{
    "question": "...",
    "options": ["A) ...", "B) ...", "C) ...", "D) ..."],
    "correct": 0,
    "explanation": "..."
  }}
]"""
    response = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.4,
        max_tokens=1500,
    )
    raw = response.choices[0].message.content.strip()

    # Nettoyage : retire tout ce qui n'est pas le tableau JSON
    raw = re.sub(r"```json|```", "", raw).strip()

    # Trouve le tableau JSON même s'il y a du texte autour
    match = re.search(r'\[.*\]', raw, re.DOTALL)
    if match:
        raw = match.group(0)

    return json.loads(raw)
# ══════════════════════════════════════════════════════════════
# MODE CHAT
# ══════════════════════════════════════════════════════════════
if mode == "💬 Chat":
    st.caption(f"Cours actuel : **{course}**")
    st.divider()

    # Show history
    for msg in st.session_state.messages:
        avatar = "👤" if msg["role"] == "user" else "🤖"
        with st.chat_message(msg["role"], avatar=avatar):
            st.markdown(msg["content"])

    # Input
    user_input = st.chat_input(f"Posez votre question sur {course}...")
    if user_input:
        with st.chat_message("user", avatar="👤"):
            st.markdown(user_input)
        st.session_state.messages.append({"role": "user", "content": user_input})

        with st.chat_message("assistant", avatar="🤖"):
            with st.spinner("Réflexion..."):
                reply = chat(user_input)
            st.markdown(reply)
        st.session_state.messages.append({"role": "assistant", "content": reply})


# ══════════════════════════════════════════════════════════════
# MODE EXAMEN
# ══════════════════════════════════════════════════════════════
elif mode == "📝 Examen":
    st.caption(f"Examen sur : **{course}**")
    st.divider()

    if not st.session_state.exam_questions:
        st.info("🤖 Cliquez pour générer 5 questions sur ce cours.")
        if st.button("🚀 Générer l'examen", type="primary"):
            with st.spinner("Génération des questions en cours..."):
                try:
                    questions = generate_questions()
                    st.session_state.exam_questions = questions
                    st.session_state.exam_answers = {}
                    st.session_state.exam_done = False
                    st.session_state.exam_score = 0
                    st.success(f"✅ {len(questions)} questions générées !")
                except Exception as e:
                    st.error(f"❌ Erreur : {e}")
                    st.write("Raw response pour debug :")
                    st.code(str(e))
            st.rerun()

    else:
        questions = st.session_state.exam_questions
        total     = len(questions)
        answered  = len(st.session_state.exam_answers)

        st.progress(answered / total, text=f"{answered}/{total} questions répondues")

        # Score final
        if st.session_state.exam_done:
            score = st.session_state.exam_score
            pct   = score / total
            emoji = "🏆" if pct >= 0.8 else "🎉" if pct >= 0.6 else "💪" if pct >= 0.4 else "📖"
            st.success(f"{emoji} Score final : **{score}/{total}**")

            col1, col2 = st.columns(2)
            with col1:
                if st.button("🔄 Nouvel examen", type="primary"):
                    st.session_state.exam_questions = []
                    st.session_state.exam_answers   = {}
                    st.session_state.exam_done      = False
                    st.rerun()
            with col2:
                if st.button("💬 Retour au chat"):
                    st.session_state.exam_questions = []
                    st.rerun()
            st.divider()

        # Questions
        for i, q in enumerate(questions):
            st.markdown(f"**Question {i+1} / {total}**")
            st.markdown(f"#### {q['question']}")

            if i not in st.session_state.exam_answers:
                for j, option in enumerate(q["options"]):
                    if st.button(option, key=f"q{i}_o{j}"):
                        st.session_state.exam_answers[i] = j
                        if len(st.session_state.exam_answers) == total:
                            st.session_state.exam_score = sum(
                                1 for idx, ans in st.session_state.exam_answers.items()
                                if ans == questions[idx]["correct"]
                            )
                            st.session_state.exam_done = True
                        st.rerun()
            else:
                user_ans    = st.session_state.exam_answers[i]
                correct_ans = q["correct"]
                for j, option in enumerate(q["options"]):
                    if j == correct_ans:
                        st.success(f"✅ {option}")
                    elif j == user_ans and user_ans != correct_ans:
                        st.error(f"❌ {option}")
                    else:
                        st.write(f"　{option}")
                st.info(f"💡 {q['explanation']}")

            st.divider()