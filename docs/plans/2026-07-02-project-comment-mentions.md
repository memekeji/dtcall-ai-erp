# Project Comment Mentions Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add `@` mentions to project-detail comments so users can mention project participants, send in-site notifications, sync the global unread badge, and show faster in-page reminders on the comment view.

**Architecture:** Keep the existing Django comment flow and extend it in place. Add a shared helper that computes the project participant scope, expose that scope through a comment mention-candidates endpoint, validate submitted `mentioned_user_ids` on comment creation, send notifications through the existing `MessageService`, and enhance the existing comment textarea UI in the project detail template with lightweight mention selection and comment-page polling.

**Tech Stack:** Django, Django REST Framework, existing `MessageService`, server-rendered template HTML, jQuery, axios, layui

---

### Task 1: Add tests for the project participant scope helper

**Files:**
- Modify: `apps/project/tests.py`
- Modify: `apps/project/views.py`
- Optional Create: `apps/project/comment_mentions.py`

**Step 1: Write the failing test**

Add a test that creates:

- a project manager
- a project member
- a task assignee
- a task participant

Then assert the computed mention candidate set for that project includes all four users exactly once.

**Step 2: Run test to verify it fails**

Run: `python manage.py test apps.project.tests.ProjectCommentMentionTests.test_project_comment_candidates_include_manager_members_assignees_and_participants`

Expected: FAIL because the helper does not exist yet or does not include the manager.

**Step 3: Write minimal implementation**

Implement a shared helper that returns the deduplicated allowed users for project comments.

**Step 4: Run test to verify it passes**

Run: `python manage.py test apps.project.tests.ProjectCommentMentionTests.test_project_comment_candidates_include_manager_members_assignees_and_participants`

Expected: PASS

**Step 5: Commit**

```bash
git add apps/project/tests.py apps/project/views.py
git commit -m "test: cover project comment mention candidate scope"
```

### Task 2: Add tests and endpoint for mention candidates

**Files:**
- Modify: `apps/project/tests.py`
- Modify: `apps/project/viewsets.py`
- Modify: `apps/project/api_urls.py`
- Optional Modify: `apps/project/serializers.py`

**Step 1: Write the failing test**

Add a test that requests the comment mention-candidates endpoint for a project and asserts:

- HTTP 200
- response includes manager, members, assignee, participants
- duplicate users appear once

**Step 2: Run test to verify it fails**

Run: `python manage.py test apps.project.tests.ProjectCommentMentionTests.test_comment_mention_candidates_endpoint_returns_deduped_project_participants`

Expected: FAIL because the route/action does not exist.

**Step 3: Write minimal implementation**

Add a DRF action on `CommentViewSet` that:

- validates the target object is a project
- loads allowed users through the helper
- returns the user payload needed by the textarea mention UI

**Step 4: Run test to verify it passes**

Run: `python manage.py test apps.project.tests.ProjectCommentMentionTests.test_comment_mention_candidates_endpoint_returns_deduped_project_participants`

Expected: PASS

**Step 5: Commit**

```bash
git add apps/project/tests.py apps/project/viewsets.py apps/project/api_urls.py
git commit -m "feat: add project comment mention candidates endpoint"
```

### Task 3: Add tests for mention notifications on comment creation

**Files:**
- Modify: `apps/project/tests.py`
- Modify: `apps/project/viewsets.py`
- Modify: `apps/project/serializers.py`
- Review: `apps/message/services.py`

**Step 1: Write the failing test**

Add tests that create a project comment with `mentioned_user_ids` and assert:

- allowed mentioned users get unread notification relations
- the comment author does not receive a mention notification
- users outside the allowed project scope do not receive one

Use real `Message` / `MessageUserRelation` rows instead of mocks.

**Step 2: Run test to verify it fails**

Run: `python manage.py test apps.project.tests.ProjectCommentMentionTests.test_creating_comment_notifies_only_allowed_mentions`

Expected: FAIL because mention IDs are ignored today.

**Step 3: Write minimal implementation**

Extend the comment create flow to:

- read `mentioned_user_ids`
- validate them against the project scope
- exclude `request.user.id`
- create the comment
- send mention notifications through `MessageService.send_notification(...)`

**Step 4: Run test to verify it passes**

Run: `python manage.py test apps.project.tests.ProjectCommentMentionTests.test_creating_comment_notifies_only_allowed_mentions`

Expected: PASS

**Step 5: Commit**

```bash
git add apps/project/tests.py apps/project/viewsets.py apps/project/serializers.py
git commit -m "feat: send notifications for project comment mentions"
```

### Task 4: Add tests for reply-plus-mention behavior

**Files:**
- Modify: `apps/project/tests.py`
- Modify: `apps/project/viewsets.py`

**Step 1: Write the failing test**

Add a test where a reply mentions another valid project participant and assert:

- the parent comment owner receives the reply notification
- the mentioned participant receives the mention notification
- the same user does not receive duplicate notifications for the same reason

**Step 2: Run test to verify it fails**

Run: `python manage.py test apps.project.tests.ProjectCommentMentionTests.test_reply_comment_sends_reply_and_mention_notifications`

Expected: FAIL because only reply notifications exist today.

**Step 3: Write minimal implementation**

Refine the notification flow so reply and mention notifications can coexist without sending duplicate mention notifications to the author or invalid recipients.

**Step 4: Run test to verify it passes**

Run: `python manage.py test apps.project.tests.ProjectCommentMentionTests.test_reply_comment_sends_reply_and_mention_notifications`

Expected: PASS

**Step 5: Commit**

```bash
git add apps/project/tests.py apps/project/viewsets.py
git commit -m "test: cover reply and mention notification interplay"
```

### Task 5: Add frontend mention selection to the project detail comment UI

**Files:**
- Modify: `templates/project/detail.html`

**Step 1: Write the failing test**

Add a template-focused server test that asserts the project detail page renders the containers and bootstrap data hooks needed for mention suggestions and in-page reminders.

**Step 2: Run test to verify it fails**

Run: `python manage.py test apps.project.tests.ProjectCommentMentionTests.test_project_detail_renders_comment_mention_bootstrap_hooks`

Expected: FAIL because the template does not expose those hooks yet.

**Step 3: Write minimal implementation**

Enhance the existing comment UI with:

- a reusable mention state object
- mention candidate loading
- `@` detection and suggestion rendering
- selection tracking for both root comments and replies
- safe content rendering helpers

**Step 4: Run test to verify it passes**

Run: `python manage.py test apps.project.tests.ProjectCommentMentionTests.test_project_detail_renders_comment_mention_bootstrap_hooks`

Expected: PASS

**Step 5: Commit**

```bash
git add apps/project/tests.py templates/project/detail.html
git commit -m "feat: add project detail comment mention UI"
```

### Task 6: Add in-page reminder polling for project comments

**Files:**
- Modify: `apps/project/tests.py`
- Modify: `apps/project/viewsets.py`
- Modify: `templates/project/detail.html`
- Review: `templates/home/base.html`

**Step 1: Write the failing test**

Add a backend test for a lightweight endpoint that returns whether the current user has newer unread project comment notifications for the current project.

**Step 2: Run test to verify it fails**

Run: `python manage.py test apps.project.tests.ProjectCommentMentionTests.test_project_comment_notification_poll_endpoint_returns_unread_state`

Expected: FAIL because the poll endpoint does not exist.

**Step 3: Write minimal implementation**

Add the endpoint and wire the project detail template to poll it when the comment tab is active, then:

- show a local reminder bubble
- refresh the global unread count using existing page helpers

**Step 4: Run test to verify it passes**

Run: `python manage.py test apps.project.tests.ProjectCommentMentionTests.test_project_comment_notification_poll_endpoint_returns_unread_state`

Expected: PASS

**Step 5: Commit**

```bash
git add apps/project/tests.py apps/project/viewsets.py templates/project/detail.html
git commit -m "feat: add project comment in-page reminders"
```

### Task 7: Run focused regression tests and clean up

**Files:**
- Modify: `apps/project/tests.py` if any test helper cleanup is needed
- Review: `apps/message/tests.py`

**Step 1: Run the focused test set**

Run: `python manage.py test apps.project.tests`

Expected: PASS with the new mention and notification coverage green.

**Step 2: Run any adjacent message tests if touched**

Run: `python manage.py test apps.message.tests`

Expected: PASS if message-side behavior was modified.

**Step 3: Refactor while staying green**

Remove duplication, tighten helper names, and keep the comment rendering safe.

**Step 4: Run tests again**

Run: `python manage.py test apps.project.tests`

Expected: PASS

**Step 5: Commit**

```bash
git add apps/project/tests.py apps/project/viewsets.py apps/project/serializers.py apps/project/views.py templates/project/detail.html
git commit -m "feat: complete project comment mentions"
```
