# utils.py
import re
from email_validator import validate_email, EmailNotValidError
from llama_cpp import Llama

EMAIL_CANDIDATE_REGEX = r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+"
_llm = None

PRIORITY_KEYWORDS = ["hr", "risorse", "human", "info", "lavoro"]

from email_validator import validate_email, EmailNotValidError

def clean_valid_emails(emails):
    valid_emails = []
    pec_keywords = ["pec", "postacert", "legalmail", ".gov", ".giustizia"]
    for e in emails:
        try:
            valid = validate_email(e, check_deliverability=False)
            email = valid.email.lower()

            domain = email.split("@")[1]
            ext = domain.split(".")[-1]

            if any(k in email for k in pec_keywords):
                continue
            if email.startswith(tuple("0123456789")):
                continue
            if ext not in ["com", "it", "gov", "net", "org", "info", "edu", "mil", "ru", "cn", "uk", "io", "int", "mobi", "biz", "fr", "de", "xyz", "sale", "career"]:
                continue

            valid_emails.append(email)
        except EmailNotValidError:
            continue
    return list(set(valid_emails))

def get_llm():
    global _llm
    if _llm is None:
        _llm = Llama(model_path="models/mistral-7b-instruct-v0.1.Q4_K_M.gguf", n_ctx=2048, n_threads=4)
    return _llm
