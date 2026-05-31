from pydantic import BaseModel, Field


class Education(BaseModel):
    degree: str | None = None
    major: str | None = None
    institution: str | None = None
    year: int | str | None = None
    coursework: list[str] = Field(default_factory=list)
    programming_languages: list[str] = Field(default_factory=list)


class Experience(BaseModel):
    title: str | None = None
    company: str | None = None
    location: str | None = None
    start_date: str | None = None
    end_date: str | None = None
    duration_years: float | None = None
    highlights: list[str] = Field(default_factory=list)


class CandidateProfile(BaseModel):
    resume_id: str
    name: str | None = None
    email: str | None = None
    phone: str | None = None
    skills: list[str] = Field(default_factory=list)
    education: list[Education] = Field(default_factory=list)
    experience: list[Experience] = Field(default_factory=list)
    certifications: list[str] = Field(default_factory=list)
    current_role: str | None = None
    domain: str | None = "INFORMATION-TECHNOLOGY"
    years_experience: float | None = None
    source: str | None = None


class CandidateSummary(BaseModel):
    resume_id: str
    name: str | None = None
    current_role: str | None = None
    years_experience: float | None = None
    skills: list[str] = Field(default_factory=list)
    score: float | None = None
    evidence: str | None = None


class QueryRequest(BaseModel):
    query: str
    top_k: int = 5


class QueryResponse(BaseModel):
    answer: str
    candidates: list[CandidateSummary] = Field(default_factory=list)


class IngestResponse(BaseModel):
    status: str
    count: int | None = None
    message: str | None = None


class UploadResponse(BaseModel):
    status: str
    count: int | None = None
