class Permissions:
    AGENT_READ = "agent:read"
    AGENT_CREATE = "agent:create"
    AGENT_UPDATE = "agent:update"
    AGENT_DELETE = "agent:delete"
    AGENT_RUN = "agent:run"

    VOICE_START = "voice:start"

    USER_READ = "user:read"
    USER_CREATE = "user:create"
    USER_UPDATE = "user:update"

    DOCUMENT_READ = "document:read"
    DOCUMENT_CREATE = "document:create"
    DOCUMENT_DELETE = "document:delete"

    ALL = frozenset({
        AGENT_READ,
        AGENT_CREATE,
        AGENT_UPDATE,
        AGENT_DELETE,
        AGENT_RUN,
        VOICE_START,
        USER_READ,
        USER_CREATE,
        USER_UPDATE,
        DOCUMENT_READ,
        DOCUMENT_CREATE,
        DOCUMENT_DELETE,
    })


ROLE_ADMIN = "admin"
ROLE_MEMBER = "member"

DEFAULT_ROLE_PERMISSIONS: dict[str, frozenset[str]] = {
    ROLE_ADMIN: Permissions.ALL,
    ROLE_MEMBER: frozenset({
        Permissions.AGENT_READ,
        Permissions.AGENT_RUN,
        Permissions.VOICE_START,
        Permissions.USER_READ,
        Permissions.DOCUMENT_READ,
    }),
}
