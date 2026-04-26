from pydantic import BaseModel


class Job(BaseModel):
    site: str
    title: str
    company: str
    location: str
    experience: str
    url: str
    tags: str
