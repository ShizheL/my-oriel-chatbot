import json
from openai import OpenAI
import re
import os
from dotenv import load_dotenv
import streamlit as st

# ACCESS CHECK
ACCESS_CODES_FILE = "access_codes.json"

def load_access_codes():
    if not os.path.exists(ACCESS_CODES_FILE):
        return {}
    with open(ACCESS_CODES_FILE, "r") as f:
        return json.load(f)

def save_access_codes(data):
    with open(ACCESS_CODES_FILE, "w") as f:
        json.dump(data, f, indent=4)

access_data = load_access_codes()

if "access_granted" not in st.session_state:
    st.session_state.access_granted = False

if not st.session_state.access_granted:
    code = st.text_input("Enter your access code:")
    if st.button("Submit Code"):
        if code in access_data:
            st.session_state.access_code = code
            st.session_state.access_granted = True
            st.rerun()
        else:
            st.error("Invalid access code.")
    st.stop()

#MAIN PROGRAM
load_dotenv()  # Load from .env file

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

with open("handbook_toc.json", encoding="utf-8") as f:
    toc = json.load(f)

with open("structured_handbook.json", encoding="utf-8") as f:
    handbook = json.load(f)

toc_string = "\n".join([i["section"] + " " + i["title"] for i in toc])

def initial_relevant_sections(user_question):
    system = "You're an assistant helping students find information in a college handbook."
    user = "Here is a table of contents from a student handbook: " + toc_string + "\nPlease give me all the sections that are the most likely to contain the answer to this question: \"" + user_question + "\"\nReturn only a Python list of only the section numbers (e.g. [\"1.2.\", \"2.3.\", \"APPENDIX 1\"])."
    
    for _ in range(3):
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user}
            ],
            temperature=0.2
        )

        try:
            output = eval(response.choices[0].message.content.strip())
            if isinstance(output, list):
                return output
        except:
            pass

    print("Error: Could not parse GPT output.")
    return []

def get_question_code(s):
    s = s.lower()
    ans = ""
    i = 0
    if "appendix" in s:
        ans += "APPENDIX "

    s = s.replace("appendix", "").strip()

    while i < len(s) and (s[i].isdigit() or s[i] == "."):
        ans += s[i]
        i += 1
    return ans.strip()

def get_text(section):
    for i in handbook:
        if i["section"] == section:
            return i["text"]
    return False

def get_title(section):
    for i in handbook:
        if i["section"] == section:
            return i["title"]
    return False

def get_relevant_sections(initial_sections):
    queue = [get_question_code(i) for i in initial_sections]
    sections = set()

    while len(queue) > 0:
        sect = queue.pop(0)
        if sect in sections:
            continue
        txt = get_text(sect)
        if not txt:
            continue
        sections.add(sect)
        ref_sects = re.findall(r"\b(?:section|Section|SECTION|appendix|APPENDIX|Appendix)\s+[\d\.]+", txt)
        for i in ref_sects:
            if "section" in i.lower():
                queue.append(i.lower().replace("section", "").strip())
            else:
                queue.append("APPENDIX " + i.lower().replace("appendix", "").strip())
    return sections


def generate_prompt(question, sections):
    context = ""
    for section in sections:
        title = get_title(section)
        text = get_text(section)
        if (not title) or (not text):
            continue
        context += "Section " + section + " - " + title + ": "
        context += text + "\n"
    
    prompt = "You are answering the following question based on the provided background information about Oriel college.\n\n"
    prompt += "User question: " + question + "\n\n"
    prompt += "Context:\n" + context + "\n"
    return prompt

def main(question):
    initial = initial_relevant_sections(question)
    sections = get_relevant_sections(initial)
    return generate_prompt(question, sections)

def get_rag_answer(prompt):
    system = "You're an assistant helping to answer questions from new students at Oriel College."
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "system", "content": system}, {"role": "user", "content": prompt}],
        temperature=0.2
    )
    return response.choices[0].message.content.strip()

st.set_page_config(page_title="Oriel Freshers RAG Chatbot", page_icon="🦉")
st.title("Oriel College Freshers Chatbot")
st.write("Welcome to Oriel College. This is an AI system developed by Orielensis to answer any questions you may have. Please enter your question below.")

question = st.text_input("Your Question:")

code = st.session_state.access_code
current = access_data[code]["count"]
limit = access_data[code]["limit"]

if current >= limit:
    st.error("Query limit reached for this code.")
    st.stop()

if question:
    with st.spinner("Thinking..."):
        initial = initial_relevant_sections(question)
        sections = get_relevant_sections(initial)
        prompt = generate_prompt(question, sections)
        answer = get_rag_answer(prompt)

        used = access_data[code]["count"]
        limit = access_data[code]["limit"]
        remaining = limit - used
        st.caption(f"💬 You have used {used} of {limit} queries ({remaining} remaining).")

    access_data[code]["count"] += 1
    save_access_codes(access_data)
    
    st.subheader("📘 Answer")
    st.markdown(answer)

    with st.expander("🧩 Prompt Context (Debug)"):
        st.text(prompt)
