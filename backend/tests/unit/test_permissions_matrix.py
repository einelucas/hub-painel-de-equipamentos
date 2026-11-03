from app.core.permissions import Permission, Role, can


def test_analyst_has_operational_permissions_without_privilege_escalation() -> None:
    assert can(Role.ANALYST, Permission.CATALOGS_MANAGE)
    assert can(Role.ANALYST, Permission.AUDIT_READ)
    assert can(Role.ANALYST, Permission.WORKFLOW_REOPEN_REQUEST)
    assert not can(Role.ANALYST, Permission.WORKFLOW_REOPEN_APPROVE)
    assert not can(Role.ANALYST, Permission.USERS_MANAGE)


def test_admin_is_the_only_role_allowed_to_decide_reopen_requests() -> None:
    assert can(Role.ADMIN, Permission.WORKFLOW_REOPEN_APPROVE)
    assert not can(Role.VIEWER, Permission.WORKFLOW_REOPEN_APPROVE)
    assert not can(Role.ANALYST, Permission.WORKFLOW_REOPEN_APPROVE)


def test_viewer_remains_read_only() -> None:
    assert can(Role.VIEWER, Permission.EQUIPMENTS_READ)
    assert not can(Role.VIEWER, Permission.EQUIPMENTS_WRITE)
    assert not can(Role.VIEWER, Permission.WORKFLOW_REOPEN_REQUEST)
