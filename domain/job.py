import hashlib

from pydantic import BaseModel


def make_job_id(job: dict) -> str:
    key = f"{job.get('site', '')}{job.get('company', '')}{job.get('title', '')}"
    return hashlib.md5(key.encode()).hexdigest()[:8]


class Job(BaseModel):
    site: str
    title: str
    company: str
    location: str
    experience: str
    url: str
    tags: str
