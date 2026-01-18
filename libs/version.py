# Google-Drive-Mirror - Mirror/Indexer of Gdrive with FastAPI
# Copyright (C) 2025 kaif-00z
#
# This file is a part of < https://github.com/kaif-00z/Google-Drive-Mirror/ >
# PLease read the GNU Affero General Public License in
# <https://github.com/kaif-00z/Google-Drive-Mirror/blob/main/LICENSE>.

# if you are using this following code then don't forgot to give proper
# credit to t.me/kAiF_00z (github.com/kaif-00z)

# inspired from tiann/KernelSU versioning system

import subprocess

def get_git_output(args: list[str]) -> str:
    try:
        result = subprocess.run(args, capture_output=True, text=True, check=False)
        if result.returncode != 0:
            return ""
        return result.stdout.strip()
    except Exception:
        return ""


def get_version_code() -> int:
    ccs = get_git_output(["git", "rev-list", "--count", "HEAD"])
    if ccs.isdigit():
        commit_count = int(ccs)
    else:
        commit_count = 0

    return commit_count


def get_branch_channel() -> str:
    branch_name = get_git_output(["git", "rev-parse", "--abbrev-ref", "HEAD"]).lower()

    if not branch_name.strip():
        return "unknown"

    if branch_name in ["main", "master"]:
        return "stable"
    
    if branch_name == "dev" or "develop" in branch_name:
        return "beta"
    
    return branch_name


def get_version_info(version_tuple: tuple[int, int, int] = (1, 0, 0)) -> str:
    major, minor, patch = version_tuple
    version_code = get_version_code()
    branch_channel = get_branch_channel()
    return f"v{major}.{minor}.{patch}@{branch_channel}.r{version_code}"