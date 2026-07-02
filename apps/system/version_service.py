# -*- coding: utf-8 -*-
"""
Backward-compatible facade for the new official update center service.

Historically this module implemented git-tag based update detection and
checkout-based updates. The implementation has now moved to
`apps.system.update_center_service`, but existing imports in views/context
processors/management commands still point here.
"""

from apps.system.update_center_service import (  # noqa: F401
    backup_database,
    check_for_updates,
    compare_versions,
    deploy_root,
    ensure_deploy_layout,
    extract_release_package,
    fetch_latest_release_info,
    finalize_staged_release,
    get_current_branch,
    get_current_commit,
    get_current_version,
    get_rollback_info,
    get_system_health,
    import_docker_images,
    load_update_state,
    normalize_version,
    perform_offline_import,
    perform_online_update,
    perform_rollback,
    read_manifest,
    release_dir,
    save_update_state,
    sha256_of_file,
    stage_release_to_version_dir,
    switch_current_release,
    update_center_latest_url,
    verify_release_package,
)


def perform_update(target_version=None):
    return perform_online_update(target_version=target_version)
