from __future__ import annotations

import re
from typing import Any

from app.models.schemas import CandidateProfile
from app.services.llm import LLMClient

SKILL_KEYWORDS = [
    "python", "java", "javascript", "typescript", "sql", "nosql", "aws", "azure", "gcp",
    "docker", "kubernetes", "machine learning", "data engineering", "etl", "spark",
    "active directory", "gpo", "group policy", "powershell", "bash", "shell script",
    "vmware", "vsphere", "hyper-v", "vdi", "citrix", "exchange", "office 365", "o365",
    "backup exec", "netbackup", "veeam", "vranger", "datadomain", "storsimple",
    "sccm", "sms", "tfs", "iis", "sharepoint", "apache", "nginx",
    "cisco", "asa", "firewall", "vpn", "dhcp", "dns", "tcp/ip", "lan/wan",
    "linux", "ubuntu", "redhat", "centos", "unix", "windows server",
    "mcafee", "symantec", "anti-virus", "security", "disaster recovery",
    "solarwinds", "cacti", "nmap", "zenmap", "wireshark",
    "html", "css", "xml", "json", "c++", "c#", ".net", "vb.net", "vbs", "visual basic",
    "t-sql", "mysql", "oracle", "postgre", "storage", "san/nas", "iscsi", "cloud"
]

EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
# Stricter phone regex to avoid matching version numbers or date ranges
PHONE_RE = re.compile(r"(\+?\d{1,3}[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4,6}")
YEARS_RE = re.compile(r"(\d+)(?:\+)?\s*(?:years?|yrs)\b")


def extract_profile(
    text: str, resume_id: str, llm: LLMClient | None, source: str | None = None
) -> CandidateProfile:
    base = _heuristic_extract(text)
    
    llm_data = {}
    if llm and llm.is_available():
        try:
            llm_data = _llm_extract(text, llm)
            base = _merge_profiles(base, llm_data)
        except Exception as e:
            print(f"LLM extraction error for {resume_id}: {e}")

    # Final cleanup of skills: deduplicate and title case
    final_skills = []
    seen = set()
    for s in base.get("skills", []):
        s_clean = s.strip().lower()
        if s_clean and s_clean not in seen:
            final_skills.append(s)
            seen.add(s_clean)
    base["skills"] = sorted(final_skills, key=lambda x: x.lower())

    base["resume_id"] = resume_id
    base["source"] = source
    
    # Use LLM years if available, otherwise fallback to heuristic
    llm_years = llm_data.get("years_experience")
    if isinstance(llm_years, (int, float)):
        base["years_experience"] = float(llm_years)
    else:
        base["years_experience"] = _infer_years_experience(text)
        
    base.setdefault("domain", "INFORMATION-TECHNOLOGY")
    return CandidateProfile(**base)


def _heuristic_extract(text: str) -> dict[str, Any]:
    email = _first_match(EMAIL_RE, text)
    phone = _first_match(PHONE_RE, text)
    
    # Validation for phone: if it's too short or contains suspicious patterns, null it
    if phone and (len(re.sub(r"\D", "", phone)) < 7 or "." in phone):
        phone = None

    name = _guess_name(text)
    skills = _extract_skills(text)
    return {
        "name": name,
        "email": email,
        "phone": phone,
        "skills": skills,
        "education": [],
        "experience": [],
        "current_role": None,
    }


def _llm_extract(text: str, llm: LLMClient) -> dict[str, Any]:
    # Increased snippet for better coverage.
    if len(text) <= 15000:
        snippet = text
    else:
        snippet = text[:9000] + "\n... [TRUNCATED MIDDLE] ...\n" + text[-6000:]
    
    # Today's date for relative calculations
    current_date = "Saturday, May 30, 2026"

    system = (
        "You are an expert HR Data Reconstructor. Your specialty is reading resume text "
        "and converting it into clean, highly structured JSON. The text might be messy due to PDF extraction."
    )
    prompt = (
        f"TODAY'S DATE: {current_date}\n\n"
        "TASK: Reconstruct the following resume text into a detailed structured JSON object.\n\n"
        "STRICT RULES:\n"
        "1. NAME: Extract the candidate's full name. If it looks like a job title or is missing, use null.\n"
        "2. CURRENT ROLE: Infer the current role from the most recent experience. Do NOT leave null if there is experience.\n"
        "3. EXPERIENCE DATES: 'Current' or 'Present' means May 2026. Ensure dates are REALISTIC (e.g., years 1990-2026). If a year like '1753' is found, it is an OCR error; look for the correct year nearby. If dates are missing for a role, use null but DO NOT skip the role.\n"
        "4. ALL ROLES: Extract EVERY job and role mentioned in the experience section. Do not skip any entry just because it is short or lacks detail.\n"
        "5. TOTAL YEARS OF EXPERIENCE: Calculate this by summing the durations of ALL professional roles.\n"
        "6. SKILLS: Extract EVERY technical skill, tool, software, and hardware mentioned. Be exhaustive.\n"
        "6. EDUCATION: List degrees, major, institution, and year. \n"
        "   - COURSEWORK: ONLY list items explicitly mentioned as coursework or specific classes. Do NOT split the 'Major' name into coursework.\n"
        "   - PROGRAMMING LANGUAGES: Separate specific languages (C++, Java) from general subjects.\n"
        "7. CERTIFICATIONS: List professional certifications. ALWAYS include the year/date if mentioned.\n"
        "8. HALLUCINATION CHECK: Do not invent data. If a field like 'phone' or 'email' is not in the text, use null.\n\n"
        "JSON SCHEMA:\n"
        "{\n"
        "  \"name\": \"string or null\",\n"
        "  \"phone\": \"string or null\",\n"
        "  \"email\": \"string or null\",\n"
        "  \"skills\": [\"string\"],\n"
        "  \"education\": [\n"
        "    {\n"
        "      \"degree\": \"string\",\n"
        "      \"major\": \"string\",\n"
        "      \"institution\": \"string\",\n"
        "      \"year\": 2005,\n"
        "      \"coursework\": [\"string\"],\n"
        "      \"programming_languages\": [\"string\"]\n"
        "    }\n"
        "  ],\n"
        "  \"experience\": [\n"
        "    {\"title\": \"string\", \"company\": \"string\", \"location\": \"string\", \"start_date\": \"string\", \"end_date\": \"string\", \"duration_years\": 2.5, \"highlights\": [\"string\"]}\n"
        "  ],\n"
        "  \"certifications\": [\"string\"],\n"
        "  \"current_role\": \"string\",\n"
        "  \"years_experience\": number,\n"
        "  \"domain\": \"string\"\n"
        "}\n\n"
        "RESUME TEXT:\n" + snippet
    )
    return llm.generate_json(prompt, system=system)


def _merge_profiles(base: dict[str, Any], incoming: dict[str, Any]) -> dict[str, Any]:
    merged = dict(base)
    for key, value in incoming.items():
        if value is None:
            continue
        if isinstance(value, list) and not value:
            continue
        if value == "" or (isinstance(value, str) and len(value) < 2):
            continue
        
        # Avoid anonymized placeholders or generic words
        if isinstance(value, str) and value.lower() in ["company name", "city", "state", "unknown", "resume", "curriculum vitae"]:
            continue
            
        # For name, be even stricter. If it's all caps and contains IT terms, it's a title.
        if key == "name":
            val_str = str(value)
            if base.get("name"):
                # If heuristic found something and LLM found something
                # Check if LLM output is actually a title
                if any(x in val_str.upper() for x in ["TECHNICIAN", "ENGINEER", "DEVELOPER", "MANAGER", "ANALYST", "SPECIALIST", "LIASON"]):
                    continue
                if val_str and " " in val_str:
                    merged[key] = val_str
                continue
            else:
                # Heuristic found nothing, check if LLM found a title instead of a name
                if any(x in val_str.upper() for x in ["TECHNICIAN", "ENGINEER", "DEVELOPER", "MANAGER", "ANALYST", "SPECIALIST", "LIASON"]):
                    merged[key] = None
                    continue

        if key == "skills" and isinstance(value, list):
            existing_skills = base.get("skills", [])
            combined = list(set(existing_skills + value))
            merged[key] = sorted(combined, key=lambda x: x.lower())
            continue

        merged[key] = value
    return merged


def _first_match(pattern: re.Pattern[str], text: str) -> str | None:
    match = pattern.search(text)
    return match.group(0) if match else None


def _guess_name(text: str) -> str | None:
    for line in text.splitlines()[:10]: # Only check first 10 lines
        clean = line.strip()
        if not clean:
            continue
        # Skip common headers, anonymized placeholders, and job titles
        lower_clean = clean.lower()
        if any(x in lower_clean for x in ["resume", "summary", "experience", "education", "company name", "city", "state", "technician", "engineer", "developer", "manager", "analyst"]):
            continue
        # Name should usually be 2-3 words
        words = clean.split()
        if 2 <= len(words) <= 4 and all(len(w) >= 2 for w in words) and any(char.isalpha() for char in clean):
            return clean
    return None


def _extract_skills(text: str) -> list[str]:
    lower = text.lower()
    skills = [skill for skill in SKILL_KEYWORDS if skill in lower]
    return sorted(set(skills))


def _infer_years_experience(text: str) -> float | None:
    matches = YEARS_RE.findall(text.lower())
    if not matches:
        return None
    values = [float(value) for value in matches]
    return max(values)

