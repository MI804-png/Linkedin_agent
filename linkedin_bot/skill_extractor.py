"""Extract and compare skills from job postings."""

import re
from typing import Set, List

# Common tech skills to recognize
TECH_SKILLS = {
    # Languages
    "python", "javascript", "java", "c#", "c++", "go", "rust", "php", "ruby", "swift", "kotlin",
    "typescript", "c", "scala", "perl", "r", "matlab", "groovy", "julia", "dart",
    # Web frameworks
    "react", "angular", "vue", "svelte", "next.js", "nuxt", "express", "django", "flask",
    "fastapi", "spring", "spring boot", "rails", "laravel", "asp.net", "asp.net core",
    # Databases
    "sql", "mysql", "postgresql", "mongodb", "redis", "elasticsearch", "cassandra", "dynamodb",
    "firebase", "cosmos db", "mariadb", "oracle", "sqlite", "neo4j", "memcached",
    # Cloud & DevOps
    "aws", "azure", "gcp", "google cloud", "docker", "kubernetes", "jenkins", "gitlab", "github",
    "terraform", "ansible", "ci/cd", "git", "svn", "devops", "cloudformation", "helm",
    # Data & ML
    "machine learning", "deep learning", "tensorflow", "pytorch", "scikit-learn", "pandas", "numpy",
    "spark", "hadoop", "data engineering", "etl", "data analysis", "statistics", "nlp", "computer vision",
    # Other tools & concepts
    "rest api", "graphql", "microservices", "serverless", "agile", "scrum", "jira", "confluence",
    "linux", "windows", "macos", "unix", "bash", "shell", "powershell", "html", "css", "json",
    "xml", "yaml", "regex", "testing", "unittest", "pytest", "mocha", "jest", "selenium",
    "git", "svn", "api", "rest", "soap", "grpc", "websocket", "oauth", "jwt", "security",
    "owasp", "encryption", "ssl/tls", "https", "cors", "authentication", "authorization",
}

# Soft skills and common job requirements
SOFT_SKILLS = {
    "communication", "leadership", "teamwork", "problem solving", "critical thinking",
    "time management", "project management", "attention to detail", "analytical",
    "documentation", "mentoring", "presentation", "negotiation", "stakeholder management",
}

WORK_REQUIREMENTS = {
    "remote", "on-site", "hybrid", "flexible", "part-time", "full-time", "contract",
    "temporary", "permanent", "internship", "graduate", "entry-level", "mid-level",
    "senior", "lead", "manager", "director", "architect", "consultant", "freelance",
}


SHORT_SKILL_PATTERNS = {
    "r": (
        r"\br language\b",
        r"\br programming\b",
        r"\bprogramming in r\b",
        r"\busing r\b",
        r"\bwith r\b",
        r"\br/shiny\b",
        r"\br studio\b",
        r"\brstudio\b",
    ),
    "c": (
        r"\bc language\b",
        r"\bc programming\b",
        r"\bprogramming in c\b",
        r"\bwith c\b",
        r"\bc/c\+\+\b",
        r"\bc and c\+\+\b",
        r"\bc developer\b",
    ),
}


def _text_mentions_skill(text_clean: str, skill: str) -> bool:
    if not text_clean or not skill:
        return False

    if skill in SHORT_SKILL_PATTERNS:
        return any(re.search(pattern, text_clean) for pattern in SHORT_SKILL_PATTERNS[skill])

    pattern = r"\b" + re.escape(skill) + r"\b"
    return bool(re.search(pattern, text_clean))


def extract_skills_from_text(text: str) -> List[str]:
    """
    Extract recognized skills from job description text.
    
    Returns a list of skills found in the text, sorted by frequency/prominence.
    """
    if not text:
        return []
    
    text_lower = text.lower()
    # Remove extra whitespace and special characters
    text_clean = re.sub(r"[^\w\s/\+\-\#\.@]", " ", text_lower)
    
    found_skills = set()
    
    # Look for tech skills. Single-letter languages like R/C need explicit context
    # so plain text such as "R&D" or "Computer Science" does not become a fake skill.
    for skill in TECH_SKILLS:
        if _text_mentions_skill(text_clean, skill):
            found_skills.add(skill)
    
    # Look for soft skills
    for skill in SOFT_SKILLS:
        pattern = r"\b" + re.escape(skill) + r"\b"
        if re.search(pattern, text_clean):
            found_skills.add(skill)
    
    return sorted(list(found_skills))


def compare_skills(job_skills: Set[str], user_skills: Set[str]) -> dict:
    """
    Compare job requirements against user's skills.
    
    Returns:
    {
        "missing": [...],  # Skills needed for job but not on user profile
        "match": [...],    # Skills user has that match job requirements
        "match_percentage": 0.0-1.0
    }
    """
    job_skills_lower = {s.lower() for s in job_skills}
    user_skills_lower = {s.lower() for s in user_skills}
    
    missing = job_skills_lower - user_skills_lower
    matched = job_skills_lower & user_skills_lower
    
    match_pct = len(matched) / len(job_skills_lower) if job_skills_lower else 0.0
    
    return {
        "missing": sorted(list(missing)),
        "matched": sorted(list(matched)),
        "match_percentage": round(match_pct, 2),
    }


def get_user_skills(profile, settings=None, cv_text: str | None = None) -> Set[str]:
    """
    Extract skills from user profile.
    Includes keywords, languages, and other profile data.
    
    Args:
        profile: CandidateProfile object or similar
        settings: Optional BotSettings object to extract keywords from
        cv_text: Optional extracted CV text used as the primary experience-backed
            skill source for comparison.
    """
    skills = set()
    
    # Keywords from settings
    if settings and hasattr(settings, 'keywords') and settings.keywords:
        for kw in settings.keywords:
            kw_lower = kw.lower().strip()
            if kw_lower:
                skills.add(kw_lower)
    
    # Languages
    if hasattr(profile, 'languages_spoken') and profile.languages_spoken:
        for lang in profile.languages_spoken.split(","):
            lang = lang.strip().lower()
            if lang:
                skills.add(lang)
    
    # Job title
    if hasattr(profile, 'current_job_title') and profile.current_job_title:
        title_lower = profile.current_job_title.lower()
        skills.update(extract_skills_from_text(title_lower))
    
    # Field of study
    if hasattr(profile, 'field_of_study') and profile.field_of_study:
        field_lower = profile.field_of_study.lower()
        skills.update(extract_skills_from_text(field_lower))
        for skill in SOFT_SKILLS:
            if _text_mentions_skill(field_lower, skill):
                skills.add(skill)

    # CV text is the strongest evidence for which skills are actually represented
    # in the candidate's documented experience.
    if cv_text:
        skills.update(extract_skills_from_text(str(cv_text)))
    
    return {s.lower() for s in skills}
