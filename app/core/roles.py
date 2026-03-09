"""User role constants: 普通会员, 中级用户, 高级用户, 管理员."""

# Internal keys (DB / API)
ROLE_MEMBER = "member"           # 普通会员
ROLE_INTERMEDIATE = "intermediate"  # 中级用户
ROLE_ADVANCED = "advanced"      # 高级用户
ROLE_ADMIN = "admin"            # 管理员

ALL_ROLES = [ROLE_MEMBER, ROLE_INTERMEDIATE, ROLE_ADVANCED, ROLE_ADMIN]
ROLE_RANK = {
    ROLE_MEMBER: 1,
    ROLE_INTERMEDIATE: 2,
    ROLE_ADVANCED: 3,
    ROLE_ADMIN: 4,
}
ROLE_LABELS = {
    ROLE_MEMBER: "普通会员",
    ROLE_INTERMEDIATE: "中级用户",
    ROLE_ADVANCED: "高级用户",
    ROLE_ADMIN: "管理员",
}

def is_valid_role(role: str) -> bool:
    return role in ALL_ROLES

def is_admin(role: str) -> bool:
    return role == ROLE_ADMIN


def has_min_role(role: str, required_role: str) -> bool:
    """Return True when role is greater than or equal to required role."""
    return ROLE_RANK.get(role, 0) >= ROLE_RANK.get(required_role, 0)
