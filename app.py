import json
from openai import OpenAI
import re
import os
from dotenv import load_dotenv
import streamlit as st

load_dotenv()  # Load from .env file
clientGPT = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

with open("handbook_toc.json", encoding="utf-8") as f:
    toc = json.load(f)

with open("structured_handbook.json", encoding="utf-8") as f:
    handbook = json.load(f)

toc_string = "\n".join([i["section"] + " " + i["title"] for i in toc])

def initial_relevant_sections(user_question):
    system = "You're an assistant helping students find information in a college handbook."
    user = "Here is a table of contents from a student handbook: " + toc_string + " \nHere is the question from the user: \"" + user_question + "\". If this question is not relevant to any section of the handbook, please return this string \"NOT_RELEVANT\". Otherwise, return only a Python list of only the section numbers (e.g. [\"1.2.\", \"2.3.\", \"APPENDIX 1\"])."
    
    response = clientGPT.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user}
        ],
        temperature=0.2
    )

    try:
        if "NOT RELEVANT" in response or "NOT_RELEVANT"in response:
            return False
        output = eval(response.choices[0].message.content.strip())
        if isinstance(output, list):
            return output
    except:
        return False

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
    response = clientGPT.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "system", "content": system}, {"role": "user", "content": prompt}],
        temperature=0.2
    )
    return response.choices[0].message.content.strip()

#MAIN PROGRAM
st.set_page_config(page_title="Oriel Freshers Intelligent AI Chatbot", page_icon="💡")
st.title("Oriel Freshers Intelligent AI Chatbot")
st.write("Welcome to Oriel College. This is an AI system developed by the Oriel JCR Fresher's Rep to answer any questions you may have.")

st.write("Please enter your question below.")

question = st.text_input("Your Question:")

if question:
    if len(question) > 400:
        st.markdown("Maximum length of 400 characters exceeded")
    else:
        with st.spinner("Thinking..."):
            initial = initial_relevant_sections(question)
            if initial:
                sections = get_relevant_sections(initial)
                prompt = generate_prompt(question, sections)
                answer = get_rag_answer(prompt)
        
        if initial:
            st.subheader("📘 Answer")
            st.markdown(answer)
            st.caption("Disclaimer: The above response is AI generated and so there is a small chance that the response contains mistakes.")
        else:
            st.markdown("Unable to answer the question, please try again.")
