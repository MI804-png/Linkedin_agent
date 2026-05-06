#!/usr/bin/env python3
"""Test skill extraction"""
import sys
sys.path.insert(0, r'd:\cv_portofolio\linkedin_bot')

from skill_extractor import extract_skills_from_text, get_user_skills, compare_skills
from config import CandidateProfile, BotSettings

# Test extraction
job_desc = "We are looking for a Python and JavaScript developer with React experience. Must know Docker, Kubernetes, and AWS. Strong communication skills required."

skills = extract_skills_from_text(job_desc)
print(f"Extracted skills: {skills}")

# Test user skills
profile = CandidateProfile()
settings = BotSettings()
user_skills = get_user_skills(profile, settings)
print(f"User skills: {user_skills}")

# Test comparison
comparison = compare_skills(set(skills), user_skills)
print(f"Missing skills: {comparison['missing']}")
print(f"Match percentage: {comparison['match_percentage']}")
