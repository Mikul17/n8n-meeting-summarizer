from typing import List

from pydantic import BaseModel


class JiraTask(BaseModel):
    task_name: str
    task_description: str
    assigned_to: str
    story_points: int


class JiraFeature(BaseModel):
    feature_name: str
    feature_description: str
    acceptance_criteria: str
    story_points: int
    assigned_to: str
    tasks: List[JiraTask]


class JiraBug(BaseModel):
    bug_name: str
    bug_description: str
    reproduction_steps: str
    story_points: int
    assigned_to: str


class JiraTaskRequest(BaseModel):
    summary: str
    features: List[JiraFeature]
    bugs: List[JiraBug]
