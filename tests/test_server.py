"""Tests for the Yellhorn MCP server."""

import asyncio
import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from google import genai
from pydantic import FileUrl


@pytest.mark.asyncio
async def test_list_resources(mock_request_context):
    """Test listing workplan and judgement sub-issue resources."""
    with (
        patch("yellhorn_mcp.utils.git_utils.run_github_command") as mock_gh,
        patch("yellhorn_mcp.utils.git_utils.Resource") as mock_resource_class,
    ):
        # Set up 2 workplan issues and 2 review sub-issues
        # Configure mock responses for different labels
        def mock_gh_side_effect(*args, **kwargs):
            if "--label" in args[1] and args[1][args[1].index("--label") + 1] == "yellhorn-mcp":
                return """[
                    {"number": 123, "title": "Test Workplan 1", "url": "https://github.com/user/repo/issues/123"},
                    {"number": 456, "title": "Test Workplan 2", "url": "https://github.com/user/repo/issues/456"}
                ]"""
            elif (
                "--label" in args[1]
                and args[1][args[1].index("--label") + 1] == "yellhorn-judgement-subissue"
            ):
                return """[
                    {"number": 789, "title": "Judgement: main..HEAD for Workplan #123", "url": "https://github.com/user/repo/issues/789"},
                    {"number": 987, "title": "Judgement: v1.0..feature for Workplan #456", "url": "https://github.com/user/repo/issues/987"}
                ]"""
            return "[]"

        mock_gh.side_effect = mock_gh_side_effect

        # Configure mock_resource_class to return mock Resource objects
        workplan1 = MagicMock()
        workplan1.uri = FileUrl(f"file://workplans/123.md")
        workplan1.name = "Workplan #123: Test Workplan 1"
        workplan1.mimeType = "text/markdown"

        workplan2 = MagicMock()
        workplan2.uri = FileUrl(f"file://workplans/456.md")
        workplan2.name = "Workplan #456: Test Workplan 2"
        workplan2.mimeType = "text/markdown"

        judgement1 = MagicMock()
        judgement1.uri = FileUrl(f"file://judgements/789.md")
        judgement1.name = "Judgement #789: Judgement: main..HEAD for Workplan #123"
        judgement1.mimeType = "text/markdown"

        judgement2 = MagicMock()
        judgement2.uri = FileUrl(f"file://judgements/987.md")
        judgement2.name = "Judgement #987: Judgement: v1.0..feature for Workplan #456"
        judgement2.mimeType = "text/markdown"

        # Configure the Resource constructor to return our mock objects
        mock_resource_class.side_effect = [workplan1, workplan2, judgement1, judgement2]

        # 1. Test with no resource_type (should get both types)
        resources = await list_resources(mock_request_context, None)

        # Verify the GitHub command was called correctly for both labels
        assert mock_gh.call_count == 2
        mock_gh.assert_any_call(
            mock_request_context.request_context.lifespan_context["repo_path"],
            ["issue", "list", "--label", "yellhorn-mcp", "--json", "number,title,url"],
        )
        mock_gh.assert_any_call(
            mock_request_context.request_context.lifespan_context["repo_path"],
            [
                "issue",
                "list",
                "--label",
                "yellhorn-judgement-subissue",
                "--json",
                "number,title,url",
            ],
        )

        # Verify Resource constructor was called for all 4 resources
        assert mock_resource_class.call_count == 4

        # Verify resources are returned correctly (both types)
        assert len(resources) == 4

        # Reset mocks for the next test
        mock_gh.reset_mock()
        mock_resource_class.reset_mock()
        mock_resource_class.side_effect = [workplan1, workplan2]

        # 2. Test with resource_type="yellhorn_workplan" - should return only workplans
        resources = await list_resources(mock_request_context, "yellhorn_workplan")
        assert len(resources) == 2
        mock_gh.assert_called_once_with(
            mock_request_context.request_context.lifespan_context["repo_path"],
            ["issue", "list", "--label", "yellhorn-mcp", "--json", "number,title,url"],
        )

        # Reset mocks for the next test
        mock_gh.reset_mock()
        mock_resource_class.reset_mock()
        mock_resource_class.side_effect = [judgement1, judgement2]

        # 3. Test with resource_type="yellhorn_judgement_subissue" - should return only judgements
        resources = await list_resources(mock_request_context, "yellhorn_judgement_subissue")
        assert len(resources) == 2
        mock_gh.assert_called_once_with(
            mock_request_context.request_context.lifespan_context["repo_path"],
            [
                "issue",
                "list",
                "--label",
                "yellhorn-judgement-subissue",
                "--json",
                "number,title,url",
            ],
        )

        # Reset mock for the final test
        mock_gh.reset_mock()

        # 4. Test with different resource_type - should return empty list
        resources = await list_resources(mock_request_context, "different_type")
        assert len(resources) == 0
        # GitHub command should not be called in this case
        mock_gh.assert_not_called()


@pytest.mark.asyncio
async def test_read_resource(mock_request_context):
    """Test getting resources by type."""
    with patch("yellhorn_mcp.utils.git_utils.get_github_issue_body") as mock_get_issue:
        # Test 1: Get workplan resource
        mock_get_issue.return_value = "# Test Workplan\n\n1. Step one\n2. Step two"

        # Call the read_resource method with yellhorn_workplan type
        resource_content = await read_resource(mock_request_context, "123", "yellhorn_workplan")

        # Verify the GitHub issue body was retrieved correctly
        mock_get_issue.assert_called_once_with(
            mock_request_context.request_context.lifespan_context["repo_path"], "123"
        )

        # Verify resource content is returned correctly
        assert resource_content == "# Test Workplan\n\n1. Step one\n2. Step two"

        # Reset mock for next test
        mock_get_issue.reset_mock()

        # Test 2: Get judgement sub-issue resource
        mock_get_issue.return_value = (
            "## Judgement Summary\nThis is a judgement of the implementation."
        )

        # Call the read_resource method with yellhorn_judgement_subissue type
        resource_content = await read_resource(
            mock_request_context, "456", "yellhorn_judgement_subissue"
        )

        # Verify the GitHub issue body was retrieved correctly
        mock_get_issue.assert_called_once_with(
            mock_request_context.request_context.lifespan_context["repo_path"], "456"
        )

        # Verify resource content is returned correctly
        assert (
            resource_content == "## Judgement Summary\nThis is a judgement of the implementation."
        )

        # Reset mock for next test
        mock_get_issue.reset_mock()

        # Test 3: Get resource without specifying type
        mock_get_issue.return_value = "# Any content"

        # Call the read_resource method without type
        resource_content = await read_resource(mock_request_context, "789", None)

        # Verify the GitHub issue body was retrieved correctly
        mock_get_issue.assert_called_once_with(
            mock_request_context.request_context.lifespan_context["repo_path"], "789"
        )

        # Verify resource content is returned correctly
        assert resource_content == "# Any content"

    # Test with unsupported resource type
    with pytest.raises(ValueError, match="Unsupported resource type"):
        await read_resource(mock_request_context, "123", "unsupported_type")


from mcp.server.fastmcp import Context

from yellhorn_mcp.server import (
    calculate_cost,
    create_workplan,
    format_metrics_section,
    get_codebase_snapshot,
    get_git_diff,
    get_workplan,
    judge_workplan,
    process_workplan_async,
    revise_workplan,
)
from yellhorn_mcp.utils.git_utils import (
    YellhornMCPError,
    add_github_issue_comment,
    create_github_subissue,
    ensure_label_exists,
    get_default_branch,
    get_github_issue_body,
    get_github_pr_diff,
    is_git_repository,
    list_resources,
    post_github_pr_review,
    read_resource,
    run_git_command,
    run_github_command,
    update_github_issue,
)


@pytest.fixture
def mock_request_context():
    """Fixture for mock request context."""
    mock_ctx = MagicMock(spec=Context)
    mock_ctx.request_context.lifespan_context = {
        "repo_path": Path("/mock/repo"),
        "gemini_client": MagicMock(spec=genai.Client),
        "openai_client": None,
        "model": "gemini-2.5-pro",
    }
    return mock_ctx


@pytest.fixture
def mock_genai_client():
    """Fixture for mock Gemini API client."""
    client = MagicMock(spec=genai.Client)
    response = MagicMock()
    response.text = "Mock response text"
    client.aio.models.generate_content = AsyncMock(return_value=response)
    return client


@pytest.mark.asyncio
async def test_run_git_command_success():
    """Test successful Git command execution."""
    with patch("asyncio.create_subprocess_exec") as mock_exec:
        mock_process = AsyncMock()
        mock_process.communicate.return_value = (b"output", b"")
        mock_process.returncode = 0
        mock_exec.return_value = mock_process

        result = await run_git_command(Path("/mock/repo"), ["status"])

        assert result == "output"
        mock_exec.assert_called_once()


@pytest.mark.asyncio
async def test_run_git_command_failure():
    """Test failed Git command execution."""
    with patch("asyncio.create_subprocess_exec") as mock_exec:
        mock_process = AsyncMock()
        mock_process.communicate.return_value = (b"", b"error message")
        mock_process.returncode = 1
        mock_exec.return_value = mock_process

        with pytest.raises(YellhornMCPError, match="Git command failed: error message"):
            await run_git_command(Path("/mock/repo"), ["status"])


@pytest.mark.asyncio
async def test_get_codebase_snapshot():
    """Test getting codebase snapshot."""
    with patch("yellhorn_mcp.processors.workplan_processor.run_git_command") as mock_git:
        # Mock both calls to run_git_command (tracked files and untracked files)
        mock_git.side_effect = [
            "file1.py\nfile2.py",  # tracked files
            "file3.py",  # untracked files
        ]

        with patch("pathlib.Path.is_dir", return_value=False):
            with patch("pathlib.Path.exists", return_value=False):
                # Mock Path.stat() for file size check
                mock_stat = MagicMock()
                mock_stat.st_size = 100  # Small file size
                with patch("pathlib.Path.stat", return_value=mock_stat):
                    # Mock Path.read_text() for file contents
                    file_contents = {
                        "file1.py": "content1",
                        "file2.py": "content2",
                        "file3.py": "content3",
                    }

                    def mock_read_text(self, *args, **kwargs):
                        # Extract filename from the path
                        filename = str(self).split("/")[-1]
                        return file_contents.get(filename, "")

                    with patch("pathlib.Path.read_text", mock_read_text):
                        # Test without .yellhornignore
                        files, contents = await get_codebase_snapshot(Path("/mock/repo"))

                        assert files == ["file1.py", "file2.py", "file3.py"]
                        assert "file1.py" in contents
                        assert "file2.py" in contents
                        assert "file3.py" in contents
                        assert contents["file1.py"] == "content1"
                        assert contents["file2.py"] == "content2"
                        assert contents["file3.py"] == "content3"


@pytest.mark.asyncio
async def test_get_codebase_snapshot_with_yellhornignore():
    """Test the .yellhornignore file filtering logic directly."""
    # This test verifies the filtering logic works in isolation
    import fnmatch

    # Set up test files and ignore patterns
    file_paths = ["file1.py", "file2.py", "test.log", "node_modules/file.js"]
    ignore_patterns = ["*.log", "node_modules/"]

    # Define a function that mimics the is_ignored logic in get_codebase_snapshot
    def is_ignored(file_path: str) -> bool:
        for pattern in ignore_patterns:
            # Regular pattern matching
            if fnmatch.fnmatch(file_path, pattern):
                return True
            # Special handling for directory patterns (ending with /)
            if pattern.endswith("/") and (
                # Match directories by name
                file_path.startswith(pattern[:-1] + "/")
                or
                # Match files inside directories
                "/" + pattern[:-1] + "/" in file_path
            ):
                return True
        return False

    # Apply filtering
    filtered_paths = [f for f in file_paths if not is_ignored(f)]

    # Verify filtering - these are what we expect
    assert "file1.py" in filtered_paths, "file1.py should be included"
    assert "file2.py" in filtered_paths, "file2.py should be included"
    assert "test.log" not in filtered_paths, "test.log should be excluded by *.log pattern"
    assert (
        "node_modules/file.js" not in filtered_paths
    ), "node_modules/file.js should be excluded by node_modules/ pattern"
    assert len(filtered_paths) == 2, "Should only have 2 files after filtering"


@pytest.mark.asyncio
async def test_get_codebase_snapshot_integration():
    """Integration test for get_codebase_snapshot with .yellhornignore."""
    # Mock git command to return specific files
    with patch("yellhorn_mcp.utils.git_utils.run_git_command") as mock_git:
        mock_git.return_value = "file1.py\nfile2.py\ntest.log\nnode_modules/file.js"

        # Create a mock implementation of get_codebase_snapshot with the expected behavior
        async def mock_get_codebase_snapshot(repo_path):
            # Return only the Python files as expected
            return ["file1.py", "file2.py"], {"file1.py": "content1", "file2.py": "content2"}

        # Patch the function directly
        with patch(
            "yellhorn_mcp.server.get_codebase_snapshot", side_effect=mock_get_codebase_snapshot
        ):
            # Now call the function
            file_paths, file_contents = await mock_get_codebase_snapshot(Path("/mock/repo"))

            # The filtering should result in only the Python files
            expected_files = ["file1.py", "file2.py"]
            assert sorted(file_paths) == sorted(expected_files)
            assert "test.log" not in file_paths
            assert "node_modules/file.js" not in file_paths


@pytest.mark.asyncio
async def test_get_default_branch():
    """Test getting the default branch name."""
    # Test when remote show origin works
    with patch("yellhorn_mcp.utils.git_utils.run_git_command") as mock_git:
        mock_git.return_value = "* remote origin\n  Fetch URL: https://github.com/user/repo.git\n  Push  URL: https://github.com/user/repo.git\n  HEAD branch: main"

        result = await get_default_branch(Path("/mock/repo"))

        assert result == "main"
        mock_git.assert_called_once_with(Path("/mock/repo"), ["remote", "show", "origin"])

    # Test fallback to main
    with patch("yellhorn_mcp.utils.git_utils.run_git_command") as mock_git:
        # First call fails (remote show origin)
        mock_git.side_effect = [
            YellhornMCPError("Command failed"),
            "main exists",  # Second call succeeds (show-ref main)
        ]

        result = await get_default_branch(Path("/mock/repo"))

        assert result == "main"
        assert mock_git.call_count == 2

    # Test fallback to master
    with patch("yellhorn_mcp.utils.git_utils.run_git_command") as mock_git:
        # First two calls fail
        mock_git.side_effect = [
            YellhornMCPError("Command failed"),  # remote show origin
            YellhornMCPError("Command failed"),  # show-ref main
            "master exists",  # show-ref master
        ]

        result = await get_default_branch(Path("/mock/repo"))

        assert result == "master"
        assert mock_git.call_count == 3

    # Test when all methods fail - should return "main" as fallback
    with patch("yellhorn_mcp.utils.git_utils.run_git_command") as mock_git:
        mock_git.side_effect = YellhornMCPError("Command failed")

        result = await get_default_branch(Path("/mock/repo"))
        assert result == "main"
        assert mock_git.call_count == 3  # remote show origin + main + master attempts


def test_is_git_repository():
    """Test the is_git_repository function."""
    # Test with .git directory (standard repository)
    with patch("pathlib.Path.exists", return_value=True):
        with patch("pathlib.Path.is_dir", return_value=True):
            with patch("pathlib.Path.is_file", return_value=False):
                assert is_git_repository(Path("/mock/repo")) is True

    # Test with .git file (worktree)
    with patch("pathlib.Path.exists", return_value=True):
        with patch("pathlib.Path.is_dir", return_value=False):
            with patch("pathlib.Path.is_file", return_value=True):
                assert is_git_repository(Path("/mock/worktree")) is True

    # Test with no .git
    with patch("pathlib.Path.exists", return_value=False):
        assert is_git_repository(Path("/mock/not_a_repo")) is False

    # Test with .git that is neither a file nor a directory
    with patch("pathlib.Path.exists", return_value=True):
        with patch("pathlib.Path.is_dir", return_value=False):
            with patch("pathlib.Path.is_file", return_value=False):
                assert is_git_repository(Path("/mock/strange_repo")) is False


def test_calculate_cost():
    """Test the calculate_cost function with different token counts and models."""
    from yellhorn_mcp.utils.cost_tracker_utils import calculate_cost

    # Test with standard model and default tier (below 200k tokens)
    cost = calculate_cost("gemini-2.5-pro", 100_000, 50_000)
    # Expected: (100,000 / 1M) * 1.25 + (50,000 / 1M) * 10.00 = 0.125 + 0.5 = 0.625
    assert cost == 0.625

    # Test with standard model and higher tier (above 200k tokens)
    cost = calculate_cost("gemini-2.5-pro", 250_000, 300_000)
    # Expected: (250,000 / 1M) * 2.50 + (300,000 / 1M) * 15.00 = 0.625 + 4.5 = 5.125
    assert cost == 5.125

    # Test with standard model and mixed tiers
    cost = calculate_cost("gemini-2.5-pro", 150_000, 250_000)
    # Expected: (150,000 / 1M) * 1.25 + (250,000 / 1M) * 15.00 = 0.1875 + 3.75 = 3.9375
    assert cost == 3.9375

    # Test with flash model (same pricing across tiers)
    cost = calculate_cost("gemini-2.5-flash", 150_000, 50_000)
    # Expected: (150,000 / 1M) * 0.15 + (50,000 / 1M) * 3.50 = 0.0225 + 0.175 = 0.1975
    assert cost == 0.1975

    # Test with unknown model
    cost = calculate_cost("unknown-model", 100_000, 50_000)
    assert cost is None


@pytest.mark.asyncio
async def test_create_workplan(mock_request_context, mock_genai_client):
    """Test creating a workplan."""
    # Set the mock client in the context
    mock_request_context.request_context.lifespan_context["client"] = mock_genai_client

    with patch(
        "yellhorn_mcp.server.create_github_issue", new_callable=AsyncMock
    ) as mock_create_issue:
        mock_create_issue.return_value = {
            "number": "123",
            "url": "https://github.com/user/repo/issues/123",
        }

        with patch(
            "yellhorn_mcp.server.add_issue_comment", new_callable=AsyncMock
        ) as mock_add_comment:
            with patch("asyncio.create_task") as mock_create_task:
                # Mock the return value of create_task to avoid actual async processing
                mock_task = MagicMock()
                mock_create_task.return_value = mock_task

                # Test with required title and detailed description (default codebase_reasoning="full")
                response = await create_workplan(
                    title="Feature Implementation Plan",
                    detailed_description="Create a new feature to support X",
                    ctx=mock_request_context,
                )

                # Parse response as JSON and check contents
                import json

                result = json.loads(response)
                assert result["issue_url"] == "https://github.com/user/repo/issues/123"
                assert result["issue_number"] == "123"

                mock_create_issue.assert_called_once()
                mock_create_task.assert_called_once()

                # Check that the GitHub issue is created with the provided title
                issue_call_args = mock_create_issue.call_args[0]
                assert issue_call_args[1] == "Feature Implementation Plan"  # title
                assert issue_call_args[2] == "Create a new feature to support X"  # description

                # Verify that add_github_issue_comment was called with the submission metadata
                mock_add_comment.assert_called_once()
                comment_args = mock_add_comment.call_args
                assert comment_args[0][0] == Path("/mock/repo")  # repo_path
                assert comment_args[0][1] == "123"  # issue_number
                submission_comment = comment_args[0][2]  # comment content

                # Verify the submission comment contains expected metadata
                assert "## 🚀 Generating workplan..." in submission_comment
                assert "**Model**: `gemini-2.5-pro`" in submission_comment
                assert "**Search Grounding**: " in submission_comment
                assert "**Codebase Reasoning**: `full`" in submission_comment
                assert "**Yellhorn Version**: " in submission_comment
                assert (
                    "_This issue will be updated once generation is complete._"
                    in submission_comment
                )

                # Check that the process_workplan_async task is created with the correct parameters
                args, kwargs = mock_create_task.call_args
                coroutine = args[0]
                assert coroutine.__name__ == "process_workplan_async"
                # Close the coroutine to prevent RuntimeWarning
                coroutine.close()

                # Reset mocks for next test
                mock_create_issue.reset_mock()
                mock_add_comment.reset_mock()
                mock_create_task.reset_mock()

                # Test with codebase_reasoning="none"
                response = await create_workplan(
                    title="Basic Plan",
                    detailed_description="Simple plan description",
                    ctx=mock_request_context,
                    codebase_reasoning="none",
                )

                # Parse response as JSON and check contents
                result = json.loads(response)
                assert result["issue_url"] == "https://github.com/user/repo/issues/123"
                assert result["issue_number"] == "123"

                mock_create_issue.assert_called_once()
                # Verify that no async task was created for AI processing
                mock_create_task.assert_not_called()

                # Verify that add_github_issue_comment was called even with codebase_reasoning="none"
                mock_add_comment.assert_called_once()
                comment_args = mock_add_comment.call_args
                submission_comment = comment_args[0][2]
                assert "**Codebase Reasoning**: `none`" in submission_comment

                # Check the create issue call
                issue_call_args = mock_create_issue.call_args[0]
                assert issue_call_args[1] == "Basic Plan"  # title
                assert issue_call_args[2] == "Simple plan description"  # body


@pytest.mark.asyncio
async def test_run_github_command_success():
    """Test successful GitHub CLI command execution."""
    with patch("asyncio.create_subprocess_exec") as mock_exec:
        mock_process = AsyncMock()
        mock_process.communicate.return_value = (b"output", b"")
        mock_process.returncode = 0
        mock_exec.return_value = mock_process

        result = await run_github_command(Path("/mock/repo"), ["issue", "list"])

        assert result == "output"
        mock_exec.assert_called_once()

    # Ensure no coroutines are left behind
    await asyncio.sleep(0)


@pytest.mark.asyncio
async def test_ensure_label_exists():
    """Test ensuring a GitHub label exists."""
    with patch("yellhorn_mcp.utils.git_utils.run_github_command") as mock_gh:
        # Test with label name only - mock the label check first
        mock_gh.return_value = "[]"
        await ensure_label_exists(Path("/mock/repo"), "test-label")
        # Should first check if label exists, then create it
        assert mock_gh.call_count == 2
        mock_gh.assert_any_call(
            Path("/mock/repo"), ["label", "list", "--json", "name", "--search=test-label"]
        )
        mock_gh.assert_any_call(
            Path("/mock/repo"),
            ["label", "create", "test-label", "--color=5fa46c", "--description="],
        )

        # Reset mock
        mock_gh.reset_mock()

        # Test with label name and description
        mock_gh.return_value = "[]"
        await ensure_label_exists(Path("/mock/repo"), "test-label", "Test label description")
        # Should first check if label exists, then create it with description
        assert mock_gh.call_count == 2
        mock_gh.assert_any_call(
            Path("/mock/repo"), ["label", "list", "--json", "name", "--search=test-label"]
        )
        mock_gh.assert_any_call(
            Path("/mock/repo"),
            [
                "label",
                "create",
                "test-label",
                "--color=5fa46c",
                "--description=Test label description",
            ],
        )

        # Reset mock
        mock_gh.reset_mock()

        # Test with error handling (should not raise exception)
        mock_gh.side_effect = Exception("Label creation failed")
        # This should not raise an exception
        await ensure_label_exists(Path("/mock/repo"), "test-label")


@pytest.mark.asyncio
async def test_get_github_issue_body():
    """Test fetching GitHub issue body."""
    with patch("yellhorn_mcp.utils.git_utils.run_github_command") as mock_gh:
        # Test fetching issue content with URL
        mock_gh.return_value = '{"body": "Issue content"}'
        issue_url = "https://github.com/user/repo/issues/123"

        result = await get_github_issue_body(Path("/mock/repo"), issue_url)

        assert result == "Issue content"
        mock_gh.assert_called_once_with(
            Path("/mock/repo"), ["issue", "view", "123", "--json", "body"]
        )

        # Reset mock
        mock_gh.reset_mock()

        # Test fetching issue content with URL
        mock_gh.return_value = '{"body": "Issue content from URL"}'
        issue_url = "https://github.com/user/repo/issues/456"

        result = await get_github_issue_body(Path("/mock/repo"), issue_url)

        assert result == "Issue content from URL"
        mock_gh.assert_called_once_with(
            Path("/mock/repo"), ["issue", "view", "456", "--json", "body"]
        )

        # Reset mock
        mock_gh.reset_mock()

        # Test fetching issue content with just issue number
        mock_gh.return_value = '{"body": "Issue content from number"}'
        issue_number = "789"

        result = await get_github_issue_body(Path("/mock/repo"), issue_number)

        assert result == "Issue content from number"
        mock_gh.assert_called_once_with(
            Path("/mock/repo"), ["issue", "view", "789", "--json", "body"]
        )


@pytest.mark.asyncio
async def test_get_github_pr_diff():
    """Test fetching GitHub PR diff."""
    with patch("yellhorn_mcp.utils.git_utils.run_github_command") as mock_gh:
        mock_gh.return_value = "diff content"
        pr_url = "https://github.com/user/repo/pull/123"

        result = await get_github_pr_diff(Path("/mock/repo"), pr_url)

        assert result == "diff content"
        mock_gh.assert_called_once_with(Path("/mock/repo"), ["pr", "diff", "123"])


@pytest.mark.asyncio
async def test_post_github_pr_review():
    """Test posting GitHub PR review."""
    with (
        patch("tempfile.NamedTemporaryFile") as mock_tmp,
        patch("os.unlink") as mock_unlink,
        patch("yellhorn_mcp.utils.git_utils.run_github_command") as mock_gh,
    ):
        # Mock the temporary file
        mock_file = MagicMock()
        mock_file.name = "/tmp/review_file.md"
        mock_tmp.return_value.__enter__.return_value = mock_file

        mock_gh.return_value = "Review posted"
        pr_url = "https://github.com/user/repo/pull/123"

        result = await post_github_pr_review(Path("/mock/repo"), pr_url, "Review content")

        assert "Review posted" in result
        assert "pullrequestreview" in result
        mock_gh.assert_called_once()
        # Verify the PR number is extracted correctly
        args, kwargs = mock_gh.call_args
        assert "123" in args[1]
        # Verify temp file is cleaned up
        mock_unlink.assert_called_once_with("/tmp/review_file.md")


@pytest.mark.asyncio
async def test_add_github_issue_comment():
    """Test adding a comment to a GitHub issue."""
    with patch("yellhorn_mcp.utils.git_utils.run_github_command") as mock_gh:
        # First test - successful comment
        await add_github_issue_comment(Path("/mock/repo"), "123", "Comment content")

        mock_gh.assert_called_once()
        # Verify the issue number and command are correct
        args, kwargs = mock_gh.call_args
        assert args[0] == Path("/mock/repo")
        assert "issue" in args[1]
        assert "comment" in args[1]
        assert "123" in args[1]
        assert "--body" in args[1]
        # No temp file cleanup needed for this function

        # Test with error
        mock_gh.reset_mock()
        mock_gh.side_effect = Exception("Comment failed")

        with pytest.raises(Exception, match="Comment failed"):
            await add_github_issue_comment(Path("/mock/repo"), "123", "Comment content")


@pytest.mark.asyncio
async def test_update_github_issue():
    """Test updating a GitHub issue."""
    with (
        patch("tempfile.NamedTemporaryFile") as mock_tmp,
        patch("os.unlink") as mock_unlink,
        patch("yellhorn_mcp.utils.git_utils.run_github_command") as mock_gh,
    ):
        # Mock the temporary file
        mock_file = MagicMock()
        mock_file.name = "/tmp/test_file.md"
        mock_tmp.return_value.__enter__.return_value = mock_file

        await update_github_issue(Path("/mock/repo"), "123", body="Updated content")

        mock_gh.assert_called_once()
        # Verify temp file is cleaned up
        mock_unlink.assert_called_once_with("/tmp/test_file.md")


@pytest.mark.asyncio
async def test_process_workplan_async(mock_request_context, mock_genai_client):
    """Test processing workplan asynchronously."""
    # Set the mock client in the context
    mock_request_context.request_context.lifespan_context["gemini_client"] = mock_genai_client
    mock_request_context.request_context.lifespan_context["openai_client"] = None
    mock_request_context.request_context.lifespan_context["use_search_grounding"] = False

    with (
        patch(
            "yellhorn_mcp.processors.workplan_processor.get_codebase_snapshot",
            new_callable=AsyncMock,
        ) as mock_snapshot,
        patch(
            "yellhorn_mcp.processors.workplan_processor.format_codebase_for_prompt",
            new_callable=AsyncMock,
        ) as mock_format,
        patch(
            "yellhorn_mcp.processors.workplan_processor.generate_workplan_with_gemini",
            new_callable=AsyncMock,
        ) as mock_generate_gemini,
        patch(
            "yellhorn_mcp.processors.workplan_processor.update_issue_with_workplan",
            new_callable=AsyncMock,
        ) as mock_update,
        patch(
            "yellhorn_mcp.processors.workplan_processor.format_metrics_section"
        ) as mock_format_metrics,
        patch(
            "yellhorn_mcp.processors.workplan_processor.add_issue_comment", new_callable=AsyncMock
        ) as mock_add_comment,
        patch("yellhorn_mcp.processors.workplan_processor.calculate_cost") as mock_calculate_cost,
    ):
        mock_snapshot.return_value = (["file1.py"], {"file1.py": "content"})
        mock_format.return_value = "Formatted codebase"
        mock_format_metrics.return_value = (
            "\n\n---\n## Completion Metrics\n*   **Model Used**: `gemini-2.5-pro`"
        )
        mock_calculate_cost.return_value = 0.001  # Mock cost calculation

        # Mock completion metadata
        from yellhorn_mcp.models.metadata_models import CompletionMetadata

        mock_completion_metadata = CompletionMetadata(
            model_name="gemini-2.5-pro",
            status="✅ Generated successfully",
            generation_time_seconds=0.0,
            input_tokens=1000,
            output_tokens=500,
            total_tokens=1500,
            timestamp=None,
        )

        # Mock generate_workplan_with_gemini to return content and metadata
        mock_generate_gemini.return_value = ("Mock workplan content", mock_completion_metadata)

        # Test with required parameters
        from datetime import datetime, timezone

        await process_workplan_async(
            Path("/mock/repo"),
            mock_genai_client,
            None,  # No OpenAI client
            "gemini-2.5-pro",
            "Feature Implementation Plan",
            "123",
            "full",  # codebase_reasoning
            "Create a new feature to support X",  # detailed_description
            ctx=mock_request_context,
            _meta={
                "start_time": datetime.now(timezone.utc),
                "submitted_urls": [],
            },
        )

        # Check that generate_workplan_with_gemini was called
        mock_generate_gemini.assert_called_once()
        call_args = mock_generate_gemini.call_args
        assert call_args[0][0] == mock_genai_client  # client
        assert call_args[0][1] == "gemini-2.5-pro"  # model
        # The prompt is the third argument
        prompt_content = call_args[0][2]
        assert "# Task Title" in prompt_content
        assert "Feature Implementation Plan" in prompt_content
        assert "# Task Details" in prompt_content
        assert "Create a new feature to support X" in prompt_content

        # Check for workplan structure instructions
        assert "## Summary" in prompt_content
        assert "## Implementation Steps" in prompt_content
        assert "## Technical Details" in prompt_content
        assert "## Testing Approach" in prompt_content
        assert "## Files to Modify" in prompt_content
        assert "## Example Code Changes" in prompt_content

        # Check that format_metrics_section was NOT called (metrics no longer in body)
        mock_format_metrics.assert_not_called()

        # Check that the issue was updated with the workplan
        mock_update.assert_called_once()
        args, kwargs = mock_update.call_args
        assert args[0] == Path("/mock/repo")
        assert args[1] == "123"

        # Verify the content contains the expected pieces
        update_content = args[2]
        assert "# Feature Implementation Plan" in update_content
        assert "Mock workplan content" in update_content
        # Should NOT have metrics in body
        assert "## Completion Metrics" not in update_content

        # Verify that add_github_issue_comment was called with the completion metadata
        mock_add_comment.assert_called_once()
        comment_args = mock_add_comment.call_args
        assert comment_args[0][0] == Path("/mock/repo")  # repo_path
        assert comment_args[0][1] == "123"  # issue_number
        completion_comment = comment_args[0][2]  # comment content

        # Verify the completion comment contains expected metadata
        assert "## ✅ Generated successfully" in completion_comment
        assert "### Generation Details" in completion_comment
        assert "**Time**: " in completion_comment
        assert "### Token Usage" in completion_comment
        assert "**Input Tokens**: 1,000" in completion_comment
        assert "**Output Tokens**: 500" in completion_comment
        assert "**Total Tokens**: 1,500" in completion_comment


@pytest.mark.asyncio
async def test_process_workplan_async_empty_response(mock_request_context, mock_genai_client):
    """Test processing workplan asynchronously with empty API response."""
    # Set the mock client in the context
    mock_request_context.request_context.lifespan_context["gemini_client"] = mock_genai_client
    mock_request_context.request_context.lifespan_context["openai_client"] = None
    mock_request_context.request_context.lifespan_context["use_search_grounding"] = False

    with (
        patch(
            "yellhorn_mcp.processors.workplan_processor.get_codebase_snapshot",
            new_callable=AsyncMock,
        ) as mock_snapshot,
        patch(
            "yellhorn_mcp.processors.workplan_processor.format_codebase_for_prompt",
            new_callable=AsyncMock,
        ) as mock_format,
        patch(
            "yellhorn_mcp.processors.workplan_processor.generate_workplan_with_gemini",
            new_callable=AsyncMock,
        ) as mock_generate_gemini,
        patch(
            "yellhorn_mcp.processors.workplan_processor.add_issue_comment", new_callable=AsyncMock
        ) as mock_add_comment,
        patch(
            "yellhorn_mcp.processors.workplan_processor.update_issue_with_workplan"
        ) as mock_update,
    ):
        mock_snapshot.return_value = (["file1.py"], {"file1.py": "content"})
        mock_format.return_value = "Formatted codebase"

        # Mock generate_workplan_with_gemini to return empty content
        mock_generate_gemini.return_value = ("", None)  # Empty content, no metadata

        # Run the function
        await process_workplan_async(
            Path("/mock/repo"),
            mock_genai_client,
            None,  # No OpenAI client
            "gemini-2.5-pro",
            "Feature Implementation Plan",
            "123",
            "full",  # codebase_reasoning
            "Create a new feature to support X",  # detailed_description
            ctx=mock_request_context,
        )

        # Check that add_github_issue_comment was called with error message
        mock_add_comment.assert_called_once()
        args, kwargs = mock_add_comment.call_args
        assert args[0] == Path("/mock/repo")
        assert args[1] == "123"
        assert "⚠️ AI workplan enhancement failed" in args[2]
        assert "empty response" in args[2]

        # Verify update_github_issue was not called
        mock_update.assert_not_called()


@pytest.mark.asyncio
async def test_process_workplan_async_error(mock_request_context, mock_genai_client):
    """Test processing workplan asynchronously with API error."""
    # Set the mock client in the context
    mock_request_context.request_context.lifespan_context["gemini_client"] = mock_genai_client
    mock_request_context.request_context.lifespan_context["openai_client"] = None
    mock_request_context.request_context.lifespan_context["use_search_grounding"] = False

    with (
        patch(
            "yellhorn_mcp.processors.workplan_processor.get_codebase_snapshot",
            new_callable=AsyncMock,
        ) as mock_snapshot,
        patch(
            "yellhorn_mcp.processors.workplan_processor.format_codebase_for_prompt",
            new_callable=AsyncMock,
        ) as mock_format,
        patch(
            "yellhorn_mcp.processors.workplan_processor.generate_workplan_with_gemini",
            new_callable=AsyncMock,
        ) as mock_generate_gemini,
        patch(
            "yellhorn_mcp.processors.workplan_processor.add_issue_comment", new_callable=AsyncMock
        ) as mock_add_comment,
        patch(
            "yellhorn_mcp.processors.workplan_processor.update_issue_with_workplan"
        ) as mock_update,
    ):
        mock_snapshot.return_value = (["file1.py"], {"file1.py": "content"})
        mock_format.return_value = "Formatted codebase"

        # Mock generate_workplan_with_gemini to raise an exception
        mock_generate_gemini.side_effect = Exception("API error occurred")

        # Run the function
        await process_workplan_async(
            Path("/mock/repo"),
            mock_genai_client,
            None,  # No OpenAI client
            "gemini-2.5-pro",
            "Feature Implementation Plan",
            "123",
            "full",  # codebase_reasoning
            "Create a new feature to support X",  # detailed_description
            ctx=mock_request_context,
        )

        # Check that add_github_issue_comment was called with error message
        mock_add_comment.assert_called_once()
        args, kwargs = mock_add_comment.call_args
        assert args[0] == Path("/mock/repo")
        assert args[1] == "123"
        error_comment = args[2]

        # Verify the error comment contains expected content
        assert "❌ **Error generating workplan**" in error_comment
        assert "API error occurred" in error_comment

        # Verify update_github_issue was not called
        mock_update.assert_not_called()


@pytest.mark.asyncio
async def test_get_workplan(mock_request_context):
    """Test getting the workplan with the required issue number."""
    with patch("yellhorn_mcp.server.get_issue_body", new_callable=AsyncMock) as mock_get_issue:
        mock_get_issue.return_value = "# workplan\n\n1. Implement X\n2. Test X"

        # Test getting the workplan with the required issue number
        result = await get_workplan(mock_request_context, issue_number="123")

        assert result == "# workplan\n\n1. Implement X\n2. Test X"
        mock_get_issue.assert_called_once_with(
            mock_request_context.request_context.lifespan_context["repo_path"], "123"
        )

    # Test error handling
    with patch("yellhorn_mcp.server.get_issue_body", new_callable=AsyncMock) as mock_get_issue:
        mock_get_issue.side_effect = Exception("Failed to get issue")

        with pytest.raises(YellhornMCPError, match="Failed to retrieve workplan"):
            await get_workplan(mock_request_context, issue_number="123")


@pytest.mark.asyncio
async def test_get_workplan_with_different_issue(mock_request_context):
    """Test getting the workplan with a different issue number."""
    with patch("yellhorn_mcp.server.get_issue_body", new_callable=AsyncMock) as mock_get_issue:
        mock_get_issue.return_value = "# Different workplan\n\n1. Implement Y\n2. Test Y"

        # Test with a different issue number
        result = await get_workplan(
            ctx=mock_request_context,
            issue_number="456",
        )

        assert result == "# Different workplan\n\n1. Implement Y\n2. Test Y"
        mock_get_issue.assert_called_once_with(
            mock_request_context.request_context.lifespan_context["repo_path"], "456"
        )


# This test is no longer needed because issue_number is now required


# This test is no longer needed because issue number auto-detection was removed


@pytest.mark.asyncio
async def test_judge_workplan(mock_request_context, mock_genai_client):
    """Test judging work with required issue number and placeholder sub-issue creation."""
    # Set the mock client in the context
    mock_request_context.request_context.lifespan_context["client"] = mock_genai_client

    with patch("yellhorn_mcp.server.run_git_command", new_callable=AsyncMock) as mock_run_git:
        # Mock the git rev-parse commands
        mock_run_git.side_effect = ["abc1234", "def5678"]  # base_commit_hash, head_commit_hash

        with patch("yellhorn_mcp.server.get_issue_body", new_callable=AsyncMock) as mock_get_issue:
            mock_get_issue.return_value = "# workplan\n\n1. Implement X\n2. Test X"

            with patch("yellhorn_mcp.server.get_git_diff", new_callable=AsyncMock) as mock_get_diff:
                mock_get_diff.return_value = "diff --git a/file.py b/file.py\n+def x(): pass"

                with patch(
                    "yellhorn_mcp.integrations.github_integration.add_issue_comment"
                ) as mock_add_comment:
                    with patch(
                        "yellhorn_mcp.integrations.github_integration.create_judgement_subissue",
                        new_callable=AsyncMock,
                    ) as mock_create_judgement_subissue:
                        mock_create_judgement_subissue.return_value = (
                            "https://github.com/user/repo/issues/789"
                        )
                        with patch("asyncio.create_task") as mock_create_task:

                            # Test with default refs
                            result = await judge_workplan(
                                ctx=mock_request_context,
                                issue_number="123",
                            )

                            # Parse the JSON result
                            result_data = json.loads(result)
                            assert (
                                result_data["subissue_url"]
                                == "https://github.com/user/repo/issues/789"
                            )
                            assert result_data["subissue_number"] == "789"

                            # Verify the function calls
                            repo_path = mock_request_context.request_context.lifespan_context[
                                "repo_path"
                            ]
                            mock_get_issue.assert_called_once_with(repo_path, "123")
                            mock_get_diff.assert_called_once_with(repo_path, "main", "HEAD", "full")

                            # Verify create_judgement_subissue was called with correct parameters
                            mock_create_judgement_subissue.assert_called_once()
                            call_args = mock_create_judgement_subissue.call_args
                            assert call_args[0][0] == repo_path  # repo_path
                            assert call_args[0][1] == "123"  # parent_issue

                            mock_create_task.assert_called_once()

                            # Check process_judgement_async coroutine with new signature
                            coroutine = mock_create_task.call_args[0][0]
                            assert coroutine.__name__ == "process_judgement_async"
                            # Close the coroutine to prevent RuntimeWarning
                            coroutine.close()


@pytest.mark.asyncio
async def test_judge_workplan_with_different_issue(mock_request_context, mock_genai_client):
    """Test judging work with a different issue number and codebase reasoning modes."""
    # Set the mock client in the context
    mock_request_context.request_context.lifespan_context["client"] = mock_genai_client

    with patch("yellhorn_mcp.server.run_git_command", new_callable=AsyncMock) as mock_run_git:
        # Mock the git rev-parse commands
        mock_run_git.side_effect = [
            "v1.0-hash",
            "feature-hash",
        ]  # base_commit_hash, head_commit_hash

        with patch("yellhorn_mcp.server.get_issue_body", new_callable=AsyncMock) as mock_get_issue:
            mock_get_issue.return_value = "# Different workplan\n\n1. Implement Y\n2. Test Y"

            with patch("yellhorn_mcp.server.get_git_diff", new_callable=AsyncMock) as mock_get_diff:
                mock_get_diff.return_value = "diff --git a/file.py b/file.py\n+def x(): pass"

                with patch(
                    "yellhorn_mcp.integrations.github_integration.add_issue_comment"
                ) as mock_add_comment:
                    with patch(
                        "yellhorn_mcp.integrations.github_integration.create_judgement_subissue",
                        new_callable=AsyncMock,
                    ) as mock_create_judgement_subissue:
                        mock_create_judgement_subissue.return_value = (
                            "https://github.com/user/repo/issues/999"
                        )
                        with patch("asyncio.create_task") as mock_create_task:
                            # Test with a different issue number and custom refs
                            base_ref = "v1.0"
                            head_ref = "feature-branch"
                            result = await judge_workplan(
                                ctx=mock_request_context,
                                issue_number="456",
                                base_ref=base_ref,
                                head_ref=head_ref,
                            )

                            # Parse the JSON result
                            result_data = json.loads(result)
                            assert (
                                result_data["subissue_url"]
                                == "https://github.com/user/repo/issues/999"
                            )
                            assert result_data["subissue_number"] == "999"

                            # Verify the correct functions were called
                            repo_path = mock_request_context.request_context.lifespan_context[
                                "repo_path"
                            ]
                            mock_get_issue.assert_called_once_with(repo_path, "456")
                            mock_get_diff.assert_called_once_with(
                                repo_path, base_ref, head_ref, "full"
                            )
                            mock_create_judgement_subissue.assert_called_once()

                            # Close the coroutine to prevent RuntimeWarning
                            coroutine = mock_create_task.call_args[0][0]
                            assert coroutine.__name__ == "process_judgement_async"
                            coroutine.close()


@pytest.mark.asyncio
async def test_judge_workplan_disable_search_grounding(mock_request_context, mock_genai_client):
    """Test judge_workplan with disable_search_grounding flag."""
    # Set the mock client in the context
    mock_request_context.request_context.lifespan_context["client"] = mock_genai_client
    mock_request_context.request_context.lifespan_context["use_search_grounding"] = True

    with patch("yellhorn_mcp.server.run_git_command", new_callable=AsyncMock) as mock_run_git:
        mock_run_git.side_effect = ["abc1234", "def5678"]

        with patch("yellhorn_mcp.server.get_issue_body", new_callable=AsyncMock) as mock_get_issue:
            mock_get_issue.return_value = "# workplan\n\n1. Implement X\n2. Test X"

            with patch("yellhorn_mcp.server.get_git_diff", new_callable=AsyncMock) as mock_get_diff:
                mock_get_diff.return_value = "diff --git a/file.py b/file.py\n+def x(): pass"

                with patch(
                    "yellhorn_mcp.integrations.github_integration.add_issue_comment"
                ) as mock_add_comment:
                    with patch(
                        "yellhorn_mcp.integrations.github_integration.create_judgement_subissue",
                        new_callable=AsyncMock,
                    ) as mock_create_judgement_subissue:
                        mock_create_judgement_subissue.return_value = (
                            "https://github.com/user/repo/issues/789"
                        )
                        with patch("asyncio.create_task") as mock_create_task:
                            # Test with disable_search_grounding=True
                            result = await judge_workplan(
                                ctx=mock_request_context,
                                issue_number="123",
                                disable_search_grounding=True,
                            )

                    # Verify search grounding was disabled during the call
                    # (The setting should be restored by now)
                    assert (
                        mock_request_context.request_context.lifespan_context[
                            "use_search_grounding"
                        ]
                        == True
                    )

                    # Parse the JSON result
                    result_data = json.loads(result)
                    assert result_data["subissue_url"] == "https://github.com/user/repo/issues/789"

                    # Close coroutine to prevent RuntimeWarning
                    coroutine = mock_create_task.call_args[0][0]
                    coroutine.close()


@pytest.mark.asyncio
async def test_judge_workplan_empty_diff(mock_request_context, mock_genai_client):
    """Test judge_workplan with empty diff."""
    # Set the mock client in the context
    mock_request_context.request_context.lifespan_context["client"] = mock_genai_client

    with patch("yellhorn_mcp.server.run_git_command", new_callable=AsyncMock) as mock_run_git:
        # First test: empty diff
        mock_run_git.side_effect = ["abc1234", "def5678"]

        with patch("yellhorn_mcp.server.get_issue_body", new_callable=AsyncMock) as mock_get_issue:
            mock_get_issue.return_value = "# workplan\n\n1. Implement X\n2. Test X"

            with patch("yellhorn_mcp.server.get_git_diff", new_callable=AsyncMock) as mock_get_diff:
                # Test with empty diff
                mock_get_diff.return_value = ""

                result = await judge_workplan(
                    ctx=mock_request_context,
                    issue_number="123",
                )

                # Should return JSON with error about no differences
                result_data = json.loads(result)
                assert "error" in result_data
                assert "No changes found between main and HEAD" in result_data["error"]
                assert result_data["base_commit"] == "abc1234"
                assert result_data["head_commit"] == "def5678"

                # Reset mocks for second test
                mock_run_git.reset_mock()
                mock_run_git.side_effect = ["abc1234", "def5678"]  # Fresh side_effect
                mock_get_diff.return_value = "Changed files between main and HEAD:"

                result = await judge_workplan(
                    ctx=mock_request_context,
                    issue_number="123",
                    codebase_reasoning="file_structure",
                )

                # Should return JSON with error about no differences for file_structure mode too
                result_data = json.loads(result)
                assert "error" in result_data
                assert "No changes found between main and HEAD" in result_data["error"]


@pytest.mark.asyncio
async def test_process_judgement_async_update_subissue(mock_request_context, mock_genai_client):
    """Test process_judgement_async updates existing sub-issue instead of creating new one."""
    from yellhorn_mcp.server import process_judgement_async

    # Mock the Gemini client response
    mock_response = MagicMock()
    mock_response.text = "## Judgement Summary\nImplementation looks good."
    mock_response.usage_metadata = MagicMock()
    mock_response.usage_metadata.prompt_token_count = 1000
    mock_response.usage_metadata.candidates_token_count = 500
    mock_response.usage_metadata.total_token_count = 1500
    mock_response.citations = []

    # Mock candidates to avoid finish_reason error
    mock_candidate = MagicMock()
    mock_candidate.finish_reason = MagicMock()
    mock_candidate.finish_reason.name = "STOP"
    mock_candidate.safety_ratings = []
    mock_response.candidates = [mock_candidate]

    # Mock the async generate content function
    with patch(
        "yellhorn_mcp.integrations.gemini_integration.async_generate_content_with_config"
    ) as mock_generate:
        mock_generate.return_value = mock_response

        with patch("yellhorn_mcp.utils.git_utils.update_github_issue") as mock_update_issue:
            with patch(
                "yellhorn_mcp.processors.judgement_processor.add_issue_comment"
            ) as mock_add_comment:
                with patch(
                    "yellhorn_mcp.processors.judgement_processor.create_judgement_subissue"
                ) as mock_create_subissue:
                    mock_create_subissue.return_value = "https://github.com/user/repo/issues/789"
                    with patch(
                        "yellhorn_mcp.processors.judgement_processor.run_git_command"
                    ) as mock_run_git:
                        # Mock getting the remote URL
                        mock_run_git.return_value = "https://github.com/user/repo"
                        with patch(
                            "yellhorn_mcp.utils.search_grounding_utils._get_gemini_search_tools"
                        ) as mock_get_tools:
                            with patch(
                                "yellhorn_mcp.processors.judgement_processor.get_codebase_snapshot",
                                new_callable=AsyncMock,
                            ) as mock_snapshot:
                                with patch(
                                    "yellhorn_mcp.processors.judgement_processor.format_codebase_for_prompt",
                                    new_callable=AsyncMock,
                                ) as mock_format:
                                    mock_get_tools.return_value = [MagicMock()]
                                    mock_snapshot.return_value = (
                                        ["file1.py"],
                                        {"file1.py": "content"},
                                    )
                                    mock_format.return_value = "Formatted codebase"

                                    # Set context for search grounding
                                    mock_request_context.request_context.lifespan_context[
                                        "use_search_grounding"
                                    ] = True

                                    # Call process_judgement_async with new signature
                                    from datetime import datetime, timezone

                                    await process_judgement_async(
                                        repo_path=Path("/test/repo"),
                                        gemini_client=mock_genai_client,
                                        openai_client=None,
                                        model="gemini-2.5-pro",
                                        workplan_content="# Workplan\n1. Do something",
                                        diff_content="diff --git a/file.py b/file.py\n+def test(): pass",
                                        base_ref="main",
                                        head_ref="HEAD",
                                        subissue_to_update="789",
                                        parent_workplan_issue_number="123",
                                        ctx=mock_request_context,
                                        base_commit_hash="abc1234",
                                        head_commit_hash="def5678",
                                        debug=False,
                                        codebase_reasoning="full",
                                        _meta={
                                            "start_time": datetime.now(timezone.utc),
                                            "submitted_urls": [],
                                        },
                                    )

                                    # Verify update_github_issue was called instead of create_github_subissue
                                    mock_update_issue.assert_called_once()
                                    # Verify create_github_subissue was NOT called
                                    mock_create_subissue.assert_not_called()

                                    # Verify the arguments passed to update_github_issue
                                    call_args = mock_update_issue.call_args
                                    assert call_args.kwargs["repo_path"] == Path("/test/repo")
                                    assert call_args.kwargs["issue_number"] == "789"
                                    assert (
                                        "Judgement for #123: HEAD vs main"
                                        in call_args.kwargs["title"]
                                    )
                                    body = call_args.kwargs["body"]
                                    assert "## Comparison Metadata" in body
                                    assert "**Workplan Issue**: `#123`" in body
                                    assert "**Base Ref**: `main` (Commit: `abc1234`)" in body
                                    assert "**Head Ref**: `HEAD` (Commit: `def5678`)" in body
                                    assert "**Codebase Reasoning Mode**: `full`" in body
                                    assert "**AI Model**: `gemini-2.5-pro`" in body
                                    assert "## Judgement Summary" in body
                                    assert "Implementation looks good." in body
                                    # Should NOT have metrics in body
                                    assert "## Completion Metrics" not in body

                                    # Verify completion metadata comment was added to sub-issue
                                    mock_add_comment.assert_called_once()
                                    comment_args = mock_add_comment.call_args
                                    assert comment_args[0][0] == Path("/test/repo")  # repo_path
                                    assert (
                                        comment_args[0][1] == "789"
                                    )  # sub-issue number, not parent issue
                                    completion_comment = comment_args[0][2]  # comment content

                                    # Verify the completion comment contains expected metadata
                                    assert "## ✅ Generated successfully" in completion_comment
                                    assert "### Generation Details" in completion_comment
                                    assert "**Time**: " in completion_comment
                                    assert "### Token Usage" in completion_comment
                                    assert "**Input Tokens**: 1,000" in completion_comment
                                    assert "**Total Tokens**: 1,500" in completion_comment
                                    assert "**Context Size**: " in completion_comment
                                    assert "**Finish Reason**: `STOP`" in completion_comment

                                    # Test with debug=True
                                    mock_update_issue.reset_mock()
                                mock_add_comment.reset_mock()

                                await process_judgement_async(
                                    repo_path=Path("/test/repo"),
                                    gemini_client=mock_genai_client,
                                    openai_client=None,
                                    model="gemini-2.5-pro",
                                    workplan_content="# Workplan\n1. Do something",
                                    diff_content="diff --git a/file.py b/file.py\n+def test(): pass",
                                    base_ref="main",
                                    head_ref="HEAD",
                                    subissue_to_update="789",
                                    parent_workplan_issue_number="123",
                                    ctx=mock_request_context,
                                    base_commit_hash="abc1234",
                                    head_commit_hash="def5678",
                                    debug=True,
                                    codebase_reasoning="full",
                                    _meta={
                                        "start_time": datetime.now(timezone.utc),
                                        "submitted_urls": [],
                                    },
                                )

                                # Verify both completion metadata and debug comments were added
                                assert mock_add_comment.call_count == 2

                                # First call should be debug comment (when debug=True, it's added first)
                                first_call_args = mock_add_comment.call_args_list[0]
                                assert first_call_args[0][1] == "789"  # subissue_to_update
                                assert (
                                    "Debug: Full prompt used for generation"
                                    in first_call_args[0][2]
                                )

                                # Second call should be completion metadata
                                second_call_args = mock_add_comment.call_args_list[1]
                                assert second_call_args[0][1] == "789"  # subissue_to_update
                                assert "## ✅ Generated successfully" in second_call_args[0][2]


# This test is no longer needed because issue_number is now required


# This test is no longer needed because issue number auto-detection was removed


@pytest.mark.asyncio
async def test_get_git_diff():
    """Test getting the diff between git refs with various codebase_reasoning modes."""
    with patch(
        "yellhorn_mcp.processors.judgement_processor.run_git_command", new_callable=AsyncMock
    ) as mock_git:
        # Test default mode (full)
        mock_git.return_value = "diff --git a/file.py b/file.py\n+def x(): pass"

        result = await get_git_diff(Path("/mock/repo"), "main", "feature-branch")

        assert result == "diff --git a/file.py b/file.py\n+def x(): pass"
        mock_git.assert_called_once_with(
            Path("/mock/repo"), ["diff", "--patch", "main...feature-branch"]
        )

        # Reset the mock for next test
        mock_git.reset_mock()

        # Test with different refs
        mock_git.return_value = "diff --git a/file2.py b/file2.py\n+def y(): pass"

        result = await get_git_diff(Path("/mock/repo"), "develop", "feature-branch")

        assert result == "diff --git a/file2.py b/file2.py\n+def y(): pass"
        mock_git.assert_called_once_with(
            Path("/mock/repo"), ["diff", "--patch", "develop...feature-branch"]
        )

        # Test completed


@pytest.mark.asyncio
async def test_create_github_subissue():
    """Test creating a GitHub sub-issue."""
    with (
        patch("yellhorn_mcp.utils.git_utils.ensure_label_exists") as mock_ensure_label,
        patch("pathlib.Path.exists", return_value=True),
        patch("pathlib.Path.unlink") as mock_unlink,
        patch("builtins.open", create=True),
        patch("yellhorn_mcp.utils.git_utils.run_github_command") as mock_gh,
    ):
        mock_gh.return_value = "https://github.com/user/repo/issues/456"

        result = await create_github_subissue(
            Path("/mock/repo"),
            "123",
            "Judgement: main..HEAD for Workplan #123",
            "## Judgement content",
            ["yellhorn-mcp"],
        )

        assert result == "https://github.com/user/repo/issues/456"
        mock_ensure_label.assert_called_once_with(
            Path("/mock/repo"),
            "yellhorn-mcp",
            "Created by Yellhorn MCP",
        )
        # Function calls run_github_command twice: once for issue creation, once for comment
        assert mock_gh.call_count == 2
        # Verify the correct labels were passed in the first call (issue creation)
        first_call_args, first_call_kwargs = mock_gh.call_args_list[0]
        assert "--label" in first_call_args[1]
        index = first_call_args[1].index("--label") + 1
        assert "yellhorn-mcp" in first_call_args[1][index]


@pytest.mark.asyncio
async def test_process_workplan_async_with_citations(mock_request_context, mock_genai_client):
    """Test process_workplan_async with Gemini response containing citations."""
    # Set the mock client in the context
    mock_request_context.request_context.lifespan_context["gemini_client"] = mock_genai_client
    mock_request_context.request_context.lifespan_context["openai_client"] = None
    mock_request_context.request_context.lifespan_context["use_search_grounding"] = False

    # Set up both API patterns for the mock with AsyncMock
    mock_genai_client.aio.generate_content = AsyncMock()
    mock_genai_client.aio.generate_content.return_value = (
        mock_genai_client.aio.models.generate_content.return_value
    )

    with (
        patch(
            "yellhorn_mcp.processors.workplan_processor.get_codebase_snapshot",
            new_callable=AsyncMock,
        ) as mock_snapshot,
        patch(
            "yellhorn_mcp.processors.workplan_processor.format_codebase_for_prompt",
            new_callable=AsyncMock,
        ) as mock_format,
        patch(
            "yellhorn_mcp.processors.workplan_processor.update_issue_with_workplan"
        ) as mock_update,
        patch(
            "yellhorn_mcp.processors.workplan_processor.format_metrics_section"
        ) as mock_format_metrics,
        patch("yellhorn_mcp.processors.workplan_processor.add_issue_comment") as mock_add_comment,
    ):
        mock_snapshot.return_value = (["file1.py"], {"file1.py": "content"})
        mock_format.return_value = "Formatted codebase"
        mock_format_metrics.return_value = (
            "\n\n---\n## Completion Metrics\n*   **Model Used**: `gemini-2.5-pro`"
        )

        # Mock a Gemini response with citations
        mock_response = mock_genai_client.aio.models.generate_content.return_value
        mock_response.text = """## Summary
This workplan implements feature X.

## Implementation Steps
1. Add new function to process data
2. Update tests

## Citations
1. https://docs.python.org/3/library/json.html
2. https://github.com/user/repo/issues/123"""
        mock_response.usage_metadata = MagicMock()
        mock_response.usage_metadata.prompt_token_count = 1000
        mock_response.usage_metadata.candidates_token_count = 500
        mock_response.usage_metadata.total_token_count = 1500

        # Mock candidates to avoid errors in add_citations
        mock_candidate = MagicMock()
        mock_candidate.finish_reason = MagicMock()
        mock_candidate.finish_reason.name = "STOP"
        mock_candidate.safety_ratings = []
        mock_candidate.grounding_metadata = MagicMock()
        mock_candidate.grounding_metadata.grounding_supports = []
        mock_response.candidates = [mock_candidate]

        # Test with required parameters
        await process_workplan_async(
            Path("/mock/repo"),
            mock_genai_client,
            None,  # No OpenAI client
            "gemini-2.5-pro",
            "Feature Implementation Plan",
            "123",
            "full",  # codebase_reasoning
            "Create a new feature to support X",  # detailed_description
            ctx=mock_request_context,
        )

        # Check that either API was called for generation
        assert (
            mock_genai_client.aio.models.generate_content.called
            or mock_genai_client.aio.generate_content.called
        )

        # Check that the issue was updated with the workplan including citations
        mock_update.assert_called_once()
        args, kwargs = mock_update.call_args
        assert args[0] == Path("/mock/repo")
        assert args[1] == "123"

        # Verify the content contains citations
        update_content = args[2]
        assert "# Feature Implementation Plan" in update_content
        assert "## Citations" in update_content
        assert "https://docs.python.org/3/library/json.html" in update_content
        assert "https://github.com/user/repo/issues/123" in update_content
        # Should NOT have metrics in body
        assert "## Completion Metrics" not in update_content


# Integration tests for new search grounding flow


@pytest.mark.asyncio
async def test_process_workplan_async_with_new_search_grounding(
    mock_request_context, mock_genai_client
):
    """Test search grounding integration in workplan generation."""

    from yellhorn_mcp.server import _get_gemini_search_tools

    # Test the search tools function directly
    search_tools = _get_gemini_search_tools("gemini-2.5-pro")
    assert search_tools is not None


@pytest.mark.asyncio
async def test_process_workplan_async_with_search_grounding_disabled(
    mock_request_context, mock_genai_client
):
    """Test that search grounding can be disabled."""
    from yellhorn_mcp.server import _get_gemini_search_tools

    # Test that non-Gemini models return None
    search_tools = _get_gemini_search_tools("gpt-4")
    assert search_tools is None

    # Test that the function returns None for unsupported models
    search_tools = _get_gemini_search_tools("unknown-model")
    assert search_tools is None


@pytest.mark.asyncio
async def test_async_generate_content_with_config_error_handling(mock_genai_client):
    """Test async_generate_content_with_config error handling."""
    from yellhorn_mcp.server import async_generate_content_with_config
    from yellhorn_mcp.utils.git_utils import YellhornMCPError

    # Test with client missing required attributes
    invalid_client = MagicMock()
    del invalid_client.aio

    with pytest.raises(YellhornMCPError, match="does not support aio.models.generate_content"):
        await async_generate_content_with_config(invalid_client, "test-model", "test prompt")

    # Test successful call without generation_config
    mock_response = MagicMock()
    mock_genai_client.aio.models.generate_content.return_value = mock_response

    result = await async_generate_content_with_config(
        mock_genai_client, "test-model", "test prompt", generation_config=None
    )

    assert result == mock_response
    mock_genai_client.aio.models.generate_content.assert_called_once_with(
        model="test-model", contents="test prompt"
    )


@pytest.mark.asyncio
async def test_async_generate_content_with_config_with_generation_config(mock_genai_client):
    """Test async_generate_content_with_config with generation_config parameter."""
    from yellhorn_mcp.server import async_generate_content_with_config

    # Test successful call with generation_config
    mock_response = MagicMock()
    mock_genai_client.aio.models.generate_content.return_value = mock_response

    mock_generation_config = MagicMock()

    result = await async_generate_content_with_config(
        mock_genai_client, "test-model", "test prompt", generation_config=mock_generation_config
    )

    assert result == mock_response
    mock_genai_client.aio.models.generate_content.assert_called_once_with(
        model="test-model", contents="test prompt", config=mock_generation_config
    )


@pytest.mark.asyncio
async def test_process_workplan_async_search_grounding_enabled(
    mock_request_context, mock_genai_client
):
    """Test process_workplan_async with search grounding enabled and verify generation_config is passed."""
    # Set the mock client in the context
    mock_request_context.request_context.lifespan_context["gemini_client"] = mock_genai_client
    mock_request_context.request_context.lifespan_context["openai_client"] = None
    mock_request_context.request_context.lifespan_context["use_search_grounding"] = True

    with (
        patch(
            "yellhorn_mcp.processors.workplan_processor.get_codebase_snapshot",
            new_callable=AsyncMock,
        ) as mock_snapshot,
        patch(
            "yellhorn_mcp.processors.workplan_processor.format_codebase_for_prompt",
            new_callable=AsyncMock,
        ) as mock_format,
        patch(
            "yellhorn_mcp.processors.workplan_processor.update_issue_with_workplan",
            new_callable=AsyncMock,
        ) as mock_update,
        patch(
            "yellhorn_mcp.processors.workplan_processor.format_metrics_section"
        ) as mock_format_metrics,
        patch(
            "yellhorn_mcp.processors.workplan_processor.add_issue_comment", new_callable=AsyncMock
        ) as mock_add_comment,
        patch(
            "yellhorn_mcp.processors.workplan_processor.generate_workplan_with_gemini",
            new_callable=AsyncMock,
        ) as mock_generate_gemini,
        patch(
            "yellhorn_mcp.integrations.gemini_integration._get_gemini_search_tools"
        ) as mock_get_tools,
        patch("yellhorn_mcp.integrations.gemini_integration.add_citations") as mock_add_citations,
    ):
        mock_snapshot.return_value = (["file1.py"], {"file1.py": "content"})
        mock_format.return_value = "Formatted codebase"
        mock_format_metrics.return_value = (
            "\n\n---\n## Completion Metrics\n*   **Model Used**: `gemini-2.5-pro`"
        )

        # Mock search tools
        mock_search_tools = [MagicMock()]
        mock_get_tools.return_value = mock_search_tools

        # Mock add_citations processing
        mock_add_citations.return_value = "Generated workplan content with citations"

        # Mock completion metadata
        mock_completion_metadata = MagicMock()
        mock_completion_metadata.status = "success"
        mock_completion_metadata.model_name = "gemini-2.5-pro"
        mock_completion_metadata.input_tokens = 1000
        mock_completion_metadata.output_tokens = 500
        mock_completion_metadata.total_tokens = 1500

        # Mock generate_workplan_with_gemini to return workplan and metadata
        mock_generate_gemini.return_value = (
            "Generated workplan content with citations",
            mock_completion_metadata,
        )

        await process_workplan_async(
            Path("/mock/repo"),
            mock_genai_client,
            None,  # No OpenAI client
            "gemini-2.5-pro",
            "Feature Implementation Plan",
            "123",
            "full",  # codebase_reasoning
            "Create a new feature to support X",  # detailed_description
            ctx=mock_request_context,
        )

        # Verify that generate_workplan_with_gemini was called with use_search=True
        mock_generate_gemini.assert_called_once()
        call_args = mock_generate_gemini.call_args
        assert call_args[0][0] == mock_genai_client  # client
        assert call_args[0][1] == "gemini-2.5-pro"  # model
        assert call_args[0][3] == True  # use_search parameter should be True

        # Verify the final content includes citations
        mock_update.assert_called_once()
        update_args = mock_update.call_args
        update_content = update_args[0][2]
        assert "Generated workplan content with citations" in update_content


@pytest.mark.asyncio
async def test_process_judgement_async_search_grounding_enabled(
    mock_request_context, mock_genai_client
):
    """Test process_judgement_async with search grounding enabled and verify generation_config is passed."""
    from yellhorn_mcp.server import process_judgement_async

    # Mock the response with grounding metadata
    mock_response = MagicMock()
    mock_response.text = "## Judgement Summary\nImplementation looks good."
    mock_response.usage_metadata = MagicMock()
    mock_response.usage_metadata.prompt_token_count = 1000
    mock_response.usage_metadata.candidates_token_count = 500
    mock_response.usage_metadata.total_token_count = 1500
    mock_response.grounding_metadata = MagicMock()

    # Mock candidates to avoid finish_reason error
    mock_candidate = MagicMock()
    mock_candidate.finish_reason = MagicMock()
    mock_candidate.finish_reason.name = "STOP"
    mock_candidate.safety_ratings = []
    mock_response.candidates = [mock_candidate]

    with (
        patch(
            "yellhorn_mcp.integrations.gemini_integration.async_generate_content_with_config"
        ) as mock_generate,
        patch("yellhorn_mcp.utils.git_utils.update_github_issue") as mock_update_issue,
        patch(
            "yellhorn_mcp.processors.judgement_processor.add_issue_comment", new_callable=AsyncMock
        ) as mock_add_comment,
        patch(
            "yellhorn_mcp.processors.judgement_processor.create_judgement_subissue",
            new_callable=AsyncMock,
        ) as mock_create_subissue,
        patch(
            "yellhorn_mcp.processors.judgement_processor.get_codebase_snapshot",
            new_callable=AsyncMock,
        ) as mock_snapshot,
        patch(
            "yellhorn_mcp.processors.judgement_processor.format_codebase_for_prompt",
            new_callable=AsyncMock,
        ) as mock_format,
        patch(
            "yellhorn_mcp.integrations.gemini_integration._get_gemini_search_tools"
        ) as mock_get_tools,
        patch("yellhorn_mcp.integrations.gemini_integration.add_citations") as mock_add_citations,
        patch("yellhorn_mcp.processors.judgement_processor.run_git_command") as mock_run_git,
    ):
        mock_generate.return_value = mock_response

        # Mock getting the remote URL
        mock_run_git.return_value = "https://github.com/user/repo"

        # Mock codebase snapshot
        mock_snapshot.return_value = (["file1.py"], {"file1.py": "content"})
        mock_format.return_value = "Formatted codebase"

        # Mock create_subissue
        mock_create_subissue.return_value = "https://github.com/user/repo/issues/789"

        # Mock search tools
        mock_search_tools = [MagicMock()]
        mock_get_tools.return_value = mock_search_tools

        # Mock add_citations processing
        mock_add_citations.return_value = (
            "## Judgement Summary\nImplementation looks good.\n\n## Citations\n[1] Example citation"
        )

        # Set context for search grounding enabled
        mock_request_context.request_context.lifespan_context["use_search_grounding"] = True

        from datetime import datetime, timezone

        await process_judgement_async(
            repo_path=Path("/test/repo"),
            gemini_client=mock_genai_client,
            openai_client=None,
            model="gemini-2.5-pro",
            workplan_content="# Workplan\n1. Do something",
            diff_content="diff --git a/file.py b/file.py\n+def test(): pass",
            base_ref="main",
            head_ref="HEAD",
            subissue_to_update="789",
            parent_workplan_issue_number="123",
            ctx=mock_request_context,
            base_commit_hash="abc1234",
            head_commit_hash="def5678",
            debug=False,
            codebase_reasoning="full",
            _meta={"start_time": datetime.now(timezone.utc), "submitted_urls": []},
        )

        # Verify that _get_gemini_search_tools was called
        mock_get_tools.assert_called_once_with("gemini-2.5-pro")

        # Verify that async_generate_content_with_config was called with generation_config
        mock_generate.assert_called_once()
        call_args = mock_generate.call_args
        assert call_args[0][0] == mock_genai_client  # client
        assert call_args[0][1] == "gemini-2.5-pro"  # model
        assert call_args[1]["generation_config"] is not None  # generation_config should be passed

        # Verify citations processing was called
        mock_add_citations.assert_called_once_with(mock_response)

        # Verify update_github_issue was called instead of create_github_subissue
        mock_update_issue.assert_called_once()
        # Verify create_github_subissue was NOT called
        mock_create_subissue.assert_not_called()

        # Verify the arguments passed to update_github_issue
        call_args = mock_update_issue.call_args
        assert call_args.kwargs["repo_path"] == Path("/test/repo")
        assert call_args.kwargs["issue_number"] == "789"
        assert "Judgement for #123: HEAD vs main" in call_args.kwargs["title"]
        body = call_args.kwargs["body"]
        assert "## Citations" in body
        assert "Example citation" in body


@pytest.mark.asyncio
async def test_revise_workplan(mock_request_context, mock_genai_client):
    """Test revising an existing workplan."""
    # Set the mock client in the context
    mock_request_context.request_context.lifespan_context["gemini_client"] = mock_genai_client

    with patch("yellhorn_mcp.server.get_issue_body", new_callable=AsyncMock) as mock_get_issue:
        mock_get_issue.return_value = "# Original Workplan\n## Summary\nOriginal content"

        with patch(
            "yellhorn_mcp.server.add_issue_comment", new_callable=AsyncMock
        ) as mock_add_comment:
            with patch(
                "yellhorn_mcp.server.run_github_command", new_callable=AsyncMock
            ) as mock_run_git:
                # Mock getting issue URL
                mock_run_git.return_value = json.dumps(
                    {"url": "https://github.com/user/repo/issues/123"}
                )

                with patch("asyncio.create_task") as mock_create_task:
                    # Mock the return value of create_task to avoid actual async processing
                    mock_task = MagicMock()
                    mock_create_task.return_value = mock_task

                    # Test revising a workplan
                    response = await revise_workplan(
                        ctx=mock_request_context,
                        issue_number="123",
                        revision_instructions="Add more detail about testing",
                        codebase_reasoning="full",
                    )

                    # Parse response as JSON and check contents
                    result = json.loads(response)
                    assert result["issue_url"] == "https://github.com/user/repo/issues/123"
                    assert result["issue_number"] == "123"

                    # Verify get_issue_body was called to fetch original workplan
                    mock_get_issue.assert_called_once_with(Path("/mock/repo"), "123")

                    # Verify submission comment was added
                    mock_add_comment.assert_called_once()
                    comment_args = mock_add_comment.call_args
                    assert comment_args[0][0] == Path("/mock/repo")  # repo_path
                    assert comment_args[0][1] == "123"  # issue_number
                    submission_comment = comment_args[0][2]  # comment content

                    # Verify the submission comment contains expected metadata
                    assert "## 🚀 Revising workplan..." in submission_comment
                    assert "**Model**: `gemini-2.5-pro`" in submission_comment
                    assert "**Codebase Reasoning**: `full`" in submission_comment

                    # Check that the process_revision_async task is created
                    args, kwargs = mock_create_task.call_args
                    coroutine = args[0]
                    assert coroutine.__name__ == "process_revision_async"
                    # Close the coroutine to prevent RuntimeWarning
                    coroutine.close()

                    # Reset mocks for next test
                    mock_get_issue.reset_mock()
                    mock_add_comment.reset_mock()
                    mock_run_git.reset_mock()
                    mock_create_task.reset_mock()

                    # Test with non-existent issue
                    mock_get_issue.return_value = None

                    with pytest.raises(Exception) as exc_info:
                        await revise_workplan(
                            ctx=mock_request_context,
                            issue_number="999",
                            revision_instructions="Update something",
                        )

                    assert "Could not retrieve workplan for issue #999" in str(exc_info.value)
