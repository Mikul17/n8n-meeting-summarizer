from typing import Dict, List, Union
import asyncio

from app.models.JiraTaskRequest import JiraTaskRequest, JiraFeature, JiraTask, JiraBug
from app.models.MeetingStatusResponse import MeetingState, MeetingStatus
from app.utils import get_logger

import os
import httpx

logger = get_logger("jira-service")

jira_ids = {
    "Miłosz": "712020:58b109dc-ae1a-4422-9466-70bed9c5b9e8",
    "Milosz": "712020:58b109dc-ae1a-4422-9466-70bed9c5b9e8",
    "Jakub": "712020:3b856f58-88ad-4f0d-abd1-7814f16f1f2c",
    "Kuba": "712020:3b856f58-88ad-4f0d-abd1-7814f16f1f2c"
}

issue_type = {"Story": "10001", "Sub-task": "10005", "Bug": "10004"}

SPACE_KEY = os.getenv("JIRA_SPACE_KEY")


async def jira_request(method: str, url: str = "/rest/api/3/issues", json: Union[Dict, None] = None) -> dict:
    base_url = os.getenv("JIRA_SERVICE_URL")
    email = os.getenv("JIRA_API_MAIL")
    token = os.getenv("JIRA_API_TOKEN")

    if not base_url or not email or not token:
        raise RuntimeError(
            "Missing Jira configuration (JIRA_BASE_URL / JIRA_EMAIL / JIRA_API_TOKEN)"
        )

    full_url = f"{base_url.rstrip('/')}{url}"

    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.request(
            method=method,
            url=full_url,
            auth=(email, token),
            headers={
                "Accept": "application/json",
                "Content-Type": "application/json",
            },
            json=json,
        )

    if response.status_code >= 400:
        logger.error(
            "Jira API error %s %s -> %s: %s",
            method,
            full_url,
            response.status_code,
            response.text,
        )
        response.raise_for_status()

    if response.text:
        return response.json()

    return {}


async def process_jira_response(
    active_sessions: Dict[str, MeetingState], meeting_id: str, request: JiraTaskRequest
):
    state = active_sessions.get(meeting_id)
    if state is None:
        raise RuntimeError(f"Meeting {meeting_id} does not exist")

    if state.status != MeetingStatus.TRANSCRIBED:
        raise RuntimeError(f"Attempted to process jira tickets without transcription")

    logger.info(f"Processing jira tickets for meeting {meeting_id}")

    if len(request.features) > 0:
        await create_jira_features(features=request.features)
    else:
        logger.info("No features to be created")

    if len(request.bugs) > 0:
        await create_jira_bugs(request.bugs)
    else:
        logger.info("No bugs to be created")

    logger.info("Finished processing jira tickets.")
    active_sessions[meeting_id].status = MeetingStatus.PROCESSED
    return None


async def create_subtask(task: JiraTask, parent_key: str):
    task_payload = {
        "fields": {
            "project": {"key": SPACE_KEY},
            "summary": task.task_name,
            "parent": {"key": parent_key},
            "issuetype": {"id": issue_type["Sub-task"]},
            "assignee": {"id": jira_ids[task.assigned_to]},
            "description": {
                "type": "doc",
                "version": 1,
                "content": [
                    {
                        "type": "paragraph",
                        "content": [{"type": "text", "text": task.task_description}],
                    }
                ],
            },
        }
    }

    account_id = jira_ids.get(task.assigned_to)
    if account_id:
        task_payload["fields"]["assignee"]: {"id": account_id}
    return await jira_request(method="POST", url="/rest/api/3/issue", json=task_payload)


async def create_single_feature(feature: JiraFeature):
    feature_payload = {
        "fields": {
            "project": {"key": SPACE_KEY},
            "summary": feature.feature_name,
            "issuetype": {"id": issue_type["Story"]},
            "description": {
                "type": "doc",
                "version": 1,
                "content": [
                    {
                        "type": "paragraph",
                        "content": [
                            {"type": "text", "text": feature.feature_description}
                        ],
                    },
                    {
                        "type": "paragraph",
                        "content": [{"type": "text", "text": "Acceptance criteria:"}],
                    },
                    {
                        "type": "paragraph",
                        "content": [
                            {"type": "text", "text": feature.acceptance_criteria}
                        ],
                    },
                ],
            },
        }
    }

    account_id = jira_ids.get(feature.assigned_to)
    if account_id:
        feature_payload["fields"]["assignee"]: {"id": account_id}
    else:
        logger.debug(
            f"Couldn't find member {feature.assigned_to} to assign task - leaving unassigned"
        )

    response = await jira_request(
        method="POST", url="/rest/api/3/issue", json=feature_payload
    )
    issue_key = response.get("key")

    if not issue_key:
        raise RuntimeError(
            f"Failed to create feature {feature.feature_name}: {response}"
        )

    if feature.tasks:
        await asyncio.gather(*(create_subtask(t, issue_key) for t in feature.tasks))

    logger.info(f"Created Jira feature {issue_key} with {len(feature.tasks)} sub-tasks")


async def create_single_bug(bug: JiraBug):
    bug_payload = {
        "fields": {
            "project": {"key": SPACE_KEY},
            "summary": bug.bug_name,
            "issuetype": {"id": issue_type["Bug"]},
            "description": {
                "type": "doc",
                "version": 1,
                "content": [
                    {
                        "type": "paragraph",
                        "content": [{"type": "text", "text": bug.bug_description}],
                    },
                    {
                        "type": "paragraph",
                        "content": [{"type": "text", "text": "Reproduction steps:"}],
                    },
                    {
                        "type": "paragraph",
                        "content": [{"type": "text", "text": bug.reproduction_steps}],
                    },
                ],
            },
        }
    }

    account_id = jira_ids.get(bug.assigned_to)
    if account_id:
        bug_payload["fields"]["assignee"]: {"id": account_id}
    else:
        logger.debug(
            f"Couldn't find member {bug.assigned_to} to assign bug - leaving unassigned"
        )

    response = await jira_request(
        method="POST", json=bug_payload
    )
    issue_key = response.get("key")

    if not issue_key:
        raise RuntimeError(f"Failed to create bug {bug.bug_name}: {response}")


async def create_jira_features(features: List[JiraFeature]) -> None:
    logger.info(f"Processing jira [{len(features)}] features ")
    await asyncio.gather(*(create_single_feature(f) for f in features))
    logger.info(f"Finished processing jira features ")
    return None


async def create_jira_bugs(bugs: List[JiraBug]) -> None:
    logger.info(f"Processing jira [{len(bugs)}] bugs ")
    await asyncio.gather(*(create_single_bug(b) for b in bugs))
    logger.info(f"Processing jira [{len(bugs)}] bugs ")
    return None
