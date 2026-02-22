"""
Auraxis AI Squad — Tools package.

Re-exports all BaseTool classes for convenient import.
Uses conditional import so that tool_security.py (which has no external
dependencies) can be imported and tested even when crewai is not installed.
"""

try:
    from .project_tools import (  # noqa: F401
        AWSStatusTool,
        GetLatestMigrationTool,
        GitOpsTool,
        IntegrationTestTool,
        ListProjectFilesTool,
        ReadAlembicHistoryTool,
        ReadContextFileTool,
        ReadGovernanceFileTool,
        ReadPendingTasksTool,
        ReadProjectFileTool,
        ReadSchemaTool,
        ReadTasksSectionTool,
        ReadTasksTool,
        RunTestsTool,
        UpdateTaskStatusTool,
        ValidateMigrationConsistencyTool,
        WriteFileTool,
    )
except ImportError:
    # crewai not installed — tools are unavailable but tool_security
    # remains importable for testing.
    pass
